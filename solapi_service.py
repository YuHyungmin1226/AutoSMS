import requests # type: ignore
import json
import time
import datetime
import uuid
import hmac
import hashlib
import base64
import os
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

    def upload_mms_image(self, image_path):
        url = f"{self.base_url}/storage/v1/files"
        with open(image_path, "rb") as f:
            encoded_file = base64.b64encode(f.read()).decode("ascii")

        data = {
            "file": encoded_file,
            "type": "MMS",
            "name": os.path.basename(image_path)
        }

        try:
            response = requests.post(url, headers=self.get_header(), json=data)
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def send_message(self, recipient_phone, content, msg_type="SMS", image_id=None):
        url = f"{self.base_url}/messages/v4/send"
        
        message = {
            "to": recipient_phone.replace("-", ""),
            "from": self.sender_phone.replace("-", ""),
            "text": content,
            "type": msg_type.upper()
        }
        if image_id:
            message["type"] = "MMS"
            message["imageId"] = image_id

        data = {"message": message}

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
