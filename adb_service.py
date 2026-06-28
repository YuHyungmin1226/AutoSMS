import os
import subprocess
import urllib.request
import zipfile
import time
import re
import xml.etree.ElementTree as ET

ADB_URL = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
ADB_DIR = os.path.join(os.getcwd(), "adb_tools")
ADB_EXE = os.path.join(ADB_DIR, "platform-tools", "adb.exe")
MMS_REMOTE_DIR = "/sdcard/Pictures/AutoSMS"
UI_DUMP_REMOTE_FILE = "/sdcard/window_dump.xml"
GOOGLE_MESSAGES_PACKAGE = "com.google.android.apps.messaging"
GOOGLE_MESSAGES_SHARE_ACTIVITY = "com.google.android.apps.messaging/.ui.conversationlist.ShareIntentActivity"


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

    def _run_adb_cmd_result(self, args):
        cmd = [ADB_EXE] + args
        creationflags = 0x08000000 if os.name == "nt" else 0
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            creationflags=creationflags
        )

    def _run_adb_cmd(self, args):
        try:
            result = self._run_adb_cmd_result(args)
            return (result.stdout or result.stderr).strip()
        except Exception as e:
            return f"Error: {str(e)}"

    def _open_text_message_intent(self, phone, content):
        # Preserve the existing SMS/SENDTO behavior for compatibility and fallback.
        escaped_content = content.replace("'", "\\'")
        cmd_intent = [
            "shell", "am", "start",
            "-a", "android.intent.action.SENDTO",
            "-d", f"sms:{phone}",
            "-f", "0x14000000",
            "--es", "sms_body", f"'{escaped_content}'",
        ]
        return self._run_adb_cmd_result(cmd_intent)

    def _push_mms_image(self, image_path):
        if not os.path.isfile(image_path):
            raise FileNotFoundError(f"MMS image not found: {image_path}")

        remote_file = f"{MMS_REMOTE_DIR}/autosms_mms_{int(time.time() * 1000)}.jpg"
        mkdir_result = self._run_adb_cmd_result(["shell", "mkdir", "-p", MMS_REMOTE_DIR])
        if mkdir_result.returncode != 0:
            msg = (mkdir_result.stderr or mkdir_result.stdout).strip()
            raise RuntimeError(msg or "Failed to create remote MMS directory")

        push_result = self._run_adb_cmd_result(["push", image_path, remote_file])
        if push_result.returncode != 0:
            msg = (push_result.stderr or push_result.stdout).strip()
            raise RuntimeError(msg or "Failed to push MMS image")

        # Best effort: some devices need a media scan before messaging apps can read the file URI.
        self._run_adb_cmd([
            "shell", "am", "broadcast",
            "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
            "-d", f"file://{remote_file}",
        ])
        time.sleep(1.0)
        return self._resolve_media_content_uri(remote_file) or f"file://{remote_file}"

    def _resolve_media_content_uri(self, remote_file):
        display_name = os.path.basename(remote_file)
        expected_suffix = remote_file.replace("/sdcard/", "/storage/emulated/0/")
        query_result = self._run_adb_cmd_result([
            "shell", "content", "query",
            "--uri", "content://media/external/images/media",
            "--projection", "_id:_display_name:_data:relative_path:mime_type",
        ])
        if query_result.returncode != 0:
            return None

        for line in (query_result.stdout or "").splitlines():
            if display_name not in line:
                continue
            if "AutoSMS" not in line and expected_suffix not in line:
                continue
            match = re.search(r"_id=(\d+)", line)
            if match:
                return f"content://media/external/images/media/{match.group(1)}"
        return None

    def _build_mms_intents(self, phone, content, stream_uri):
        return [
            [
                "shell", "am", "start",
                "-n", GOOGLE_MESSAGES_SHARE_ACTIVITY,
                "-a", "android.intent.action.SEND",
                "-t", "image/jpeg",
                "--eu", "android.intent.extra.STREAM", stream_uri,
                "--es", "android.intent.extra.TEXT", content,
                "--es", "sms_body", content,
                "--es", "address", phone,
                "--es", "phone", phone,
                "--es", "recipient", phone,
                "--grant-read-uri-permission",
                "-f", "0x14000000",
            ],
            [
                "shell", "am", "start",
                "-p", GOOGLE_MESSAGES_PACKAGE,
                "-a", "android.intent.action.SEND",
                "-t", "image/jpeg",
                "--eu", "android.intent.extra.STREAM", stream_uri,
                "--es", "android.intent.extra.TEXT", content,
                "--es", "sms_body", content,
                "--es", "address", phone,
                "--es", "phone", phone,
                "--es", "recipient", phone,
                "--grant-read-uri-permission",
                "-f", "0x14000000",
            ],
            [
                "shell", "am", "start",
                "-a", "android.intent.action.SENDTO",
                "-d", f"mmsto:{phone}",
                "-t", "image/jpeg",
                "--eu", "android.intent.extra.STREAM", stream_uri,
                "--es", "sms_body", content,
                "--es", "address", phone,
                "--grant-read-uri-permission",
                "-f", "0x14000000",
            ],
            [
                "shell", "am", "start",
                "-a", "android.intent.action.SEND",
                "-t", "image/jpeg",
                "--eu", "android.intent.extra.STREAM", stream_uri,
                "--es", "sms_body", content,
                "--es", "address", phone,
                "--grant-read-uri-permission",
                "-f", "0x14000000",
            ],
        ]

    def _open_mms_image_intent(self, phone, content, image_path):
        stream_uri = self._push_mms_image(image_path)
        last_result = None
        for cmd_intent in self._build_mms_intents(phone, content, stream_uri):
            last_result = self._run_adb_cmd_result(cmd_intent)
            if last_result.returncode == 0:
                return last_result
        return last_result

    def _select_multishare_recipient(self, phone, timeout=8.0):
        deadline = time.time() + timeout
        normalized_phone = re.sub(r"\D", "", phone)
        while time.time() < deadline:
            xml_text = self._dump_current_ui()
            if not xml_text:
                time.sleep(0.5)
                continue
            if "수신자 선택" not in xml_text and "multi_share_list_" not in xml_text:
                return True

            if "선택됨" in xml_text:
                next_bounds = self._find_text_or_desc_bounds(xml_text, ("다음", "next"))
                if next_bounds:
                    x = (next_bounds[0] + next_bounds[2]) // 2
                    y = (next_bounds[1] + next_bounds[3]) // 2
                    self._run_adb_cmd_result(["shell", "input", "tap", str(x), str(y)])
                    time.sleep(1.5)
                    return True

            target_bounds = self._find_multishare_recipient_bounds(xml_text, normalized_phone)
            if not target_bounds:
                self._open_multishare_search(xml_text)
                self._run_adb_cmd_result(["shell", "input", "text", normalized_phone])
                time.sleep(1.0)
                xml_text = self._dump_current_ui() or ""
                target_bounds = self._find_multishare_recipient_bounds(xml_text, normalized_phone)

            if target_bounds:
                x = (target_bounds[0] + target_bounds[2]) // 2
                y = (target_bounds[1] + target_bounds[3]) // 2
                self._run_adb_cmd_result(["shell", "input", "tap", str(x), str(y)])
                time.sleep(0.8)
                xml_text = self._dump_current_ui() or ""
                next_bounds = self._find_text_or_desc_bounds(xml_text, ("다음", "next"))
                if next_bounds:
                    x = (next_bounds[0] + next_bounds[2]) // 2
                    y = (next_bounds[1] + next_bounds[3]) // 2
                    self._run_adb_cmd_result(["shell", "input", "tap", str(x), str(y)])
                    time.sleep(1.5)
                    return True

            time.sleep(0.5)
        return False

    def _dump_current_ui(self):
        dump_result = self._run_adb_cmd_result(["shell", "uiautomator", "dump", UI_DUMP_REMOTE_FILE])
        if dump_result.returncode != 0:
            return None
        xml_result = self._run_adb_cmd_result(["exec-out", "cat", UI_DUMP_REMOTE_FILE])
        if xml_result.returncode != 0 or not xml_result.stdout:
            return None
        return xml_result.stdout

    def _open_multishare_search(self, xml_text):
        bounds = self._find_text_or_desc_bounds(xml_text, ("검색", "search"))
        if not bounds:
            return False
        x = (bounds[0] + bounds[2]) // 2
        y = (bounds[1] + bounds[3]) // 2
        result = self._run_adb_cmd_result(["shell", "input", "tap", str(x), str(y)])
        time.sleep(0.5)
        return result.returncode == 0

    def _find_multishare_recipient_bounds(self, xml_text, normalized_phone):
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return None

        best = None
        for node in root.iter("node"):
            bounds = self._parse_bounds(node.attrib.get("bounds", ""))
            if not bounds:
                continue
            text = node.attrib.get("text") or ""
            desc = node.attrib.get("content-desc") or ""
            resource_id = node.attrib.get("resource-id") or ""
            haystack = " ".join([text, desc, resource_id])
            normalized = re.sub(r"\D", "", haystack)
            if normalized_phone and normalized_phone in normalized:
                return bounds
            if "유형민" in haystack:
                best = bounds
        return best

    def _tap_send_button_from_ui(self, timeout=8.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            xml_text = self._dump_current_ui()
            if not xml_text:
                time.sleep(0.5)
                continue

            bounds = self._find_send_button_bounds(xml_text)
            if bounds:
                x = (bounds[0] + bounds[2]) // 2
                y = (bounds[1] + bounds[3]) // 2
                tap_result = self._run_adb_cmd_result(["shell", "input", "tap", str(x), str(y)])
                return tap_result.returncode == 0

            time.sleep(0.5)
        return False

    def _find_send_button_bounds(self, xml_text):
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return None

        candidates = []
        for node in root.iter("node"):
            package = (node.attrib.get("package") or "").strip()
            text = (node.attrib.get("text") or "").strip().lower()
            desc = (node.attrib.get("content-desc") or "").strip().lower()
            resource_id = (node.attrib.get("resource-id") or "").strip().lower()
            class_name = (node.attrib.get("class") or "").strip().lower()
            clickable = node.attrib.get("clickable") == "true"
            enabled = node.attrib.get("enabled") == "true"
            bounds = self._parse_bounds(node.attrib.get("bounds", ""))
            if not bounds:
                continue
            if package and package not in (GOOGLE_MESSAGES_PACKAGE, "com.android.mms"):
                continue
            if not enabled:
                continue

            haystack = " ".join([text, desc, resource_id])
            score = 0
            if resource_id == "compose:draft:send":
                score += 20
            if any(keyword in haystack for keyword in ("send", "보내기", "전송")):
                score += 7
            if any(keyword in resource_id for keyword in ("send", "compose_send", "message_send", "send_message", "compose:draft:send")):
                score += 4
            if clickable:
                score += 2
            if "button" in class_name or "imagebutton" in class_name:
                score += 1
            if bounds[0] > 600 and bounds[1] > 1200:
                score += 1

            if score >= 5:
                candidates.append((score, bounds))

        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    def _tap_bottom_right_send_area(self):
        size_result = self._run_adb_cmd_result(["shell", "wm", "size"])
        match = re.search(r"Physical size:\s*(\d+)x(\d+)", size_result.stdout or "")
        if match:
            width, height = (int(value) for value in match.groups())
        else:
            width, height = 1080, 2246

        candidates = [
            (int(width * 0.91), int(height * 0.90)),
            (int(width * 0.91), int(height * 0.88)),
            (int(width * 0.94), int(height * 0.88)),
        ]
        for x, y in candidates:
            tap_result = self._run_adb_cmd_result(["shell", "input", "tap", str(x), str(y)])
            time.sleep(0.35)
            if tap_result.returncode == 0:
                return True
        return False

    def _find_text_or_desc_bounds(self, xml_text, keywords):
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return None
        lowered_keywords = tuple(keyword.lower() for keyword in keywords)
        for node in root.iter("node"):
            text = (node.attrib.get("text") or "").strip().lower()
            desc = (node.attrib.get("content-desc") or "").strip().lower()
            bounds = self._parse_bounds(node.attrib.get("bounds", ""))
            if bounds and any(keyword in text or keyword in desc for keyword in lowered_keywords):
                return bounds
        return None

    def _parse_bounds(self, bounds_text):
        match = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds_text)
        if not match:
            return None
        return tuple(int(value) for value in match.groups())

    def check_device(self):
        output = self._run_adb_cmd(["devices"])
        lines = output.split('\n')
        devices = []
        for line in lines[1:]:
            parts = line.strip().split()
            if len(parts) >= 2 and parts[1] == 'device':
                devices.append(parts[0])
        return devices

    def send_message(self, phone, content, click_x=None, click_y=None, delay=2.0, image_path=None):
        try:
            used_mms_intent = bool(image_path)
            if image_path:
                try:
                    intent_result = self._open_mms_image_intent(phone, content, image_path)
                    if intent_result.returncode != 0:
                        used_mms_intent = False
                        self._open_text_message_intent(phone, content)
                    elif not self._select_multishare_recipient(phone):
                        return {
                            "status": "Fail",
                            "msg": "Google Messages 수신자 선택 화면에서 대상 연락처를 자동 선택하지 못했습니다."
                        }
                except Exception:
                    used_mms_intent = False
                    self._open_text_message_intent(phone, content)
            else:
                self._open_text_message_intent(phone, content)

            time.sleep(float(delay))

            sent_by_tap = False
            if click_x and click_y:
                self._run_adb_cmd(["shell", "input", "tap", str(int(click_x)), str(int(click_y))])
                time.sleep(1.0)
                sent_by_tap = True
            else:
                sent_by_tap = self._tap_send_button_from_ui()
                time.sleep(1.0)

            if not sent_by_tap:
                return {
                    "status": "Fail",
                    "msg": "ADB compose opened, but send button was not found automatically. 화면을 유지했습니다."
                }

            self._run_adb_cmd(["shell", "input", "keyevent", "3"])
            time.sleep(1.5)

            msg = "ADB MMS Intent & Auto Send Success" if used_mms_intent else "ADB SMS Intent & Auto Send Success"
            return {"status": "Success", "msg": msg}

        except Exception as e:
            return {"status": "Fail", "msg": str(e)}


if __name__ == "__main__":
    service = AdbService()
    print("Devices:", service.check_device())
