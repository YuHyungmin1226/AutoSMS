import json
import os

CONFIG_FILE = "config.json"

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_config(api_key, api_secret, sender_phone, send_method="SOLAPI", adb_click_x="", adb_click_y="", adb_delay="2.0"):
    config = {
        "api_key": api_key,
        "api_secret": api_secret,
        "sender_phone": sender_phone,
        "send_method": send_method,
        "adb_click_x": adb_click_x,
        "adb_click_y": adb_click_y,
        "adb_delay": adb_delay
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
    return True

def is_config_valid():
    config = load_config()
    # If method is ADB, we might only need ADB connected, but for simplicity let's just make valid if api_key exists for solapi, or sending_method is ADB
    m = config.get("send_method", "SOLAPI")
    if m == "SOLAPI":
        return bool(config.get("api_key") and config.get("api_secret") and config.get("sender_phone"))
    return True # ADB requires fewer explicit text configs initially
