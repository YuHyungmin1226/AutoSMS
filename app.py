import customtkinter as ctk # type: ignore
import pandas as pd # type: ignore
from tkinter import messagebox, filedialog
from PIL import Image # type: ignore
from utils import get_byte_length, determine_msg_type # type: ignore
from address_book import AddressBookManager # type: ignore
from sending_manager import SendingManager # type: ignore
from solapi_service import SolapiService # type: ignore
from config_manager import load_config, save_config, is_config_valid # type: ignore
from database import init_db # type: ignore
from mms_image_utils import MMS_ALLOWED_EXTENSIONS
import threading
import time
import os

# 앱 기본 설정: 프리미엄 다크 테마
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class ContactSelector(ctk.CTkToplevel):
    def __init__(self, parent, contacts_df, on_confirm):
        super().__init__(parent) # type: ignore
        self.title("연락처 선택")
        self.geometry("500x650")
        self.on_confirm = on_confirm
        self.contacts_df = contacts_df
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # 1. 상단 필터 및 툴바
        filter_frame = ctk.CTkFrame(self)
        filter_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        
        ctk.CTkLabel(filter_frame, text="그룹 필터:").pack(side="left", padx=5)
        categories = ["전체"] + sorted([str(c) for c in contacts_df['category'].unique() if c])
        self.filter_var = ctk.StringVar(value="전체")
        self.filter_menu = ctk.CTkComboBox(filter_frame, values=categories, variable=self.filter_var, command=self.apply_filter)
        self.filter_menu.pack(side="left", padx=5, fill="x", expand=True)

        toolbar = ctk.CTkFrame(self)
        toolbar.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        
        ctk.CTkButton(toolbar, text="전체 선택", width=100, command=self.select_all).pack(side="left", padx=5)
        ctk.CTkButton(toolbar, text="전체 해제", width=100, command=self.deselect_all).pack(side="left", padx=5)

        # 2. 목록 영역
        self.scroll_frame = ctk.CTkScrollableFrame(self)
        self.scroll_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        
        self.check_vars = [] # List of (var, phone, widget)
        self.render_contacts()

        # 3. 하단 확인 버튼
        ctk.CTkButton(self, text="선택 완료", height=45, command=self.confirm).grid(row=3, column=0, sticky="ew", padx=10, pady=10)

    def render_contacts(self):
        # 기존 위젯 제거
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        
        self.check_vars = []
        filter_val = self.filter_var.get()
        
        for i, row in self.contacts_df.iterrows():
            category = str(row.get("category", ""))
            if filter_val != "전체" and category != filter_val:
                continue
                
            var = ctk.BooleanVar()
            name = str(row.get("name", "이름없음"))
            phone = str(row.get("phone", ""))
            cb = ctk.CTkCheckBox(self.scroll_frame, text=f"{name} ({phone}) [{category}]", variable=var)
            cb.pack(fill="x", padx=10, pady=5)
            self.check_vars.append((var, phone))

    def apply_filter(self, choice):
        self.render_contacts()

    def select_all(self):
        for var, _ in self.check_vars:
            var.set(True)

    def deselect_all(self):
        for var, _ in self.check_vars:
            var.set(False)

    def confirm(self):
        selected_phones = [phone for var, phone in self.check_vars if var.get()]
        self.on_confirm(selected_phones)
        self.destroy()

