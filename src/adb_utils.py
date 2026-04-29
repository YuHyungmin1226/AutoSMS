import subprocess
import os
import time

class ADBUtils:
    def __init__(self, adb_path):
        self.adb_path = adb_path

    def run_cmd(self, args):
        cmd = [self.adb_path] + args
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            return f"Error: {e.stderr}"

    def check_connection(self):
        output = self.run_cmd(["devices"])
        lines = output.splitlines()
        devices = [line for line in lines[1:] if line.strip() and "device" in line]
        return len(devices) > 0

    def send_sms(self, phone_number, message, delay=5):
        # Open Google Messages with the number and message
        # Package for Google Messages: com.google.android.apps.messaging
        self.run_cmd([
            "shell", "am", "start", "-a", "android.intent.action.SENDTO",
            "-d", f"sms:{phone_number}",
            "--es", "sms_body", message,
            "com.google.android.apps.messaging"
        ])
        
        # Wait for the app to load
        time.sleep(2)
        
        # Simulating send button click
        # This is the tricky part. For Google Messages, usually focus is on the send button or text field.
        # Common sequence: Right arrow (focus send) -> Enter
        self.run_cmd(["shell", "input", "keyevent", "22"]) # Right
        time.sleep(0.5)
        self.run_cmd(["shell", "input", "keyevent", "66"]) # Enter
        
        # Wait before next message to avoid spam detection
        time.sleep(delay)
        return True

    def is_screen_on(self):
        output = self.run_cmd(["shell", "dumpsys", "power"])
        return "mIsPowered=true" in output or "Display Power: state=ON" in output
