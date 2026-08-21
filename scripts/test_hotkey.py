import keyboard
import time
import threading

def on_hotkey():
    print("Hotkey triggered!")
    with open("hotkey_test.log", "a") as f:
        f.write("Triggered!\n")

try:
    print("Binding hotkey ctrl+k")
    keyboard.add_hotkey("ctrl+k", on_hotkey, suppress=False)
    print("Hotkey bound successfully.")
except Exception as e:
    print(f"Error binding hotkey: {e}")

def trigger_later():
    time.sleep(1)
    print("Sending ctrl+k...")
    keyboard.send("ctrl+k")
    time.sleep(1)
    print("Done sending.")
    keyboard.send("esc")

threading.Thread(target=trigger_later).start()
keyboard.wait("esc")
