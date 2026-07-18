import tkinter as tk
from ui.components.factory import get_color
from .controller import ICON_SIZE, ICONS_PER_ROW, GRID_GAP

class DragController:
    def __init__(self, view, grid_controller):
        self.view = view
        self.grid_controller = grid_controller
        self.drag_data = {"widget": None, "start_x": 0, "start_y": 0, "idx": -1, "ghost": None, "cell": None, "is_dragging": False}

    def on_drag_start(self, event, idx, label, cell):
        if not self.view._edit_mode:
            return

        self.drag_data.update({
            "widget": label,
            "cell": cell,
            "idx": idx,
            "start_x": event.x_root,
            "start_y": event.y_root,
            "ghost": None,
            "is_dragging": False
        })

    def on_drag_motion(self, event):
        if not self.view._edit_mode or not self.drag_data.get("widget"):
            return

        dx = abs(event.x_root - self.drag_data["start_x"])
        dy = abs(event.y_root - self.drag_data["start_y"])
        if not self.drag_data.get("is_dragging"):
            if dx > 5 or dy > 5:
                self.drag_data["is_dragging"] = True
                self._create_ghost_icon()
            else:
                return

        ghost = self.drag_data["ghost"]
        if ghost:
            x = event.x_root - self.view.winfo_toplevel().winfo_rootx() - (ICON_SIZE // 2)
            y = event.y_root - self.view.winfo_toplevel().winfo_rooty() - (ICON_SIZE // 2)
            ghost.place(x=x, y=y)

    def _create_ghost_icon(self):
        label = self.drag_data["widget"]
        cell = self.drag_data["cell"]
        try:
            img = label.cget("image")
            if img:
                ghost = tk.Label(self.view.winfo_toplevel(), image=img, bg=get_color("colors.background.app"), bd=0)
                x = self.drag_data["start_x"] - self.view.winfo_toplevel().winfo_rootx() - (ICON_SIZE // 2)
                y = self.drag_data["start_y"] - self.view.winfo_toplevel().winfo_rooty() - (ICON_SIZE // 2)
                ghost.place(x=x, y=y)
                ghost.lift()
                self.drag_data["ghost"] = ghost
                
                label.configure(image="")
                cell.configure(fg_color="#141E28", border_width=1, border_color="#e81123")
        except Exception:
            pass

    def on_drag_release(self, event):
        if not self.view._edit_mode or not self.drag_data.get("widget"):
            return

        is_dragging = self.drag_data.get("is_dragging")
        idx = self.drag_data["idx"]
        
        if self.drag_data.get("ghost"):
            self.drag_data["ghost"].destroy()
            self.drag_data["ghost"] = None

        self.drag_data["widget"] = None
        self.drag_data["is_dragging"] = False

        if not is_dragging:
            self.view._on_cell_click(idx)
            return

        drop_x = event.x_root - self.view.grid_parent.winfo_rootx()
        drop_y = event.y_root - self.view.grid_parent.winfo_rooty()

        col = max(0, min(ICONS_PER_ROW - 1, int(drop_x // (ICON_SIZE + GRID_GAP))))
        row = max(0, int(drop_y // (ICON_SIZE + GRID_GAP)))
        
        target_idx = (row * ICONS_PER_ROW) + col
        
        names = self.grid_controller.get_priority_list()
        target_idx = max(0, min(target_idx, len(names) - 1))

        if target_idx != idx:
            item = names.pop(idx)
            names.insert(target_idx, item)
            self.grid_controller.save_priority_list(names)
            self.view._selected_indices = {target_idx}

        self.view._render_grid()
