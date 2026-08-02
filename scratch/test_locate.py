import pyautogui
import ctypes
import time

def test_locate():
    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, "Riot Client")
    if hwnd != 0:
        user32.ShowWindow(hwnd, 9) # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
        time.sleep(2)
        
    pyautogui.screenshot('scratch/debug_screen.png')
        
    try:
        logo_loc = pyautogui.locateCenterOnScreen('assets/templates/riot_logo.png', confidence=0.7, grayscale=True)
        print(f"Logo location: {logo_loc}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_locate()
