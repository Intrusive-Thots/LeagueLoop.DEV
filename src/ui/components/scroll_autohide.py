"""Hide a CTkScrollableFrame's scrollbar until its content overflows.

CustomTkinter always grids the bar, so empty states (no friends, no
accounts, an empty loot vault) show a track with nothing to scroll. This
watches the canvas view and only shows the bar when there is somewhere to
go; wheel scrolling already no-ops when the view spans (0.0, 1.0).
"""
import tkinter

from utils.logger import Logger


def needs_scrollbar(view) -> bool:
    """True when a ``yview()``/``xview()`` pair doesn't cover the whole content."""
    first, last = view
    return first > 0.0 or last < 1.0


def autohide_scrollbar(frame):
    """Wire *frame* (a ``ctk.CTkScrollableFrame``) to show its bar only on overflow."""
    bar = getattr(frame, "_scrollbar", None)
    canvas = getattr(frame, "_parent_canvas", None)
    if bar is None or canvas is None:
        return frame
    vertical = getattr(frame, "_orientation", "vertical") != "horizontal"
    pending = {"id": None}
    grid_opts = {}
    # Flap guard: if the bar keeps flipping while the content size stays the
    # same, the layout depends on the bar itself; leave it shown.
    flips = {"count": 0, "content": None}

    def _sync():
        pending["id"] = None
        try:
            view = canvas.yview() if vertical else canvas.xview()
            shown = bool(bar.winfo_manager())
            content = frame.winfo_reqheight() if vertical else frame.winfo_reqwidth()
            if content != flips["content"]:
                flips["count"], flips["content"] = 0, content
            want = needs_scrollbar(view)
            if want != shown:
                flips["count"] += 1
                if flips["count"] > 4:
                    if not shown and grid_opts:
                        tkinter.Grid.grid_configure(bar, **grid_opts)
                    return
            if want:
                if not shown and grid_opts:
                    # Plain Tk regrid with the saved, already-scaled options;
                    # CTk's grid() would rescale padding and bare grid()
                    # doesn't restore a removed slave reliably.
                    tkinter.Grid.grid_configure(bar, **grid_opts)
            elif not shown:
                # A forget issued before the tab's first map can leave the
                # window mapped with no manager; regrid and drop it again
                # now that it really exists so Tk actually unmaps it.
                if grid_opts and bar.winfo_ismapped():
                    tkinter.Grid.grid_configure(bar, **grid_opts)
                    tkinter.Grid.grid_forget(bar)
            else:
                # A shown bar has its own minimum length and can be what
                # holds the frame open (Loot asks for 125px but renders
                # taller). Pin the canvas at the size the bar was holding so
                # hiding the bar never shrinks the view into overflow and
                # flips straight back.
                if vertical:
                    size = min(canvas.winfo_height(), bar.winfo_reqheight())
                    asked = int(float(canvas.cget("height")))
                    if size > asked:
                        canvas.configure(height=size)
                else:
                    size = min(canvas.winfo_width(), bar.winfo_reqwidth())
                    asked = int(float(canvas.cget("width")))
                    if size > asked:
                        canvas.configure(width=size)
                info = dict(bar.grid_info())
                info["in_"] = info.pop("in", None) or bar.master
                grid_opts.clear()
                grid_opts.update(info)
                tkinter.Grid.grid_forget(bar)
        except tkinter.TclError:
            pass
        except Exception as exc:
            Logger.debug("ScrollAutohide", f"Scrollbar sync failed: {exc}", exc=exc)

    def _schedule(_event=None):
        # Coalesce: content and canvas resizes arrive in bursts.
        if pending["id"] is None:
            try:
                pending["id"] = frame.after_idle(_sync)
            except tkinter.TclError:
                pass

    tkinter.Misc.bind(frame, "<Configure>", _schedule, add="+")
    canvas.bind("<Configure>", _schedule, add="+")
    tkinter.Misc.bind(frame, "<Map>", _schedule, add="+")
    tkinter.Misc.bind(bar, "<Map>", _schedule, add="+")
    _schedule()
    return frame
