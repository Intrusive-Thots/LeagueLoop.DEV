import tkinter as tk
import customtkinter as ctk
from ui.components.factory import get_color, get_font
from utils.logger import Logger
from ui.ui_shared import CTkTooltip

class DraggableList(ctk.CTkScrollableFrame):
    def __init__(self, master, items, on_reorder, on_remove, asset_manager=None, **kwargs):
        super().__init__(master, **kwargs)
        self.items = items
        self.on_reorder = on_reorder
        self.on_remove = on_remove
        self.asset_manager = asset_manager
        self._row_frames = []
        self._drag_data = {"y": 0, "item": None, "index": -1}
        self.render()

    def render(self):
        # Prevent destroying CTkScrollableFrame internals (Canvas/Scrollbar).
        for widget in self._row_frames:
            if widget.winfo_exists():
                widget.destroy()
        self._row_frames.clear()
        
        if not self.items:
            lbl_empty = ctk.CTkLabel(self, text="Build your ARAM priority list.\nClick '+ Add Champion' to start.", text_color=get_color("colors.text.muted", "gray"))
            lbl_empty.pack(pady=20)
            self._row_frames.append(lbl_empty)
            return

        danger_color = get_color("colors.state.danger", "#EF5350")
        accent_color = get_color("colors.accent.primary", "#C8AA6E")
        card_hover_color = get_color("colors.background.card", "gray30")

        # ⚡ Bolt: Apply LICM for faster list rendering
        font_body = get_font("body")

        for i, item in enumerate(self.items):
            frame = ctk.CTkFrame(self, fg_color=get_color("colors.background.card", "gray20"))
            frame.pack(fill="x", pady=2, padx=5)
            self._row_frames.append(frame)
            
            # Priority Number
            lbl_pri = ctk.CTkLabel(frame, text=f"#{i+1}", width=30, font=font_body, text_color=get_color("colors.accent.gold", "gold"))
            lbl_pri.pack(side="left", padx=5)
            
            # Champion Icon
            if self.asset_manager:
                lbl_icon = ctk.CTkLabel(frame, text="", width=32, height=32)
                lbl_icon.pack(side="left", padx=5)

                def _update_icon(img, lbl=lbl_icon):
                    if lbl.winfo_exists():
                        lbl.configure(image=img)

                self.asset_manager.get_icon_async("champion", item, _update_icon, size=(32, 32), widget=lbl_icon)
            
            # Name
            display_name = item
            if self.asset_manager and self.asset_manager.champ_data and item in self.asset_manager.champ_data:
                display_name = self.asset_manager.champ_data[item].get("name", item)
                
            lbl_name = ctk.CTkLabel(frame, text=display_name)
            lbl_name.pack(side="left", padx=5)
            
            # Action Buttons Container
            actions = ctk.CTkFrame(frame, fg_color="transparent")
            actions.pack(side="right", padx=5)
            
            # Up Button
            btn_up = ctk.CTkButton(
                actions, text="▲", width=25, height=25,
                fg_color="transparent", hover_color=get_color("colors.state.hover", "gray30"),
                command=lambda f=frame: self._move_item(f, -1),
                cursor="hand2",
            )
            btn_up.pack(side="left", padx=2)
            CTkTooltip(btn_up, "Move Up")
            if i == 0:
                btn_up.configure(state="disabled", text_color=get_color("colors.text.disabled", "gray40"))
                
            # Down Button
            btn_down = ctk.CTkButton(
                actions, text="▼", width=25, height=25,
                fg_color="transparent", hover_color=get_color("colors.state.hover", "gray30"),
                command=lambda f=frame: self._move_item(f, 1),
                cursor="hand2",
            )
            btn_down.pack(side="left", padx=2)
            CTkTooltip(btn_down, "Move Down")
            if i == len(self.items) - 1:
                btn_down.configure(state="disabled", text_color=get_color("colors.text.disabled", "gray40"))

            # Remove Button
            btn_remove = ctk.CTkButton(
                actions, text="❌", width=30, height=25,
                fg_color="transparent", hover_color=danger_color,
                command=lambda x=item, f=frame: self._animate_remove(x, f),
                cursor="hand2",
            )
            btn_remove.pack(side="left", padx=(5, 0))
            CTkTooltip(btn_remove, "Remove Item")
            
            # Optional Drag Handle (Kept for flexibility but less buggy now)
            lbl_drag = ctk.CTkLabel(frame, text=" ↕ ", cursor="hand2")
            lbl_drag.pack(side="right", padx=5)
            CTkTooltip(lbl_drag, "Drag to reorder")
            
            lbl_drag.bind("<Button-1>", lambda e, f=frame: self._on_drag_start(e, f))
            lbl_drag.bind("<ButtonRelease-1>", self._on_drag_release)
            lbl_drag.configure(text_color=get_color("colors.text.muted", "gray"))
            lbl_drag.bind("<Enter>", lambda e, l=lbl_drag: l.configure(text_color=get_color("colors.text.primary", "white")))
            lbl_drag.bind("<Leave>", lambda e, l=lbl_drag: l.configure(text_color=get_color("colors.text.muted", "gray")))

            # Malcolm's Infusion: Row hover states
            def on_enter(e, f=frame):
                if f.winfo_exists() and f.cget("fg_color") != danger_color and f.cget("fg_color") != accent_color:
                    f.configure(fg_color=card_hover_color)
            def on_leave(e, f=frame):
                if f.winfo_exists() and f.cget("fg_color") != danger_color and f.cget("fg_color") != accent_color:
                    f.configure(fg_color=get_color("colors.background.card", "gray20"))

            frame.bind("<Enter>", on_enter)
            frame.bind("<Leave>", on_leave)

            for child in frame.winfo_children():
                child.bind("<Enter>", on_enter)
                child.bind("<Leave>", on_leave)

    def _move_item(self, frame, offset):
        if frame not in self._row_frames: return
        index = self._row_frames.index(frame)
        new_idx = index + offset

        if 0 <= new_idx < len(self.items):
            # ⚡ Bolt: O(1) targeted widget repacking
            # Instead of destroying and rebuilding all CTkFrames on every list mutation,
            # we simply unpack and repack the existing widgets in the new order.
            # This completely eliminates CustomTkinter widget allocation overhead and prevents micro-stutters.

            # Swap data
            self.items.insert(new_idx, self.items.pop(index))
            self.on_reorder(self.items)

            # Swap frames
            self._row_frames.insert(new_idx, self._row_frames.pop(index))

            # Repack O(N) frames without destroying
            for f in self._row_frames:
                f.pack_forget()

            for i, f in enumerate(self._row_frames):
                f.pack(fill="x", pady=2, padx=5)
                # Update priority label
                lbl_pri = f.winfo_children()[0]
                lbl_pri.configure(text=f"#{i+1}")

                # Update Up/Down button states
                actions = f.winfo_children()[3]
                btn_up = actions.winfo_children()[0]
                btn_down = actions.winfo_children()[1]

                if i == 0:
                    btn_up.configure(state="disabled", text_color=get_color("colors.text.disabled", "gray40"))
                else:
                    btn_up.configure(state="normal", text_color=get_color("colors.text.primary", "#F0E6D2"))

                if i == len(self.items) - 1:
                    btn_down.configure(state="disabled", text_color=get_color("colors.text.disabled", "gray40"))
                else:
                    btn_down.configure(state="normal", text_color=get_color("colors.text.primary", "#F0E6D2"))

            self.after(50, lambda: self._highlight_row(new_idx))

    def _highlight_row(self, index):
        """Malcolm's Infusion: Pulse the row to help the eye track moved items."""
        if self._row_frames and 0 <= index < len(self._row_frames):
            frame = self._row_frames[index]
            if not frame.winfo_exists(): return

            orig_color = frame.cget("fg_color")
            pulse_color = get_color("colors.accent.primary", "#C8AA6E")

            try:
                frame.configure(fg_color=pulse_color)
                self.after(300, lambda f=frame, c=orig_color: f.winfo_exists() and f.configure(fg_color=c))
            except Exception as e:
                Logger.error("draggable_list.py", f"Highlight animation error: {e}")

    def _animate_remove(self, item, frame):
        """Malcolm's Infusion: Smooth slide-out animation before removal."""
        if not frame.winfo_exists():
            self._do_remove(item)
            return

        # Disable interaction during animation to prevent rapid-click issues
        for child in frame.winfo_children():
            try:
                child.configure(state="disabled")
            except ValueError:
                pass # Some widgets don't have state

        # Flash danger color
        danger_color = get_color("colors.state.danger", "#EF5350")
        frame.configure(fg_color=danger_color)

        # Read current padding safely
        try:
            pack_info = frame.pack_info()
            current_padx = pack_info.get('padx', 5)
            # padx can be a tuple or a single value
            if isinstance(current_padx, tuple):
                left_pad = current_padx[0]
                right_pad = current_padx[1]
            else:
                left_pad = current_padx
                right_pad = current_padx
        except Exception as e:
            Logger.error("draggable_list.py", f"Padding extraction error: {e}")
            left_pad, right_pad = 5, 5

        def slide(step):
            if not frame.winfo_exists():
                # Critical bug fix: If the frame is destroyed mid-animation (e.g. by another rapid render),
                # we MUST ensure the underlying state removal still occurs!
                self._do_remove(item)
                return

            if step < 10:
                # Slide right by increasing left padding
                try:
                    frame.pack_configure(padx=(left_pad + step * 10, right_pad))
                    self.after(16, lambda: slide(step + 1))
                except tk.TclError:
                    self._do_remove(item)
            else:
                self._do_remove(item)

        slide(0)

    def _do_remove(self, item):
        self.on_remove(item)
        
    def _on_drag_start(self, event, frame):
        if frame not in self._row_frames: return
        index = self._row_frames.index(frame)
        self._drag_data["item"] = self.items[index]
        self._drag_data["index"] = index
        self._drag_data["frame"] = frame
        self._drag_data["y"] = event.y_root
        
    def _on_drag_release(self, event):
        if not self._drag_data.get("item"): return
        
        delta_y = event.y_root - self._drag_data["y"]
        row_height = 40
        slots_moved = round(delta_y / row_height)
        
        if slots_moved != 0:
            frame = self._drag_data["frame"]
            self._move_item(frame, slots_moved)
                
        self._drag_data = {"y": 0, "item": None, "index": -1, "frame": None}