class AutoSMSApp(ctk.CTk):
    def __init__(self):
        super().__init__() # type: ignore
        
        # DB 초기화 강제 실행 (포터블 환경 대응)
        init_db()

        self.title("Auto SMS Premium - Pro Edition")
        self.geometry("1200x800")
        self.minsize(1000, 700)
        self.selected_image_paths = []
        self.selected_image_preview = None

        # 시스템 매니저 초기화
        self.db_mgr = AddressBookManager()
        self.send_mgr = SendingManager()
        
        # UI 레이아웃 구성
        self.setup_ui()
        self.load_data()

        # 초기 설정 체크
        if not is_config_valid():
            self.after(1000, self.show_initial_setup_popup)

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- 사이드바 (내비게이션) ---
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(5, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="PREMIUM\nSMS SYSTEM", font=ctk.CTkFont(size=22, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(30, 40))

        self.nav_btns = {}
        nav_items = [
            ("send", "✉  메시지 발송"),
            ("contacts", "👥  주소록 관리"),
            ("logs", "📊  발송 내역"),
            ("settings", "⚙  설정 및 가이드")
        ]

        for i, (key, text) in enumerate(nav_items):
            btn = ctk.CTkButton(self.sidebar_frame, text=text, height=45, corner_radius=8,
                               fg_color="transparent", text_color=("gray10", "gray90"), 
                               hover_color=("gray70", "gray30"), anchor="w",
                               command=lambda k=key: self.select_screen(k))
            btn.grid(row=i+1, column=0, padx=15, pady=8, sticky="ew")
            self.nav_btns[key] = btn

        self.info_label = ctk.CTkLabel(self.sidebar_frame, text="SOLAPI 연동 중", font=ctk.CTkFont(size=11))
        self.info_label.grid(row=6, column=0, pady=20)

        # --- 메인 컨텐츠 영역 ---
        self.main_content = ctk.CTkFrame(self, corner_radius=15, fg_color="transparent")
        self.main_content.grid(row=0, column=1, padx=25, pady=25, sticky="nsew")
        self.main_content.grid_columnconfigure(0, weight=1)
        self.main_content.grid_rowconfigure(0, weight=1)

        # 화면 프레임 생성
        self.screens = {
            "send": self.create_send_screen(),
            "contacts": self.create_contacts_screen(),
            "logs": self.create_logs_screen(),
            "settings": self.create_settings_screen()
        }

        self.select_screen("send")

    def create_send_screen(self):
        frame = ctk.CTkFrame(self.main_content, fg_color="transparent")
        
        # 헤더
        header_frame = ctk.CTkFrame(frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 25))
        ctk.CTkLabel(header_frame, text="메시지 발송 센터", font=ctk.CTkFont(size=28, weight="bold")).pack(side="left")
        self.current_method_lbl = ctk.CTkLabel(header_frame, text="[ 발송 모드 파악 중... ]", font=ctk.CTkFont(size=14, weight="bold"))
        self.current_method_lbl.pack(side="right", padx=10)

        content_layout = ctk.CTkFrame(frame, fg_color="transparent")
        content_layout.pack(fill="both", expand=True)
        content_layout.grid_columnconfigure(0, weight=1, uniform="send_columns")
        content_layout.grid_columnconfigure(1, weight=1, uniform="send_columns")
        content_layout.grid_rowconfigure(0, weight=1)

        # 1. 수신인 섹션
        recv_frame = ctk.CTkFrame(content_layout, corner_radius=12)
        recv_frame.grid(row=0, column=0, padx=(0, 15), sticky="nsew")
        
        recv_header = ctk.CTkFrame(recv_frame, fg_color="transparent")
        recv_header.pack(fill="x", padx=20, pady=(15, 5))
        
        recv_title = ctk.CTkFrame(recv_header, fg_color="transparent")
        recv_title.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(recv_title, text="1. 수신인 목록", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(recv_title, text="한 줄에 한 번호씩 입력하거나 주소록에서 불러오세요.", text_color="gray70", font=ctk.CTkFont(size=12)).pack(anchor="w")
        
        ctk.CTkButton(recv_header, text="🗑 비우기", width=80, height=28, 
                      fg_color="#A02020", hover_color="#801010", command=self.on_clear_recipients).pack(side="right", padx=(5, 0))
        
        ctk.CTkButton(recv_header, text="📂 주소록에서 불러오기", width=140, height=28, 
                      fg_color="gray30", hover_color="gray40", command=self.on_load_contacts).pack(side="right")
        
        self.recipients_box = ctk.CTkTextbox(recv_frame, height=350, border_width=1)
        self.recipients_box.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.recipients_box.bind("<ButtonRelease-1>", self.on_recipient_select)
        self.recipients_box.bind("<KeyRelease>", self.on_recipient_select)

        # 2. 메시지 섹션
        msg_frame = ctk.CTkFrame(content_layout, corner_radius=12)
        msg_frame.grid(row=0, column=1, padx=(15, 0), sticky="nsew")
        
        msg_header = ctk.CTkFrame(msg_frame, fg_color="transparent")
        msg_header.pack(fill="x", padx=20, pady=(15, 5))
        ctk.CTkLabel(msg_header, text="2. 메시지 작성", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(msg_header, text="AUTO는 길이에 따라 SMS/LMS를 자동 판단합니다.", text_color="gray70", font=ctk.CTkFont(size=12)).pack(anchor="w")
        self.msg_box = ctk.CTkTextbox(msg_frame, height=350, border_width=1)
        self.msg_box.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        self.msg_box.bind("<KeyRelease>", self.refresh_byte_info)

        # 정보바
        status_bar = ctk.CTkFrame(msg_frame, height=40, fg_color="gray25", corner_radius=0)
        status_bar.pack(fill="x", padx=20, pady=(0, 20))
        
        self.byte_info = ctk.CTkLabel(status_bar, text="0 / 90 bytes (SMS)", font=ctk.CTkFont(size=12))
        self.byte_info.pack(side="left", padx=15)

        self.msg_type_var = ctk.StringVar(value="AUTO")
        self.type_menu = ctk.CTkOptionMenu(status_bar, values=["AUTO", "SMS", "LMS", "MMS"], width=100, variable=self.msg_type_var, command=self.on_msg_type_change)
        self.type_menu.pack(side="right", padx=10)

        # 옵션 섹션
        opt_frame = ctk.CTkFrame(msg_frame, fg_color="transparent")
        opt_frame.pack(fill="x", padx=20, pady=(0, 10))
        
        self.use_memo_var = ctk.BooleanVar(value=False)
        self.use_memo_cb = ctk.CTkCheckBox(opt_frame, text="메모 컬럼을 개별 메시지로 발송", 
                                           variable=self.use_memo_var, command=self.on_memo_toggle)
        self.use_memo_cb.pack(side="left")

        # 여러 이미지는 전송 직전에 MMS 규격에 맞는 한 장의 이미지로 합성됩니다.
        attach_frame = ctk.CTkFrame(msg_frame, corner_radius=10, fg_color=("gray88", "gray18"))
        attach_frame.pack(fill="x", padx=20, pady=(0, 20))
        attach_frame.grid_columnconfigure(1, weight=1)

        self.image_preview_label = ctk.CTkLabel(attach_frame, text="이미지\n없음", width=86, height=64, fg_color=("gray78", "gray25"), corner_radius=8)
        self.image_preview_label.grid(row=0, column=0, rowspan=2, padx=12, pady=12, sticky="ns")

        ctk.CTkLabel(attach_frame, text="MMS 이미지 첨부", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=1, padx=(0, 12), pady=(12, 2), sticky="w")
        self.image_status_label = ctk.CTkLabel(attach_frame, text="선택된 이미지 없음", text_color="gray70", anchor="w")
        self.image_status_label.grid(row=1, column=1, padx=(0, 12), pady=(0, 12), sticky="ew")

        image_buttons = ctk.CTkFrame(attach_frame, fg_color="transparent")
        image_buttons.grid(row=0, column=2, rowspan=2, padx=(0, 12), pady=12, sticky="e")
        ctk.CTkButton(image_buttons, text="이미지 선택", width=100, height=30, command=self.on_select_image).pack(pady=(0, 6))
        ctk.CTkButton(image_buttons, text="해제", width=100, height=30, fg_color="gray35", hover_color="gray28", command=self.on_clear_image).pack()

        # 3. 하단 버튼
        self.send_action_btn = ctk.CTkButton(frame, text="메시지 전송 시작", height=60, font=ctk.CTkFont(size=18, weight="bold"),
                                          fg_color="#1f538d", hover_color="#14375e", command=self.on_send_click)
        self.send_action_btn.pack(fill="x", pady=(30, 0))

        return frame

    def create_contacts_screen(self):
        frame = ctk.CTkFrame(self.main_content, fg_color="transparent")
        
        header = ctk.CTkLabel(frame, text="주소록 매니저", font=ctk.CTkFont(size=28, weight="bold"))
        header.pack(pady=(0, 20), anchor="w")

        # 툴바
        toolbar = ctk.CTkFrame(frame, corner_radius=10, height=60)
        toolbar.pack(fill="x", pady=(0, 20))
        
        ctk.CTkButton(toolbar, text="+ 단일 추가", width=120, command=self.dummy_action).pack(side="left", padx=15, pady=10)
        ctk.CTkButton(toolbar, text="📥 엑셀 불러오기", fg_color="green", hover_color="darkgreen", command=self.on_excel_import).pack(side="left", padx=5)
        ctk.CTkButton(toolbar, text="📤 엑셀 내보내기", command=self.on_excel_export).pack(side="left", padx=5)
        
        ctk.CTkButton(toolbar, text="🗑 전체 삭제", fg_color="#A02020", hover_color="#801010", command=self.on_delete_all_contacts).pack(side="right", padx=15, pady=10)
        ctk.CTkButton(toolbar, text="✂ 선택 삭제", fg_color="#A02020", hover_color="#801010", command=self.on_delete_selected_contacts).pack(side="right", padx=5)

        # 테이블 영역
        self.contacts_view = ctk.CTkTextbox(frame, font=ctk.CTkFont(family="Consolas", size=13))
        self.contacts_view.pack(fill="both", expand=True)

        return frame

    def create_logs_screen(self):
        frame = ctk.CTkFrame(self.main_content, fg_color="transparent")
        header = ctk.CTkLabel(frame, text="발송 히스토리", font=ctk.CTkFont(size=28, weight="bold"))
        header.pack(pady=(0, 20), anchor="w")

        self.logs_view = ctk.CTkTextbox(frame, font=ctk.CTkFont(family="Consolas", size=12))
        self.logs_view.pack(fill="both", expand=True)
        
        ctk.CTkButton(frame, text="새로고침", width=150, command=self.load_data).pack(pady=20)
        return frame

    def create_settings_screen(self):
        frame = ctk.CTkFrame(self.main_content, fg_color="transparent")
        header = ctk.CTkLabel(frame, text="시스템 설정 & 연동 가이드", font=ctk.CTkFont(size=28, weight="bold"))
        header.pack(pady=(0, 25), anchor="w")

        # 발송 수단 선택
        method_frame = ctk.CTkFrame(frame, corner_radius=15)
        method_frame.pack(fill="x", pady=(0, 20))
        ctk.CTkLabel(method_frame, text="발송 엔진 선택:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=25, pady=15)
        
        self.send_method_var = ctk.StringVar(value="SOLAPI")
        ctk.CTkRadioButton(method_frame, text="SOLAPI (대량발송 특화)", variable=self.send_method_var, value="SOLAPI", command=self.on_method_change).pack(side="left", padx=10)
        ctk.CTkRadioButton(method_frame, text="ADB 연동 (기기 무료 발송)", variable=self.send_method_var, value="ADB", command=self.on_method_change).pack(side="left", padx=10)

        # 설정 내용 프레임들
        self.settings_content_frame = ctk.CTkFrame(frame, fg_color="transparent")
        self.settings_content_frame.pack(fill="both", expand=True)

        self.solapi_frame = self.create_solapi_settings(self.settings_content_frame)
        self.adb_frame = self.create_adb_settings(self.settings_content_frame)

        btn_layout = ctk.CTkFrame(frame, fg_color="transparent")
        btn_layout.pack(fill="x", pady=10, side="bottom")
        ctk.CTkButton(btn_layout, text="설정값 저장하기", fg_color="#1f538d", width=250, command=self.on_save_settings).pack(side="right")

        return frame

    def create_solapi_settings(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        guide_box = ctk.CTkFrame(frame, border_width=2, border_color="#1f538d", corner_radius=15)
        guide_box.pack(fill="x", pady=(0, 20))
        guide_txt = "✨ SOLAPI 연동 가이드\n   1. solapi.com 회원가입\n   2. [개발/연동] -> API Key 발급\n   3. 발신자 번호 사전 인증 필수"
        ctk.CTkLabel(guide_box, text=guide_txt, justify="left", font=ctk.CTkFont(size=14)).pack(padx=25, pady=15)

        entry_frame = ctk.CTkFrame(frame, corner_radius=15)
        entry_frame.pack(fill="x", expand=False)
        self.ui_api_key = self.make_entry(entry_frame, "API KEY", 0)
        self.ui_api_secret = self.make_entry(entry_frame, "API SECRET (비밀키)", 1)
        self.ui_sender = self.make_entry(entry_frame, "발신 번호 (인증완료)", 2)

        bot_layout = ctk.CTkFrame(frame, fg_color="transparent")
        bot_layout.pack(fill="x", pady=20)
        self.balance_lbl = ctk.CTkLabel(bot_layout, text="잔액: 조회 전", font=ctk.CTkFont(weight="bold"))
        self.balance_lbl.pack(side="left", padx=5)
        ctk.CTkButton(bot_layout, text="잔액 확인", width=100, command=self.check_solapi_balance).pack(side="left", padx=10)
        return frame

    def create_adb_settings(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        guide_box = ctk.CTkFrame(frame, border_width=2, border_color="#2b8a3e", corner_radius=15)
        guide_box.pack(fill="x", pady=(0, 20))
        guide_txt = "📱 모바일 ADB 발송 가이드\n   1. 스마트폰 개발자 옵션 및 USB 디버깅 활성화\n   2. PC와 USB 연결 후 권한 승인\n   3. 좌표값(X,Y) 입력 시 전송 버튼 자동 클릭 (빈칸이면 수작업 터치 요망)"
        ctk.CTkLabel(guide_box, text=guide_txt, justify="left", font=ctk.CTkFont(size=14)).pack(padx=25, pady=15)

        entry_frame = ctk.CTkFrame(frame, corner_radius=15)
        entry_frame.pack(fill="x", expand=False)
        self.ui_adb_x = self.make_entry(entry_frame, "전송 버튼 X 좌표 (선택)", 0)
        self.ui_adb_y = self.make_entry(entry_frame, "전송 버튼 Y 좌표 (선택)", 1)
        self.ui_adb_delay = self.make_entry(entry_frame, "문자앱 로딩 대기시간 (초, 기본 2.0)", 2)

        bot_layout = ctk.CTkFrame(frame, fg_color="transparent")
        bot_layout.pack(fill="x", pady=20)
        self.adb_status_lbl = ctk.CTkLabel(bot_layout, text="기기 통신: 기기 확인 요망", font=ctk.CTkFont(weight="bold"))
        self.adb_status_lbl.pack(side="left", padx=5)
        ctk.CTkButton(bot_layout, text="기기 연결 확인", width=120, fg_color="#2b8a3e", hover_color="#2b8a3e", command=self.check_adb_device).pack(side="left", padx=10)
        return frame

    def on_method_change(self):
        method = self.send_method_var.get()
        if method == "ADB":
            self.solapi_frame.pack_forget()
            self.adb_frame.pack(fill="both", expand=True)
        else:
            self.adb_frame.pack_forget()
            self.solapi_frame.pack(fill="both", expand=True)

    def update_send_mode_label(self):
        config_method = load_config().get("send_method", "SOLAPI")
        if hasattr(self, 'current_method_lbl'):
            if config_method == "ADB":
                self.current_method_lbl.configure(text="[ 현재 수단: 스마트폰 ADB 발송 (무료) ]", text_color="#2b8a3e")
            else:
                self.current_method_lbl.configure(text="[ 현재 수단: SOLAPI 서버 연동 발송 ]", text_color="#1f538d")

    def on_memo_toggle(self):
        if self.use_memo_var.get():
            self.msg_box.configure(state="disabled", fg_color="gray30")
            self.byte_info.configure(text="개별 메모 발송 모드 활성화됨")
            
            # 메모 캐시 생성
            df = self.db_mgr.get_all_contacts()
            self.memo_cache = {str(row['phone']): str(row['memo']) for _, row in df.iterrows() if row.get('memo')}
            
            # 안내 메시지 표시
            self.msg_box.configure(state="normal")
            self.msg_box.delete("1.0", "end")
            self.msg_box.insert("1.0", "수신인 목록에서 번호를 클릭하면 개별 메시지 내용을 미리볼 수 있습니다.")
            self.msg_box.configure(state="disabled")
        else:
            self.msg_box.configure(state="normal", fg_color="gray20")
            self.memo_cache = {}
            self.msg_box.delete("1.0", "end")
            self.refresh_byte_info()

    def on_recipient_select(self, event=None):
        if not self.use_memo_var.get() or not hasattr(self, 'memo_cache'):
            return
            
        try:
            # 현재 커서가 위치한 줄의 텍스트(전화번호) 가져오기
            idx = self.recipients_box.index("insert")
            line_num = idx.split('.')[0]
            phone = self.recipients_box.get(f"{line_num}.0", f"{line_num}.end").strip()
            
            if not phone:
                return
                
            memo = self.memo_cache.get(phone, "[메모가 등록되지 않은 연락처입니다]")
            
            # 메시지 창 업데이트
            self.msg_box.configure(state="normal")
            self.msg_box.delete("1.0", "end")
            self.msg_box.insert("1.0", memo)
            self.msg_box.configure(state="disabled")
            
            # 바이트 정보 업데이트
            blen = get_byte_length(memo)
            mtype = determine_msg_type(memo, self.msg_type_var.get() if self.msg_type_var.get() != "AUTO" else None)
            limit = 90 if mtype == "SMS" else 2000
            self.byte_info.configure(text=f"선택된 메모: {blen} / {limit} bytes ({mtype})")
            
        except Exception as e:
            print(f"Error in on_recipient_select: {e}")

    def make_entry(self, parent, lbl, row):
        ctk.CTkLabel(parent, text=lbl).grid(row=row, column=0, padx=25, pady=15, sticky="w")
        ent = ctk.CTkEntry(parent, width=400, height=35)
        ent.grid(row=row, column=1, padx=(0, 25), pady=15, sticky="ew")
        parent.grid_columnconfigure(1, weight=1)
        return ent

    # --- 로직 함수들 ---

    def select_screen(self, name):
        for k, screen in self.screens.items():
            if k == name:
                screen.pack(fill="both", expand=True)
                self.nav_btns[k].configure(fg_color="#1f538d", text_color="white")
            else:
                screen.pack_forget()
                self.nav_btns[k].configure(fg_color="transparent", text_color=("gray10", "gray90"))

        if name == "settings": 
            self.load_settings_ui()
        elif name == "send":
            self.update_send_mode_label()

    def on_msg_type_change(self, _choice=None):
        self.refresh_byte_info()
        if self.msg_type_var.get() == "MMS" and not self.selected_image_paths:
            self.image_status_label.configure(text="MMS 선택됨 · 이미지를 첨부하거나 텍스트 MMS로 발송할 수 있습니다.", text_color="#f0ad4e")
        elif not self.selected_image_paths:
            self.image_status_label.configure(text="선택된 이미지 없음", text_color="gray70")

    def refresh_byte_info(self, e=None):
        txt = self.msg_box.get("1.0", "end-1c")
        blen = get_byte_length(txt)
        mtype = determine_msg_type(txt, self.msg_type_var.get() if self.msg_type_var.get() != "AUTO" else None)
        limit = 90 if mtype == "SMS" else 2000
        self.byte_info.configure(text=f"{blen} / {limit} bytes ({mtype})")

    def on_select_image(self):
        file_paths = filedialog.askopenfilenames(
            title="첨부 이미지 선택",
            filetypes=[
                ("Image Files", "*.jpg *.jpeg *.png *.gif"),
                ("All Files", "*.*")
            ]
        )
        if not file_paths:
            return

        try:
            invalid_files = [
                os.path.basename(path) for path in file_paths
                if os.path.splitext(path)[1].lower() not in MMS_ALLOWED_EXTENSIONS
            ]
            if invalid_files:
                raise ValueError(f"지원하지 않는 형식: {', '.join(invalid_files)}")

            first_image = file_paths[0]
            with Image.open(first_image) as img:
                img.thumbnail((86, 64))
                preview = ctk.CTkImage(light_image=img.copy(), dark_image=img.copy(), size=img.size)

            self.selected_image_paths = list(file_paths)
            self.selected_image_preview = preview
            file_name = os.path.basename(first_image)
            if len(file_name) > 34:
                file_name = f"{file_name[:16]}...{file_name[-15:]}"
            total_kb = max(1, sum(os.path.getsize(path) for path in self.selected_image_paths) // 1024)

            if len(self.selected_image_paths) == 1:
                status_text = f"{file_name} · 총 {total_kb:,} KB · MMS로 발송"
            else:
                status_text = f"{file_name} 외 {len(self.selected_image_paths) - 1}개 · 총 {total_kb:,} KB · MMS로 발송"

            self.image_preview_label.configure(text="", image=self.selected_image_preview)
            self.image_status_label.configure(
                text=status_text,
                text_color="#2b8a3e"
            )
            if self.msg_type_var.get() != "MMS":
                self.msg_type_var.set("MMS")
                self.refresh_byte_info()
        except Exception as e:
            self.selected_image_paths = []
            self.selected_image_preview = None
            self.image_preview_label.configure(text="이미지\n없음", image=None)
            messagebox.showerror("이미지 오류", f"이미지를 불러오지 못했습니다.\n{e}")

    def on_clear_image(self):
        self.selected_image_paths = []
        self.selected_image_preview = None
        self.image_preview_label.configure(text="이미지\n없음", image=None)
        self.on_msg_type_change()

    def load_data(self):
        # 주소록 로드 및 표시 가공
        df = self.db_mgr.get_all_contacts()
        self.contacts_view.delete("1.0", "end")
        if not df.empty:
            display_df = df.rename(columns={"name": "이름", "phone": "전화번호", "category": "그룹", "memo": "메모"})
            self.contacts_view.insert("1.0", display_df.drop(columns=['id', 'created_at'], errors='ignore').to_string(index=False))
        else:
            self.contacts_view.insert("1.0", "등록된 연락처가 없습니다.")

        # 로그 로드
        logs = self.send_mgr.get_logs()
        self.logs_view.delete("1.0", "end")
        for log in logs:
            self.logs_view.insert("end", f"[{log[1]}] {log[2]} -> {log[5]} ({log[4]})\n")

    def load_settings_ui(self):
        c = load_config()
        self.ui_api_key.delete(0, "end"); self.ui_api_key.insert(0, c.get("api_key", ""))
        self.ui_api_secret.delete(0, "end"); self.ui_api_secret.insert(0, c.get("api_secret", ""))
        self.ui_sender.delete(0, "end"); self.ui_sender.insert(0, c.get("sender_phone", ""))
        
        self.send_method_var.set(c.get("send_method", "SOLAPI"))
        self.ui_adb_x.delete(0, "end"); self.ui_adb_x.insert(0, c.get("adb_click_x", ""))
        self.ui_adb_y.delete(0, "end"); self.ui_adb_y.insert(0, c.get("adb_click_y", ""))
        self.ui_adb_delay.delete(0, "end"); self.ui_adb_delay.insert(0, c.get("adb_delay", "2.0"))
        
        self.on_method_change()

    def on_save_settings(self):
        ak = self.ui_api_key.get(); asc = self.ui_api_secret.get(); sp = self.ui_sender.get()
        sm = self.send_method_var.get()
        ax = self.ui_adb_x.get(); ay = self.ui_adb_y.get(); ad = self.ui_adb_delay.get()
        
        if save_config(ak, asc, sp, sm, ax, ay, ad):
            messagebox.showinfo("저장 완료", "API 및 발송 설정이 안전하게 저장되었습니다.")
            self.send_mgr.solapi = SolapiService() # 갱신
            self.update_send_mode_label()

    def on_send_click(self):
        content = self.msg_box.get("1.0", "end-1c")
        nums = [n.strip() for n in self.recipients_box.get("1.0", "end-1c").split("\n") if n.strip()]
        use_memo = self.use_memo_var.get()

        if not nums:
            messagebox.showwarning("입력 누락", "수신인 번호를 입력하세요.")
            return
            
        if not use_memo and not content and not self.selected_image_paths:
            messagebox.showwarning("입력 누락", "메시지 내용이나 첨부 이미지를 입력하세요.")
            return

        if self.selected_image_paths:
            send_method = load_config().get("send_method", "SOLAPI")
            if send_method == "ADB":
                confirm_msg = (
                    f"선택한 이미지 {len(self.selected_image_paths)}개를 한 장으로 합성해 ADB MMS 작성 화면에 첨부합니다.\n"
                    "기기와 문자앱에 따라 전송 버튼 좌표가 필요할 수 있습니다.\n계속하시겠습니까?"
                )
            else:
                confirm_msg = f"선택한 이미지 {len(self.selected_image_paths)}개를 MMS로 첨부해 발송하시겠습니까?"
            if not messagebox.askyesno("MMS 발송 확인", confirm_msg):
                return

        # 개별 메시지 준비 (메모 사용 시)
        individual_msgs = None
        if use_memo:
            df = self.db_mgr.get_all_contacts()
            # 전화번호:메모 매핑 생성
            individual_msgs = {str(row['phone']): str(row['memo']) for _, row in df.iterrows() if row.get('memo')}
            
            # 선택된 번호 중 메모가 있는 사람만 필터링 확인
            nums_with_memo = [n for n in nums if n in individual_msgs and individual_msgs[n].strip()]
            if not nums_with_memo:
                messagebox.showerror("오류", "선택된 번호 중 메모가 등록된 연락처가 없습니다.")
                return
            
            if not messagebox.askyesno("확인", f"선택된 {len(nums)}명 중 메모가 있는 {len(nums_with_memo)}명에게 개별 메시지를 발송하시겠습니까?"):
                return
            nums = nums_with_memo

        self.send_action_btn.configure(state="disabled", text="발송 중...")
        
        def run_task():
            recipients = [("수신인", n) for n in nums]
            m_type = self.msg_type_var.get() if self.msg_type_var.get() != "AUTO" else None
            results = self.send_mgr.send_to_recipients(
                recipients,
                content,
                m_type,
                individual_messages=individual_msgs,
                image_paths=self.selected_image_paths
            )
            
            success_count = sum(1 for r in results if r["status"] == "Success")
            self.after(0, lambda: messagebox.showinfo("완료", f"총 {len(results)}건 중 {success_count}건 발송 성공!"))
            self.after(0, lambda: self.send_action_btn.configure(state="normal", text="메시지 전송 시작"))
            self.after(0, self.load_data)

        threading.Thread(target=run_task).start()

    def check_solapi_balance(self):
        def task():
            res = self.send_mgr.solapi.get_balance()
            if "balance" in res:
                self.after(0, lambda: self.balance_lbl.configure(text=f"잔액: {res['balance']}원"))
            else:
                self.after(0, lambda: messagebox.showerror("오류", "잔액 조회 실패. API 설정을 확인하세요."))
        threading.Thread(target=task).start()

    def check_adb_device(self):
        def task():
            self.after(0, lambda: self.adb_status_lbl.configure(text="확인 중..."))
            devs = self.send_mgr.adb.check_device()
            if devs:
                self.after(0, lambda: self.adb_status_lbl.configure(text=f"통신 성공! ({devs[0]})", text_color="#2b8a3e"))
            else:
                self.after(0, lambda: self.adb_status_lbl.configure(text="연결된 기기 없음", text_color="red"))
        threading.Thread(target=task).start()

    def on_excel_import(self):
        file = filedialog.askopenfilename(filetypes=[("Excel Files", "*.xlsx *.csv")])
        if file:
            ok, msg = self.db_mgr.import_from_excel(file)
            messagebox.showinfo("결과", msg)
            self.load_data()

    def on_excel_export(self):
        file = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel Files", "*.xlsx")])
        if file:
            ok, msg = self.db_mgr.export_to_excel(file)
            messagebox.showinfo("결과", msg)

    def show_initial_setup_popup(self):
        if messagebox.askyesno("API 설정 알림", "현재 API 설정이 되어 있지 않습니다.\n설정 화면으로 이동하시겠습니까?"):
            self.select_screen("settings")

    def on_delete_all_contacts(self):
        if not self.db_mgr.get_all_contacts().empty:
            if messagebox.askyesno("전체 삭제 확인", "주소록의 모든 데이터를 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다."):
                self.db_mgr.clear_all_contacts()
                messagebox.showinfo("삭제 완료", "모든 연락처가 삭제되었습니다.")
                self.load_data()
        else:
            messagebox.showinfo("안내", "삭제할 연락처가 없습니다.")

    def on_delete_selected_contacts(self):
        df = self.db_mgr.get_all_contacts()
        if df.empty:
            messagebox.showinfo("안내", "주소록이 비어 있습니다.")
            return
            
        def confirm_delete(phones):
            if not phones: return
            if messagebox.askyesno("선택 삭제 확인", f"선택한 {len(phones)}개의 연락처를 삭제하시겠습니까?"):
                self.db_mgr.delete_contacts_by_phone(phones)
                messagebox.showinfo("삭제 완료", "선택한 연락처가 삭제되었습니다.")
                self.load_data()

        selector = ContactSelector(self, df, confirm_delete)
        selector.title("삭제할 연락처 선택")
        selector.grab_set()

    def on_clear_recipients(self):
        if messagebox.askyesno("목록 비우기", "수신인 목록을 모두 지우시겠습니까?"):
            self.recipients_box.delete("1.0", "end")

    def on_load_contacts(self):
        df = self.db_mgr.get_all_contacts()
        if df.empty:
            messagebox.showinfo("안내", "주소록이 비어 있습니다.")
            return
        
        selector = ContactSelector(self, df, self.populate_recipients)
        selector.grab_set() 

    def populate_recipients(self, phones):
        current = self.recipients_box.get("1.0", "end-1c").strip()
        new_text = "\n".join(phones)
        if current:
            self.recipients_box.insert("end", "\n" + new_text)
        else:
            self.recipients_box.insert("1.0", new_text)

    def dummy_action(self): messagebox.showinfo("안내", "상세 CRUD 디자인은 현재 엑셀 업로드로 대체 중입니다.")

if __name__ == "__main__":
    app = AutoSMSApp()
    app.mainloop()
