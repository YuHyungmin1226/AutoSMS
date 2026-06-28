from solapi_service import SolapiService # type: ignore
from adb_service import AdbService
from config_manager import load_config
from utils import determine_msg_type # type: ignore
from mms_image_utils import prepare_mms_image
import sqlite3
import os

DB_PATH = "auto_sms.db"

class SendingManager:
    def __init__(self, solapi_service=None, adb_service=None):
        self.solapi = solapi_service or SolapiService()
        self.adb = adb_service or AdbService()
        self.db_path = DB_PATH

    def send_to_recipients(self, recipients, content, manual_type=None, individual_messages=None, image_paths=None):
        """
        recipients: list of (name, phone)
        content: common message content
        manual_type: SMS, LMS, MMS or None for AUTO
        individual_messages: dict of {phone: message_content}
        image_paths: list of image paths. Multiple images are merged into one MMS-safe image.
        """
        config = load_config()
        send_method = config.get("send_method", "SOLAPI")
        adb_click_x = config.get("adb_click_x", "")
        adb_click_y = config.get("adb_click_y", "")
        adb_delay = config.get("adb_delay", "2.0")
        
        results = []
        image_paths = image_paths or []
        prepared_image_path = None
        image_id = None

        if image_paths:
            try:
                prepared_image_path = prepare_mms_image(image_paths)
                if send_method != "ADB":
                    upload_res = self.solapi.upload_mms_image(prepared_image_path)
                    image_id = self._extract_image_id(upload_res)
                    if not image_id:
                        raise ValueError(str(upload_res))
            except Exception as e:
                return [{
                    "phone": phone,
                    "status": "Fail",
                    "msg": f"MMS 이미지 준비 실패: {e}"
                } for _, phone in recipients]
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            for name, phone in recipients:
                # 개별 메시지가 있으면 사용, 없으면 공통 메시지 사용
                current_content = content
                if individual_messages and phone in individual_messages:
                    current_content = individual_messages[phone]

                if not current_content and not image_id and not prepared_image_path:
                    continue # 내용과 첨부가 모두 없으면 건너뜀

                msg_type = "MMS" if image_id or prepared_image_path else determine_msg_type(current_content, manual_type)

                if send_method == "ADB":
                    api_res = self.adb.send_message(
                        phone,
                        current_content,
                        adb_click_x,
                        adb_click_y,
                        float(adb_delay),
                        image_path=prepared_image_path
                    )
                    status = api_res["status"]
                    result_msg = api_res["msg"]
                else:
                    # SOLAPI API 호출
                    api_res = self.solapi.send_message(phone, current_content, msg_type, image_id=image_id)
                    success = "messageId" in api_res or "groupId" in api_res
                    status = "Success" if success else "Fail"
                    result_msg = str(api_res.get("errorCode", api_res.get("errorMessage", api_res.get("error", "OK"))))

                # DB 로그 기록
                log_content = current_content
                if image_paths:
                    log_content = f"{current_content}\n[첨부 이미지 {len(image_paths)}개]"

                cursor.execute('''
                    INSERT INTO sending_logs (recipient_phone, content, msg_type, status, result_msg)
                    VALUES (?, ?, ?, ?, ?)
                ''', (phone, log_content, msg_type, status, result_msg))
                
                results.append({
                    "phone": phone,
                    "status": status,
                    "msg": result_msg
                })

            conn.commit()
        finally:
            conn.close()
            if prepared_image_path and os.path.exists(prepared_image_path):
                os.remove(prepared_image_path)
        return results

    def _extract_image_id(self, response):
        if not isinstance(response, dict):
            return None
        for key in ("fileId", "imageId", "id"):
            if response.get(key):
                return response[key]
        if isinstance(response.get("file"), dict):
            return self._extract_image_id(response["file"])
        return None

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
