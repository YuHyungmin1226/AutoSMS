from solapi_service import SolapiService # type: ignore
from adb_service import AdbService
from config_manager import load_config
from utils import determine_msg_type # type: ignore
import sqlite3

DB_PATH = "auto_sms.db"

class SendingManager:
    def __init__(self, solapi_service=None, adb_service=None):
        self.solapi = solapi_service or SolapiService()
        self.adb = adb_service or AdbService()
        self.db_path = DB_PATH

    def send_to_recipients(self, recipients, content, manual_type=None, individual_messages=None):
        """
        recipients: list of (name, phone)
        content: common message content
        manual_type: SMS, LMS, MMS or None for AUTO
        individual_messages: dict of {phone: message_content}
        """
        config = load_config()
        send_method = config.get("send_method", "SOLAPI")
        adb_click_x = config.get("adb_click_x", "")
        adb_click_y = config.get("adb_click_y", "")
        adb_delay = config.get("adb_delay", "2.0")
        
        results = []
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for name, phone in recipients:
            # 개별 메시지가 있으면 사용, 없으면 공통 메시지 사용
            current_content = content
            if individual_messages and phone in individual_messages:
                current_content = individual_messages[phone]
                
            if not current_content:
                continue # 내용이 없으면 건너뜀

            msg_type = determine_msg_type(current_content, manual_type)
            
            if send_method == "ADB":
                api_res = self.adb.send_message(phone, current_content, adb_click_x, adb_click_y, float(adb_delay))
                status = api_res["status"]
                result_msg = api_res["msg"]
            else:
                # SOLAPI API 호출
                api_res = self.solapi.send_message(phone, current_content, msg_type)
                success = "messageId" in api_res or "groupId" in api_res
                status = "Success" if success else "Fail"
                result_msg = str(api_res.get("errorCode", api_res.get("errorMessage", "OK")))
            
            # DB 로그 기록
            cursor.execute('''
                INSERT INTO sending_logs (recipient_phone, content, msg_type, status, result_msg)
                VALUES (?, ?, ?, ?, ?)
            ''', (phone, current_content, msg_type, status, result_msg))
            
            results.append({
                "phone": phone,
                "status": status,
                "msg": result_msg
            })
            
        conn.commit()
        conn.close()
        return results

    def get_logs(self):
        """
        발송 로그를 가져옵니다.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sending_logs ORDER BY send_time DESC")
        logs = cursor.fetchall()
        conn.close()
        return logs

if __name__ == "__main__":
    mgr = SendingManager()
    res = mgr.send_to_recipients([("테스터", "01012345678")], "테스트 메시지입니다.")
    print(res)
