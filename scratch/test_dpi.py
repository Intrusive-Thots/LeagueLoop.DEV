import ctypes

def get_dpi():
    user32 = ctypes.windll.user32
    user32.SetProcessDPIAware()
    hwnd = user32.FindWindowW(None, "Riot Client")
    
    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                    ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
    
    rect = RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    print(f"DPI Aware Rect: {rect.right - rect.left}x{rect.bottom - rect.top} at {rect.left},{rect.top}")
    
if __name__ == "__main__":
    get_dpi()
