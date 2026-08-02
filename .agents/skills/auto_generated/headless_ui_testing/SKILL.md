---
name: headless_ui_testing
description: Reusable skill for unit testing CustomTkinter and Tkinter UI widgets in headless CI/test environments without initializing Tcl/Tk window handles or encountering TclError.
---

# Headless UI Testing Skill

## Purpose
When unit testing CustomTkinter (`ctk.CTkFrame`, `ctk.CTkEntry`, etc.) or Tkinter widgets on Windows or CI environments, instantiating `ctk.CTk()` top-level windows can cause `_tkinter.TclError: Can't find a usable init.tcl` or thread-local storage hangs across multiple test files.

## Reusable Pattern: `sys.modules` Headless Mocking
Instead of creating `ctk.CTk()` or calling real `tkinter.Widget` constructors, mock `customtkinter` and `tkinter` in `sys.modules` before importing the widget under test:

```python
import sys
import unittest
from unittest.mock import MagicMock, patch

class TestHeadlessUI(unittest.TestCase):
    def setUp(self):
        self.root = MagicMock()
        self.config_mock = MagicMock()
        self.config_mock.get.return_value = {}
        self.assets_mock = MagicMock()

    def test_widget_instantiation(self):
        mods_to_mock = {
            'customtkinter': MagicMock(),
            'tkinter': MagicMock(),
            'tkinterdnd2': MagicMock(),
            'tkinterdnd2.TkinterDnD': MagicMock(),
        }
        with patch.dict(sys.modules, mods_to_mock):
            # Remove any previously cached module imports from sys.modules
            for mod_name in list(sys.modules.keys()):
                if mod_name.startswith('ui.components.your_component'):
                    sys.modules.pop(mod_name, None)
            from ui.components.your_component import YourComponent
            
            widget = YourComponent(self.root, self.config_mock, self.assets_mock)
            self.assertIsNotNone(widget)
```

## Benefits
- Zero native Tk/Tcl window creation.
- Runs in 0.01 seconds without UI flickers or hangs.
- 100% thread-safe across full test suites (`pytest -v`).
