import keyboard

try:
    keyboard.add_hotkey("ctrl+alt+win+c", lambda: print("x"), suppress=False)
    print("ctrl+alt+win+c OK")
except Exception as e:
    print("Error with ctrl+alt+win+c:", e)

try:
    keyboard.add_hotkey("alt+esc", lambda: print("x"), suppress=False)
    print("alt+esc OK")
except Exception as e:
    print("Error with alt+esc:", e)
    
try:
    keyboard.add_hotkey("ctrl+alt+a", lambda: print("x"), suppress=False)
    print("ctrl+alt+a OK")
except Exception as e:
    print("Error with ctrl+alt+a:", e)

