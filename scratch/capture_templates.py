import pyautogui
import ctypes
import os
from PIL import Image

def capture_templates():
    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, "Riot Client")
    
    if hwnd == 0:
        print("Riot Client window not found.")
        return
        
    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                    ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
    
    rect = RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    
    win_x = rect.left
    win_y = rect.top
    win_w = rect.right - rect.left
    win_h = rect.bottom - rect.top
    
    print(f"Riot Client at {win_x}, {win_y} ({win_w}x{win_h})")
    
    user32.SetForegroundWindow(hwnd)
    pyautogui.sleep(1)
    
    # We take a screenshot of the window
    screenshot = pyautogui.screenshot(region=(win_x, win_y, win_w, win_h))
    
    # Define bounding boxes for the "USERNAME" and "PASSWORD" labels based on manual pixel offsets
    # In a 1536x864 window, the labels are roughly around:
    # Username Label: x: 60 to 120, y: 260 to 280
    # Let's just crop a small distinctive piece, e.g., the "USERNAME" text itself.
    # Actually, we can just crop the entire input box.
    # The input box for username is roughly x:60 to 220, y:280 to 320
    
    # Let's save the whole left panel first to inspect it
    left_panel = screenshot.crop((0, 0, int(win_w * 0.2), win_h))
    left_panel.save("scratch/left_panel.png")
    
    print("Saved left_panel.png")
    
if __name__ == "__main__":
    capture_templates()
