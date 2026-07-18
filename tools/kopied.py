import os
import time
import shutil
import threading
from datetime import datetime
import win32clipboard
from PIL import ImageGrab, Image
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Configuration
SCREENCLIP_PATH = os.path.expandvars(r"%LOCALAPPDATA%\Packages\MicrosoftWindows.Client.Core_cw5n1h2txyewy\TempState\ScreenClip")
TARGET_BASE = r"C:\Kopied"
LOG_FILE = os.path.join(TARGET_BASE, "kopied.log")
SCREENSHOTS_DIR = os.path.join(TARGET_BASE, "Screenshots")
CLIPBOARD_TEXT_DIR = os.path.join(TARGET_BASE, "Clipboard", "Text")
CLIPBOARD_IMAGES_DIR = os.path.join(TARGET_BASE, "Clipboard", "Images")

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{ts}] {msg}"
    print(formatted)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except: pass

def ensure_dirs():
    for d in [SCREENSHOTS_DIR, CLIPBOARD_TEXT_DIR, CLIPBOARD_IMAGES_DIR]:
        if not os.path.exists(d):
            os.makedirs(d, exist_ok=True)

class ScreenshotHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith(('.png', '.jpg', '.jpeg')):
            self._sync_file(event.src_path)

    def _sync_file(self, src_path):
        time.sleep(0.5) # Wait for file write to complete
        filename = os.path.basename(src_path)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        new_name = f"ss_{timestamp}_{filename}"
        target_path = os.path.join(SCREENSHOTS_DIR, new_name)
        try:
            if os.path.exists(src_path):
                shutil.copy2(src_path, target_path)
                log(f"Synced screenshot: {new_name}")
        except Exception as e:
            log(f"Error syncing {filename}: {e}")

def sync_existing_screenshots():
    if not os.path.exists(SCREENCLIP_PATH): return
    for f in os.listdir(SCREENCLIP_PATH):
        if f.lower().endswith(('.png', '.jpg', '.jpeg')):
            full_path = os.path.join(SCREENCLIP_PATH, f)
            # Only sync if not already in target (simple check by filename)
            # We add timestamp so it's likely unique
            handler = ScreenshotHandler()
            handler._sync_file(full_path)

def clipboard_monitor():
    last_seq = 0
    while True:
        try:
            current_seq = win32clipboard.GetClipboardSequenceNumber()
            if current_seq != last_seq:
                last_seq = current_seq
                process_clipboard()
        except Exception:
            pass
        time.sleep(0.5)

def process_clipboard():
    try:
        win32clipboard.OpenClipboard()
        # CF_UNICODETEXT is for text
        if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
            data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
            save_text(data)
        # CF_DIB is for images
        elif win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_DIB):
            win32clipboard.CloseClipboard()
            save_image()
        else:
            win32clipboard.CloseClipboard()
    except Exception as e:
        try: win32clipboard.CloseClipboard()
        except: pass

def save_text(text):
    if not text or not text.strip(): return
    
    # Dedup check - don't save if same as last saved (optional but good)
    # For now, let's just save
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"txt_{timestamp}.txt"
    path = os.path.join(CLIPBOARD_TEXT_DIR, filename)
    
    # Don't save if it's the exact same as latest file content
    # (Avoids spamming files if clipboard is refreshed by OS)
    try:
        files = sorted(os.listdir(CLIPBOARD_TEXT_DIR))
        if files:
            last_file = os.path.join(CLIPBOARD_TEXT_DIR, files[-1])
            with open(last_file, 'r', encoding='utf-8', errors='ignore') as f:
                if f.read() == text:
                    return
    except: pass

    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    log(f"Saved clipboard text: {filename}")

def save_image():
    try:
        img = ImageGrab.grabclipboard()
        if isinstance(img, Image.Image):
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"img_{timestamp}.png"
            path = os.path.join(CLIPBOARD_IMAGES_DIR, filename)
            img.save(path)
            log(f"Saved clipboard image: {filename}")
    except Exception as e:
        log(f"Error saving image: {e}")

def run_service():
    ensure_dirs()
    log(f"Kopied Service v1.0. Monitoring {SCREENCLIP_PATH} and Clipboard...")
    
    # Sync existing ones first
    sync_existing_screenshots()
    
    # Start Screenshot Watcher
    event_handler = ScreenshotHandler()
    observer = Observer()
    observer.schedule(event_handler, SCREENCLIP_PATH, recursive=False)
    observer.start()
    
    # Start Clipboard Monitor thread
    cb_thread = threading.Thread(target=clipboard_monitor, daemon=True)
    cb_thread.start()
    
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    run_service()
