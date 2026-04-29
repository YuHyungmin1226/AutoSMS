import os
import threading
import time
import pandas as pd
import customtkinter as ctk
from tkinter import filedialog, messagebox
from adb_setup import setup_adb
from adb_utils import ADBUtils

# UI Settings
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class AutoSMSApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("AutoSMS - Premium Bulk Messenger")
        self.geometry("1100x700")

        # State variables
        self.excel_path = None
        self.df = None
        self.groups = []
        self.adb_utils = None
        self.is_sending = False

        # ADB Setup
        self.init_adb()

        # Layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=300, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.setup_sidebar()

        # Main Content
        self.main_frame = ctk.CTkFrame(self, corner_radius=10)
        self.main_frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        self.setup_main()

    def init_adb(self):
        adb_path = setup_adb()
        if adb_path:
            self.adb_utils = ADBUtils(adb_path)
        else:
            messagebox.showerror("Error", "Failed to setup ADB. Please check your internet connection.")

    def setup_sidebar(self):
        self.sidebar_label = ctk.CTkLabel(self.sidebar, text="AutoSMS Control", font=ctk.CTkFont(size=24, weight="bold"))
        self.sidebar_label.pack(padx=20, pady=30)

        self.load_btn = ctk.CTkButton(self.sidebar, text="엑셀 주소록 불러오기", command=self.load_excel, height=40)
        self.load_btn.pack(padx=20, pady=10, fill="x")

        self.file_label = ctk.CTkLabel(self.sidebar, text="선택된 파일 없음", font=ctk.CTkFont(size=12))
        self.file_label.pack(padx=20, pady=5)

        ctk.CTkLabel(self.sidebar, text="발송 지연 시간 (초)", font=ctk.CTkFont(size=13)).pack(padx=20, pady=(20, 0))
        self.delay_entry = ctk.CTkEntry(self.sidebar, placeholder_text="5")
        self.delay_entry.insert(0, "5")
        self.delay_entry.pack(padx=20, pady=5, fill="x")

        self.status_indicator = ctk.CTkLabel(self.sidebar, text="● ADB 미연결", text_color="red", font=ctk.CTkFont(weight="bold"))
        self.status_indicator.pack(padx=20, pady=20)

        self.check_adb_btn = ctk.CTkButton(self.sidebar, text="연결 확인", command=self.check_connection, fg_color="transparent", border_width=1)
        self.check_adb_btn.pack(padx=20, pady=10, fill="x")

        self.send_btn = ctk.CTkButton(self.sidebar, text="발송 시작", command=self.start_sending, height=50, fg_color="#2ecc71", hover_color="#27ae60")
        self.send_btn.pack(padx=20, pady=30, fill="x", side="bottom")

    def setup_main(self):
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(1, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)

        # 1. Left Column: Contact Management (Groups + Individual)
        self.contact_mgmt_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.contact_mgmt_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.contact_mgmt_frame.grid_columnconfigure(0, weight=1)
        self.contact_mgmt_frame.grid_rowconfigure(1, weight=1)

        # Groups (Top of Left Column)
        self.group_frame = ctk.CTkScrollableFrame(self.contact_mgmt_frame, label_text="그룹 필터", height=150)
        self.group_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=(0, 10))
        self.group_vars = {}

        # Contacts (Bottom of Left Column)
        self.contact_list_frame = ctk.CTkScrollableFrame(self.contact_mgmt_frame, label_text="연락처 선택 (발송 대상)")
        self.contact_list_frame.grid(row=1, column=0, sticky="nsew", padx=5)
        self.contact_vars = []

        # 2. Right Column: Messaging & Logs
        self.msg_log_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.msg_log_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        self.msg_log_frame.grid_columnconfigure(0, weight=1)
        self.msg_log_frame.grid_rowconfigure(1, weight=1)

        # Message Input (Top of Right Column)
        ctk.CTkLabel(self.msg_log_frame, text="공통 메시지", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, sticky="w", padx=5)
        self.msg_text = ctk.CTkTextbox(self.msg_log_frame, height=150)
        self.msg_text.grid(row=1, column=0, pady=5, sticky="nsew", padx=5)

        # Log Box (Bottom of Right Column)
        ctk.CTkLabel(self.msg_log_frame, text="발송 로그", font=ctk.CTkFont(size=14, weight="bold")).grid(row=2, column=0, sticky="w", padx=5, pady=(10, 0))
        self.log_box = ctk.CTkTextbox(self.msg_log_frame, height=300)
        self.log_box.grid(row=3, column=0, pady=5, sticky="nsew", padx=5)
        self.msg_log_frame.grid_rowconfigure(3, weight=2) # Give log box more weight

        self.log("시스템 준비 완료.")

    def log(self, text):
        timestamp = time.strftime("[%H:%M:%S] ")
        self.log_box.insert("end", timestamp + text + "\n")
        self.log_box.see("end")

    def load_excel(self):
        file_path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx *.xls")])
        if not file_path:
            return

        try:
            self.df = pd.read_excel(file_path)
            required_cols = ['이름', '연락처', '메시지', '그룹']
            if not all(col in self.df.columns for col in required_cols):
                messagebox.showerror("Error", f"엑셀 파일에 다음 컬럼이 필요합니다: {', '.join(required_cols)}")
                return

            self.excel_path = file_path
            self.file_label.configure(text=os.path.basename(file_path))
            
            # Refresh Groups
            self.groups = sorted(self.df['그룹'].dropna().unique().tolist())
            for widget in self.group_frame.winfo_children():
                widget.destroy()
            
            self.group_vars = {}
            for group in self.groups:
                var = ctk.BooleanVar(value=True)
                self.group_vars[group] = var
                cb = ctk.CTkCheckBox(self.group_frame, text=group, variable=var, command=self.refresh_contact_list)
                cb.pack(padx=10, pady=5, anchor="w")
            
            self.refresh_contact_list()
            self.log(f"엑셀 로드 완료: {len(self.df)}개의 연락처 발견.")
        except Exception as e:
            messagebox.showerror("Error", f"파일을 읽는 중 오류 발생: {e}")

    def refresh_contact_list(self):
        # Filter contacts based on selected groups
        selected_groups = [g for g, v in self.group_vars.items() if v.get()]
        
        for widget in self.contact_list_frame.winfo_children():
            widget.destroy()
        
        self.contact_vars = []
        
        filtered_df = self.df[self.df['그룹'].isin(selected_groups)]
        
        for idx, row in filtered_df.iterrows():
            var = ctk.BooleanVar(value=True)
            self.contact_vars.append((idx, var))
            
            name = str(row['이름'])
            number = str(row['연락처'])
            group = str(row['그룹'])
            
            # Contact row container
            contact_row = ctk.CTkFrame(self.contact_list_frame, fg_color="transparent")
            contact_row.pack(fill="x", padx=5, pady=2)
            
            cb = ctk.CTkCheckBox(contact_row, text=f"{name} ({number}) [{group}]", variable=var)
            cb.pack(side="left", padx=5)

    def check_connection(self):
        if self.adb_utils and self.adb_utils.check_connection():
            self.status_indicator.configure(text="● ADB 연결됨", text_color="green")
            self.log("안드로이드 기기 연결 확인됨.")
            return True
        else:
            self.status_indicator.configure(text="● ADB 미연결", text_color="red")
            self.log("연결된 기기를 찾을 수 없습니다. USB 디버깅을 확인하세요.")
            return False

    def start_sending(self):
        if self.is_sending:
            self.is_sending = False
            self.send_btn.configure(text="발송 시작", fg_color="#2ecc71")
            self.log("발송 중지됨.")
            return

        if self.df is None:
            messagebox.showwarning("Warning", "엑셀 파일을 먼저 불러오세요.")
            return

        if not self.check_connection():
            messagebox.showwarning("Warning", "휴대폰을 연결해 주세요.")
            return

        # Only send to contacts checked in the list
        checked_indices = [idx for idx, var in self.contact_vars if var.get()]
        if not checked_indices:
            messagebox.showwarning("Warning", "발송할 연락처를 하나 이상 선택하세요.")
            return

        default_msg = self.msg_text.get("1.0", "end-1c").strip()
        delay = int(self.delay_entry.get() if self.delay_entry.get().isdigit() else 5)

        self.is_sending = True
        self.send_btn.configure(text="중지", fg_color="#e74c3c")
        
        threading.Thread(target=self.send_loop, args=(checked_indices, default_msg, delay), daemon=True).start()

    def send_loop(self, checked_indices, default_msg, delay):
        targets = self.df.loc[checked_indices]
        total = len(targets)
        self.log(f"총 {total}명에게 발송을 시작합니다.")

        for i, (idx, row) in enumerate(targets.iterrows()):
            if not self.is_sending:
                break

            number = str(row['연락처']).replace("-", "").strip()
            name = str(row['이름']).strip()
            
            # Handle message selection
            msg = row['메시지']
            if pd.isna(msg) or str(msg).strip() == "":
                msg = default_msg
            
            if not msg:
                self.log(f"[{i+1}/{total}] {name}({number}): 메시지가 없어 건너뜀.")
                continue

            self.log(f"[{i+1}/{total}] {name}({number})에게 전송 중...")
            success = self.adb_utils.send_sms(number, msg, delay)
            
            if not success:
                self.log(f"!! {name}({number}) 전송 실패")
        
        self.is_sending = False
        self.send_btn.configure(text="발송 시작", fg_color="#2ecc71")
        self.log("모든 발송 작업이 완료되었습니다.")
        messagebox.showinfo("Done", "발송이 완료되었습니다.")

if __name__ == "__main__":
    app = AutoSMSApp()
    app.mainloop()
