import os
import zipfile
import urllib.request
import shutil

ADB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'adb')
ADB_ZIP_URL = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
ADB_ZIP_PATH = os.path.join(ADB_DIR, "platform-tools.zip")
ADB_EXE_PATH = os.path.join(ADB_DIR, "platform-tools", "adb.exe")

def setup_adb():
    if not os.path.exists(ADB_DIR):
        os.makedirs(ADB_DIR)

    if os.path.exists(ADB_EXE_PATH):
        print(f"ADB already exists at {ADB_EXE_PATH}")
        return ADB_EXE_PATH

    print("Downloading Portable ADB...")
    try:
        urllib.request.urlretrieve(ADB_ZIP_URL, ADB_ZIP_PATH)
        print("Extracting ADB...")
        with zipfile.ZipFile(ADB_ZIP_PATH, 'r') as zip_ref:
            zip_ref.extractall(ADB_DIR)
        
        os.remove(ADB_ZIP_PATH)
        print("ADB Setup Complete.")
        return ADB_EXE_PATH
    except Exception as e:
        print(f"Error setting up ADB: {e}")
        return None

if __name__ == "__main__":
    setup_adb()
