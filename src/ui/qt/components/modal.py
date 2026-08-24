"""
LLModal — the app's dialog surface (UI/UX Master Plan §40, §54, §63).

Rules this encodes so callers cannot get them wrong:

* A modal always has a title that says what it will do, and a body that says
  what will happen. No bare "Are you sure?".
* The confirm button is labelled with the *verb* ("Delete account"), never
  "OK". You should be able to read only the buttons and still know what
  each one does (§40).
* Escape and the close control always cancel. Destructive confirms never
  get keyboard-default, so Enter cannot fire them by muscle memory.
* Frameless, matching the main window, with its own drag handle.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ui.qt.components.button import ButtonSize, ButtonVariant, LLButton
from ui.qt.theme.colors import (
    BORDER_ACCENT,
    BORDER_DEFAULT,
    SURFACE_PANEL_ELEVATED,
    TEXT_MUTED,
    TEXT_PRIMARY,
)
from ui.qt.theme.radii import RADIUS_LG
from ui.qt.theme.spacing import SPACE_LG, SPACE_MD, SPACE_SM, SPACE_XL
from ui.qt.theme.typography import TEXT_BODY, TEXT_SECTION_TITLE

MODAL_MIN_WIDTH = 420
#: A modal wider than this stops reading as a dialog and starts reading as
#: the application having lost control of its own window.
MODAL_MAX_WIDTH = 760
MODAL_MIN_HEIGHT = 160
MODAL_MAX_HEIGHT = 720


class LLModal(QDialog):
    """Base dialog: title, body region, footer actions."""

    def __init__(
        self,
        title: str,
        parent: Optional[QWidget] = None,
        confirm_text: str = "Confirm",
        cancel_text: str = "Cancel",
        destructive: bool = False,
    ):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setModal(True)
        self.setMinimumWidth(MODAL_MIN_WIDTH)
        self._drag_origin: Optional[QPoint] = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self.frame = QFrame(self)
        self.frame.setObjectName("modalFrame")
        self.frame.setStyleSheet(f"""
            QFrame#modalFrame {{
                background-color: {SURFACE_PANEL_ELEVATED};
                border: 1px solid {BORDER_ACCENT};
                border-radius: {RADIUS_LG}px;
            }}
        """)
        outer.addWidget(self.frame)

        root = QVBoxLayout(self.frame)
        root.setContentsMargins(SPACE_XL, SPACE_LG, SPACE_XL, SPACE_LG)
        root.setSpacing(SPACE_MD)

        self.title_label = QLabel(title, self.frame)
        self.title_label.setStyleSheet(
            TEXT_SECTION_TITLE.qss(color=TEXT_PRIMARY) + " background: transparent;"
        )
        root.addWidget(self.title_label)

        self.body = QVBoxLayout()
        self.body.setSpacing(SPACE_MD)
        root.addLayout(self.body, 1)

        self.error_label = QLabel("", self.frame)
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        root.addWidget(self.error_label)

        footer = QHBoxLayout()
        footer.setSpacing(SPACE_SM)
        footer.addStretch(1)

        self.cancel_button = LLButton(
            cancel_text, variant=ButtonVariant.GHOST, size=ButtonSize.MD,
            parent=self.frame,
        )
        self.cancel_button.clicked.connect(self.reject)
        footer.addWidget(self.cancel_button)

        self.confirm_button = LLButton(
            confirm_text,
            variant=ButtonVariant.DANGER if destructive else ButtonVariant.PRIMARY,
            size=ButtonSize.MD,
            parent=self.frame,
        )
        # A destructive confirm must never be the Enter-key default: Enter is
        # what you press to dismiss things you did not read (§40).
        self.confirm_button.setAutoDefault(not destructive)
        self.confirm_button.setDefault(not destructive)
        self.confirm_button.clicked.connect(self._on_confirm)
        footer.addWidget(self.confirm_button)

        root.addLayout(footer)

    # ------------------------------------------------------------- sizing
    def showEvent(self, event):  # noqa: N802 (Qt override)
        """Size to whatever the body ended up containing.

        Modals are populated *after* `__init__` — `add_widget` is called by
        the subclass — so the only honest moment to measure is the one just
        before the dialog is shown. Doing it here means a two-line confirm and
        a text editor with twenty rows both get the size they need, and
        neither is hard-coded anywhere.
        """
        from ui.qt.services.popup_size import size_to_content

        super().showEvent(event)
        if not getattr(self, "_sized", False):
            self._sized = True
            size_to_content(
                self,
                min_size=(MODAL_MIN_WIDTH, MODAL_MIN_HEIGHT),
                max_size=(MODAL_MAX_WIDTH, MODAL_MAX_HEIGHT),
            )
            self._centre_on_parent()

    def _centre_on_parent(self) -> None:
        """A frameless dialog gets no placement from the window manager."""
        parent = self.parentWidget()
        try:
            if parent is not None and parent.isVisible():
                origin = parent.frameGeometry()
            else:
                from PySide6.QtGui import QGuiApplication

                screen = QGuiApplication.primaryScreen()
                if screen is None:
                    return
                origin = screen.availableGeometry()
            self.move(
                origin.x() + (origin.width() - self.width()) // 2,
                origin.y() + (origin.height() - self.height()) // 2,
            )
        except Exception as exc:
            from utils.logger import Logger

            Logger.debug("Modal", "Could not centre the dialog", exc=exc)

    # ---------------------------------------------------------------- body
    def add_widget(self, widget: QWidget, stretch: int = 0) -> None:
        self.body.addWidget(widget, stretch)

    def add_layout(self, layout) -> None:
        self.body.addLayout(layout)

    def set_message(self, text: str) -> QLabel:
        label = QLabel(text, self.frame)
        label.setWordWrap(True)
        label.setStyleSheet(
            TEXT_BODY.qss(color=TEXT_MUTED) + " background: transparent;"
        )
        self.add_widget(label)
        return label

    # --------------------------------------------------------------- error
    def set_error(self, message: str) -> None:
        from ui.qt.theme.colors import COLOR_DANGER

        self.error_label.setText(message)
        self.error_label.setStyleSheet(
            TEXT_BODY.qss(color=COLOR_DANGER) + " background: transparent;"
        )
        self.error_label.setVisible(bool(message))

    def clear_error(self) -> None:
        self.error_label.setText("")
        self.error_label.setVisible(False)

    # ------------------------------------------------------------- confirm
    def validate(self) -> bool:
        """Override to block accept(). Return False to keep the modal open."""
        return True

    def _on_confirm(self) -> None:
        self.clear_error()
        if self.validate():
            self.accept()

    # ---------------------------------------------------------- frameless
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_origin = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_origin is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_origin)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_origin = None
        super().mouseReleaseEvent(event)


class LLConfirmModal(LLModal):
    """A modal that only asks a question. Body is one explanatory paragraph."""

    def __init__(
        self,
        title: str,
        message: str,
        confirm_text: str,
        parent: Optional[QWidget] = None,
        destructive: bool = True,
    ):
        super().__init__(
            title, parent=parent, confirm_text=confirm_text, destructive=destructive
        )
        self.set_message(message)
