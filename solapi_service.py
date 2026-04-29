import requests # type: ignore
import json
import time
import datetime
import uuid
import hmac
import hashlib
from config_manager import load_config # type: ignore

class SolapiService:
    def __init__(self, api_key=None, api_secret=None, sender_phone=None):
        config = load_config()
        self.api_key = api_key or config.get("api_key") or ""
        self.api_secret = api_secret or config.get("api_secret") or ""
        self.sender_phone = sender_phone or config.get("sender_phone") or ""
        self.base_url = "https://api.solapi.com"

    def get_header(self):
        now = datetime.datetime.now().isoformat() + "Z"
        salt = str(uuid.uuid4().hex)
        combined = now + salt
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            combined.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        
        return {
            "Authorization": f"HMAC-SHA256 apiKey={self.api_key}, date={now}, salt={salt}, signature={signature}",
            "Content-Type": "application/json; charset=utf-8"
        }

    def send_message(self, recipient_phone, content, msg_type="SMS"):
        url = f"{self.base_url}/messages/v4/send"
        
        data = {
            "message": {
                "to": recipient_phone.replace("-", ""),
                "from": self.sender_phone.replace("-", ""),
                "text": content,
                "type": msg_type.upper()
            }
        }

        try:
            response = requests.post(url, headers=self.get_header(), json=data)
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def get_balance(self):
        url = f"{self.base_url}/cash/v1/balance"
        try:
            response = requests.get(url, headers=self.get_header())
            return response.json()
        except Exception as e:
            return {"error": str(e)}
