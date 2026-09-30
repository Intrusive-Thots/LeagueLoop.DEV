import customtkinter as ctk

class SectionContainer(ctk.CTkFrame):
    def __init__(self, master, padding=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(0, weight=1)
