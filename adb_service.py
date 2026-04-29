import os
import subprocess
import urllib.request
import zipfile
import time

ADB_URL = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
ADB_DIR = os.path.join(os.getcwd(), "adb_tools")
ADB_EXE = os.path.join(ADB_DIR, "platform-tools", "adb.exe")

class AdbService:
    def __init__(self):
        self._ensure_adb_installed()

    def _ensure_adb_installed(self):
        if not os.path.exists(ADB_EXE):
            print("Downloading ADB Platform Tools...")
            os.makedirs(ADB_DIR, exist_ok=True)
            zip_path = os.path.join(ADB_DIR, "platform-tools.zip")
            urllib.request.urlretrieve(ADB_URL, zip_path)
            print("Extracting ADB...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(ADB_DIR)
            os.remove(zip_path)
            print("ADB Setup Complete.")

    def _run_adb_cmd(self, args):
        cmd = [ADB_EXE] + args
        try:
            # CREATE_NO_WINDOW = 0x08000000 to prevent cmd popup on Windows
            result = subprocess.run(cmd, capture_output=True, text=True, creationflags=0x08000000)
            return result.stdout.strip()
        except Exception as e:
            return f"Error: {str(e)}"

    def check_device(self):
        output = self._run_adb_cmd(["devices"])
        lines = output.split('\n')
        devices = []
        for line in lines[1:]:
            parts = line.strip().split()
            if len(parts) >= 2 and parts[1] == 'device':
                devices.append(parts[0])
        return devices

    def send_message(self, phone, content, click_x=None, click_y=None, delay=2.0):
        try:
            # 1. 메시지 작성 앱 실행 인텐트 호출 (Activity 스택 찌꺼기 제거 플래그 포함)
            # 전화번호 텍스트 내용 이스케이프 (작은따옴표로 감싸기)
            escaped_content = content.replace("'", "\\'") 
            # -f 0x14000000: FLAG_ACTIVITY_NEW_TASK | FLAG_ACTIVITY_CLEAR_TOP (기존 앱 화면 초기화)
            cmd_intent = ["shell", "am", "start", "-a", "android.intent.action.SENDTO", "-d", f"sms:{phone}", "-f", "0x14000000", "--es", "sms_body", f"'{escaped_content}'"]
            self._run_adb_cmd(cmd_intent)
            
            # 2. 문자 앱 로딩 및 텍스트 채워지는 시간 대기
            time.sleep(float(delay))
            
            # 3. 전송 버튼 좌표 터치 (설정된 경우)
            if click_x and click_y:
                self._run_adb_cmd(["shell", "input", "tap", str(int(click_x)), str(int(click_y))])
                time.sleep(1.0) # 메시지 보내는 모션/로딩 대기
            
            # 4. 앱 초기화 (홈 화면 이동 후 백그라운드 발송 대기)
            # 홈 키(3번)를 눌러서 앱을 화면에서만 내림 (백그라운드 통신은 유지됨)
            self._run_adb_cmd(["shell", "input", "keyevent", "3"])
            
            # 통신사가 기지국으로 문자를 안전하게 전송할 수 있도록 다음 발송 전까지 약간의 여유 유지
            # 주의: 여기서 am force-stop을 하면 전송 도중 앱이 죽어서 발송 실패 처리가 됨
            time.sleep(1.5)
            
            # ADB 방식은 실제 전송 성공 여부를 파악하기 어려우므로 항상 Success로 반환함
            return {"status": "Success", "msg": "ADB Intent & Hook Success"}
            
        except Exception as e:
            return {"status": "Fail", "msg": str(e)}

if __name__ == "__main__":
    service = AdbService()
    print("Devices:", service.check_device())
