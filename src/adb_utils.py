import subprocess
import os
import time

class ADBUtils:
    def __init__(self, adb_path):
        self.adb_path = adb_path

    def run_cmd(self, args):
        cmd = [self.adb_path] + args
        try:
            # Use utf-8 encoding and ignore errors to prevent cp949 decoding issues on Windows
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding='utf-8', errors='ignore')
            return result.stdout.strip() if result.stdout else ""
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            return f"Error: {error_msg}"
        except Exception as e:
            return f"Error: {str(e)}"

    def check_connection(self):
        output = self.run_cmd(["devices"])
        lines = output.splitlines()
        devices = [line for line in lines[1:] if line.strip() and "device" in line]
        return len(devices) > 0

    def send_sms(self, phone_number, message, delay=5, x=None, y=None):
        # Open Google Messages with the number and message
        self.run_cmd([
            "shell", "am", "start", "-a", "android.intent.action.SENDTO",
            "-d", f"sms:{phone_number}",
            "--es", "sms_body", message,
            "com.google.android.apps.messaging"
        ])
        
        # Wait for the app to load and message to populate
        time.sleep(4)
        
        # Tap the specified coordinates
        if x is not None and y is not None:
            self.run_cmd(["shell", "input", "tap", str(x), str(y)])
        
        # Wait before next message to avoid spam detection
        time.sleep(delay)
        return True

    def is_screen_on(self):
        output = self.run_cmd(["shell", "dumpsys", "power"])
        return "mIsPowered=true" in output or "Display Power: state=ON" in output
