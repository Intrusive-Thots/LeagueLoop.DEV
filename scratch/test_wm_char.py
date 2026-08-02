import ctypes
import time
import win32api
import win32con

def send_char_to_window(hwnd, char):
    win32api.SendMessage(hwnd, win32con.WM_CHAR, ord(char), 0)

def test_wm_char():
    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, "Riot Client")
    
    if hwnd == 0:
        print("Riot Client not found.")
        return

    # Bring to front
    user32.SetForegroundWindow(hwnd)
    time.sleep(1)

    print("Sending characters...")
    for char in "hello":
        send_char_to_window(hwnd, char)
        time.sleep(0.1)

if __name__ == "__main__":
    test_wm_char()
