import sys
try:
    import uiautomation as auto
except ImportError:
    auto = None

def test_uia():
    if auto is None:
        print("uiautomation not installed")
        return
    print("Searching for Riot Client...")
    riot_window = auto.WindowControl(searchDepth=1, Name="Riot Client")
    if not riot_window.Exists(3, 1):
        print("Riot Client window not found")
        return
        
    print(f"Found window: {riot_window.Name}")
    print("Walking control tree:")
    for control, depth in auto.WalkControl(riot_window, maxDepth=6):
        print("  " * depth + f"{control.ControlType}: {control.Name} ({control.ClassName})")

if __name__ == "__main__":
    test_uia()
