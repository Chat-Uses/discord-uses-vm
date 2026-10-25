"""Discord Uses VM control panel (PyQt6)."""
import asyncio
import base64
import csv
import html
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from string import Template

import discord
from PyQt6.QtCore import (
    QEasingCurve, QObject, QProcess, QPropertyAnimation, QRectF, QRegularExpression, QRunnable,
    QThread, QThreadPool, QTimer, QUrl, Qt, pyqtProperty, pyqtSignal,
)
from PyQt6.QtGui import (
    QAction, QColor, QDesktopServices, QFont, QKeySequence, QPainter, QPalette, QPixmap,
    QRegularExpressionValidator,
)
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QDoubleSpinBox,
    QFileDialog, QFormLayout, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView,
    QInputDialog, QLabel, QLineEdit, QListWidget, QMainWindow, QMenu, QMessageBox,
    QPlainTextEdit, QProgressDialog, QPushButton, QScrollArea, QSizePolicy, QSpinBox, QSplitter,
    QStackedWidget, QTableWidget, QTableWidgetItem, QTextBrowser, QVBoxLayout, QWidget,
)

import keyboard_layouts
import updater
from config import ALL_COMMANDS, LOG_CATEGORIES, MOD_COMMANDS, VOTE_COMMANDS, Config
from discord_bot import Events, VMBot
from gui_lang import LANGUAGES, T, set_language, translate_tree
from vbox_control import VBox, VBoxError, normalize_combo
from version import __version__

APP_NAME = "Discord Uses VM"
LOG_DIR = Path(__file__).with_name("logs")
ASSET_DIR = Path(__file__).with_name("assets")
LEVEL_COLORS = {"info": "#9aa0aa", "ok": "#3ba55d", "warn": "#f0a020", "error": "#ed4245"}
INVITE_PERMISSIONS = 1024 + 2048 + 16384 + 32768 + 65536  # view, send, embed, attach, history
MAX_LOG_ENTRIES = 5000


# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------

THEMES = {
    "dark": {
        "bg": "#0f1013", "sidebar": "#15161a", "surface": "#1a1b20", "surface2": "#22242a",
        "hover": "#2a2d34", "border": "#2b2e35", "text": "#e8e9ec", "muted": "#8a8f99",
        "accent": "#5865f2", "accent_hover": "#6c77f4", "accent_soft": "rgba(88,101,242,0.16)",
        "danger": "#e5484d", "danger_hover": "#f05a5f", "success": "#3ba55d",
        "warning": "#f0a020", "toggle_off": "#3a3d45",
    },
    "light": {
        "bg": "#f3f4f7", "sidebar": "#ffffff", "surface": "#ffffff", "surface2": "#f2f3f6",
        "hover": "#e8eaef", "border": "#e2e4ea", "text": "#1c1e23", "muted": "#6b7079",
        "accent": "#5865f2", "accent_hover": "#4752e0", "accent_soft": "rgba(88,101,242,0.12)",
        "danger": "#e5484d", "danger_hover": "#cf3a3f", "success": "#2f9e52",
        "warning": "#d98a00", "toggle_off": "#cdd0d8",
    },
}
THEME = dict(THEMES["dark"])

STYLE = Template("""
* { outline: none; }
QMainWindow, QWidget#root { background: $bg; }
QWidget { color: $text; }
QWidget#page, QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }
QLabel { background: transparent; }

/* Sidebar */
QFrame#sidebar { background: $sidebar; border-right: 1px solid $border; }
QLabel#brand { font-size: 15pt; font-weight: 700; }
QLabel#brandSub { color: $muted; font-size: 8.5pt; }
QLabel#navSection { color: $muted; font-size: 8pt; font-weight: 600; letter-spacing: 1px; }
QPushButton#nav { text-align: left; padding: 9px 14px; border: none; border-radius: 8px;
                  background: transparent; color: $muted; font-size: 10pt; }
QPushButton#nav:hover { background: $surface2; color: $text; }
QPushButton#nav:checked { background: $accent_soft; color: $text; font-weight: 600; }
QLabel#statusPill { background: $surface2; border: 1px solid $border; border-radius: 14px;
                    padding: 6px 12px; }

/* Page header */
QLabel#pageTitle { font-size: 19pt; font-weight: 700; }
QLabel#pageSubtitle { color: $muted; font-size: 10pt; }

/* Cards */
QGroupBox { background: $surface; border: 1px solid $border; border-radius: 12px;
            margin-top: 0px; padding: 40px 16px 16px 16px; font-size: 10.5pt; font-weight: 600; }
QGroupBox::title { subcontrol-origin: padding; subcontrol-position: top left;
                   left: 16px; top: 14px; color: $text; }
QFrame#card { background: $surface; border: 1px solid $border; border-radius: 12px; }
QLabel#statValue { font-size: 15pt; font-weight: 700; }
QLabel#statLabel { color: $muted; font-size: 8.5pt; font-weight: 600; letter-spacing: 0.5px; }
QLabel#hint { color: $muted; font-weight: normal; }
QLabel#preview { background: #000; color: $muted; border-radius: 10px; }

/* Buttons */
QPushButton { background: $surface2; border: 1px solid $border; border-radius: 8px;
              padding: 7px 14px; font-weight: 500; }
QPushButton:hover { background: $hover; }
QPushButton:pressed { background: $border; }
QPushButton:disabled { color: $muted; background: $surface2; }
QPushButton#primary { background: $accent; border: 1px solid $accent; color: white; font-weight: 600; }
QPushButton#primary:hover { background: $accent_hover; border-color: $accent_hover; }
QPushButton#danger { background: transparent; border: 1px solid $danger; color: $danger; font-weight: 600; }
QPushButton#danger:hover { background: $danger; color: white; }
QPushButton#primary:disabled, QPushButton#danger:disabled {
    background: $surface2; border: 1px solid $border; color: $muted; }
QPushButton#chip { padding: 4px 11px; border-radius: 13px; font-size: 9pt; }
QPushButton#link { background: transparent; border: none; padding: 0; color: $accent;
                   font-size: 8.5pt; text-align: left; }
QPushButton#link:hover { text-decoration: underline; background: transparent; }
QPushButton#chip:hover { border-color: $accent; }
QPushButton#icon { padding: 6px 10px; }

/* Inputs */
QLineEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: $surface2; border: 1px solid $border; border-radius: 8px;
    padding: 6px 10px; selection-background-color: $accent; selection-color: white; }
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 1px solid $accent; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox::down-arrow { image: url("$chevron"); width: 12px; height: 12px; }
QComboBox QAbstractItemView { background: $surface; border: 1px solid $border; border-radius: 8px;
                              padding: 4px; selection-background-color: $accent_soft; selection-color: $text; }
/* Clean number fields: type, scroll or use arrow keys */
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    width: 0; border: none; }

/* Lists & tables */
QListWidget, QTableWidget { background: $surface2; border: 1px solid $border; border-radius: 8px;
                            padding: 4px; alternate-background-color: $surface; }
QListWidget::item { padding: 6px 8px; border-radius: 6px; }
QListWidget::item:hover { background: $hover; }
QListWidget::item:selected, QTableWidget::item:selected { background: $accent_soft; color: $text; }
QTableWidget { gridline-color: transparent; }
QTableWidget::item { padding: 4px 8px; }
QHeaderView::section { background: transparent; color: $muted; border: none;
                       border-bottom: 1px solid $border; padding: 8px; font-weight: 600; }
QTableCornerButton::section { background: transparent; border: none; }

/* Scrollbars */
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle { background: $border; border-radius: 3px; min-height: 30px; min-width: 30px; }
QScrollBar::handle:hover { background: $muted; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QSplitter::handle { background: transparent; width: 12px; }
QToolTip { background: $surface; color: $text; border: 1px solid $border; border-radius: 6px; padding: 6px; }
QMenu { background: $surface; border: 1px solid $border; border-radius: 10px; padding: 6px; }
QMenu::item { padding: 7px 16px; border-radius: 6px; }
QMenu::item:selected { background: $accent_soft; }
QStatusBar { background: $sidebar; color: $muted; border-top: 1px solid $border; }
QMessageBox, QInputDialog { background: $surface; }
""")


def apply_theme(app: QApplication, dark: bool):
    THEME.clear()
    THEME.update(THEMES["dark" if dark else "light"])
    app.setStyle("Fusion")
    p = QPalette()
    roles = {
        QPalette.ColorRole.Window: "bg", QPalette.ColorRole.WindowText: "text",
        QPalette.ColorRole.Base: "surface2", QPalette.ColorRole.AlternateBase: "surface",
        QPalette.ColorRole.ToolTipBase: "surface", QPalette.ColorRole.ToolTipText: "text",
        QPalette.ColorRole.Text: "text", QPalette.ColorRole.Button: "surface2",
        QPalette.ColorRole.ButtonText: "text", QPalette.ColorRole.Highlight: "accent",
        QPalette.ColorRole.Link: "accent", QPalette.ColorRole.PlaceholderText: "muted",
        QPalette.ColorRole.Mid: "border",
    }
    for role, key in roles.items():
        p.setColor(role, QColor(THEME[key]))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor("white"))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText, QPalette.ColorRole.WindowText):
        p.setColor(QPalette.ColorGroup.Disabled, role, QColor(THEME["muted"]))
    app.setPalette(p)
    app.setStyleSheet(STYLE.substitute(THEME, chevron=chevron_icon(THEME["muted"])))


def chevron_icon(color: str) -> str:
    """Write a small SVG dropdown arrow in the theme color; QSS needs a file path."""
    ASSET_DIR.mkdir(exist_ok=True)
    path = ASSET_DIR / f"chevron-{color.lstrip('#')}.svg"
    if not path.exists():
        path.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 12 12">'
            f'<path d="M2.5 4.5 6 8l3.5-3.5" fill="none" stroke="{color}" stroke-width="1.6" '
            'stroke-linecap="round" stroke-linejoin="round"/></svg>',
            encoding="utf-8",
        )
    return path.as_posix()


def set_dark_titlebar(window: QWidget, dark: bool):
    """Windows 10/11: match the native title bar to the theme."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        value = ctypes.c_int(1 if dark else 0)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            int(window.winId()), 20, ctypes.byref(value), ctypes.sizeof(value)
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Threads
# ---------------------------------------------------------------------------

class BotSignals(QObject):
    log = pyqtSignal(str, str)
    command = pyqtSignal(str, str, str, bool, str)  # user, user id (str: too big for int), text, ok, result
    status = pyqtSignal(str)
    config_changed = pyqtSignal()
    channels = pyqtSignal(list)


class SignalEvents(Events):
    """Forwards bot events (from the bot thread) to the GUI thread via Qt signals."""

    def __init__(self, signals: BotSignals):
        self.signals = signals

    def log(self, level, message):
        self.signals.log.emit(level, message)

    def command(self, user, user_id, text, ok, result):
        self.signals.command.emit(user, str(user_id), text, ok, result)

    def status(self, status):
        self.signals.status.emit(status)

    def config_changed(self):
        self.signals.config_changed.emit()

    def channels(self, channels):
        self.signals.channels.emit(channels)


class BotThread(QThread):
    """Runs the discord bot on its own asyncio loop."""

    def __init__(self, config: Config, signals: BotSignals):
        super().__init__()
        self.config = config
        self.signals = signals
        self.bot: VMBot | None = None
        self.loop: asyncio.AbstractEventLoop | None = None

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.bot = VMBot(self.config, SignalEvents(self.signals))
            self.loop.run_until_complete(self.bot.start(self.config.token))
        except discord.LoginFailure:
            self.signals.log.emit("error", "Login failed: the bot token is invalid.")
        except discord.PrivilegedIntentsRequired:
            self.signals.log.emit(
                "error", "Turn on MESSAGE CONTENT INTENT for your bot in the Discord Developer Portal."
            )
        except Exception as e:
            self.signals.log.emit("error", f"Bot crashed: {e!r}")
        finally:
            try:
                if self.bot and not self.bot.is_closed():
                    self.loop.run_until_complete(self.bot.close())
                self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            finally:
                self.loop.close()
                self.signals.status.emit("offline")

    def call(self, make_coro) -> bool:
        """Schedule a coroutine on the bot's loop from the GUI thread."""
        if self.bot and self.loop and self.loop.is_running() and not self.bot.is_closed():
            future = asyncio.run_coroutine_threadsafe(make_coro(), self.loop)
            future.add_done_callback(self._report_error)
            return True
        return False

    def _report_error(self, future):
        # Without this, exceptions in scheduled coroutines vanish silently
        if not future.cancelled() and future.exception() is not None:
            self.signals.log.emit("error", f"Bot action failed: {future.exception()!r}")

    def stop(self):
        self.call(lambda: self.bot.close())


class TaskSignals(QObject):
    done = pyqtSignal(object)
    error = pyqtSignal(str)


class Task(QRunnable):
    """Runs a blocking VirtualBox call off the GUI thread."""

    def __init__(self, fn, *args):
        super().__init__()
        self.setAutoDelete(False)
        self.fn, self.args = fn, args
        self.signals = TaskSignals()

    def run(self):
        try:
            result = self.fn(*self.args)
        except Exception as e:
            self.signals.error.emit(str(e))
        else:
            self.signals.done.emit(result)


# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------

class Toggle(QCheckBox):
    """An animated on/off switch. Drop-in replacement for QCheckBox."""

    def __init__(self, text: str = ""):
        super().__init__(text)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._knob = 0.0
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate)

    def _get_knob(self):
        return self._knob

    def _set_knob(self, value):
        self._knob = value
        self.update()

    knob = pyqtProperty(float, _get_knob, _set_knob)

    def _animate(self, on: bool):
        self._anim.stop()
        if not self.isVisible():
            # Settings loading at startup: jump straight to the new state
            self._set_knob(1.0 if on else 0.0)
            return
        self._anim.setStartValue(self._knob)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def sizeHint(self):
        size = super().sizeHint()
        fm = self.fontMetrics()
        text_w = fm.horizontalAdvance(self.text()) + 12 if self.text() else 0
        size.setWidth(40 + text_w)
        size.setHeight(max(24, fm.height() + 6))
        return size

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def paintEvent(self, event):
        if self._anim.state() != QPropertyAnimation.State.Running:
            self._knob = 1.0 if self.isChecked() else 0.0
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = QRectF(1, (self.height() - 20) / 2, 36, 20)
        off, on = QColor(THEME["toggle_off"]), QColor(THEME["accent"])
        t = self._knob
        color = QColor(
            int(off.red() + (on.red() - off.red()) * t),
            int(off.green() + (on.green() - off.green()) * t),
            int(off.blue() + (on.blue() - off.blue()) * t),
        )
        if not self.isEnabled():
            color.setAlpha(110)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawRoundedRect(track, 10, 10)
        p.setBrush(QColor("white"))
        p.drawEllipse(QRectF(track.x() + 2 + t * 16, track.y() + 2, 16, 16))
        if self.text():
            p.setPen(self.palette().color(
                QPalette.ColorGroup.Normal if self.isEnabled() else QPalette.ColorGroup.Disabled,
                QPalette.ColorRole.WindowText,
            ))
            p.drawText(QRectF(48, 0, self.width() - 48, self.height()),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())
        p.end()


class PreviewLabel(QLabel):
    """Shows the VM screen scaled to fit; clicks are mapped back to VM pixels."""
    clicked = pyqtSignal(int, int, str)

    def __init__(self):
        super().__init__("No preview yet")
        self.setObjectName("preview")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.setMinimumSize(320, 240)
        self._pix: QPixmap | None = None

    def set_image(self, data: bytes):
        pix = QPixmap()
        if pix.loadFromData(data):
            self._pix = pix
            self._rescale()

    def clear_image(self, text: str):
        self._pix = None
        self.setText(text)

    def set_message(self, text: str):
        if self._pix is None:
            self.setText(text)

    def resizeEvent(self, event):
        self._rescale()
        super().resizeEvent(event)

    def _rescale(self):
        if self._pix:
            self.setPixmap(self._pix.scaled(
                self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))

    def mousePressEvent(self, event):
        shown = self.pixmap()
        if not self._pix or shown is None or shown.isNull():
            return
        ox = (self.width() - shown.width()) / 2
        oy = (self.height() - shown.height()) / 2
        px, py = event.position().x() - ox, event.position().y() - oy
        if not (0 <= px < shown.width() and 0 <= py < shown.height()):
            return
        x = int(px * self._pix.width() / shown.width())
        y = int(py * self._pix.height() / shown.height())
        button = {
            Qt.MouseButton.RightButton: "right",
            Qt.MouseButton.MiddleButton: "middle",
        }.get(event.button(), "left")
        self.clicked.emit(x, y, button)


class ListEditor(QWidget):
    """A list with an add box and a remove button."""

    def __init__(self, placeholder: str, numeric: bool = False):
        super().__init__()
        self.numeric = numeric
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list.setMinimumHeight(110)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
        if numeric:
            self.edit.setValidator(QRegularExpressionValidator(QRegularExpression(r"\d{0,20}")))
        self.edit.returnPressed.connect(self.add)

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self.edit, 1)
        row.addWidget(button("Add", self.add, "primary"))
        row.addWidget(button("Remove", self.remove))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.list)
        layout.addLayout(row)

    def add(self):
        text = self.edit.text().strip()
        if text and text not in self._texts():
            self.list.addItem(text)
        self.edit.clear()

    def remove(self):
        for item in self.list.selectedItems():
            self.list.takeItem(self.list.row(item))

    def _texts(self):
        return [self.list.item(i).text() for i in range(self.list.count())]

    def values(self):
        return [int(t) for t in self._texts()] if self.numeric else self._texts()

    def set_values(self, values):
        self.list.clear()
        self.list.addItems(str(v) for v in values)


class UpdateDialog(QDialog):
    """Shows what's new in a release and asks whether to install it."""

    def __init__(self, parent, release, config: Config):
        super().__init__(parent)
        self.config = config
        self.choice = "later"
        self.setWindowTitle(T("Update available"))
        self.setMinimumSize(520, 420)
        v = QVBoxLayout(self)
        v.setContentsMargins(22, 20, 22, 18)
        v.setSpacing(12)
        title = QLabel(T("Update available"))
        title.setObjectName("pageTitle")
        v.addWidget(title)
        v.addWidget(hint(T("Version {new} is available. You have {current}.")
                         .format(new=release.tag, current=f"v{__version__}")))
        notes = QTextBrowser()
        notes.setOpenExternalLinks(True)
        notes.setMarkdown(release.notes or "-")
        v.addWidget(QLabel("<b>" + html.escape(T("What's new")) + "</b>"))
        v.addWidget(notes, 1)
        v.addWidget(hint(T("Your settings are kept. The panel restarts after updating, "
                           "and if the bot is running it starts again by itself.")))
        self.auto = Toggle(T("Check for updates automatically"))
        self.auto.setChecked(config.auto_check_updates)
        self.auto.toggled.connect(lambda on: setattr(config, "auto_check_updates", on))
        v.addWidget(self.auto)
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(button(T("Skip this version"), lambda: self._done("skip")))
        row.addStretch()
        row.addWidget(button(T("Later"), lambda: self._done("later")))
        row.addWidget(button("⬆  " + T("Update now"), lambda: self._done("update"), "primary"))
        v.addLayout(row)

    def _done(self, choice: str):
        self.choice = choice
        self.accept()

    def exec_choice(self) -> str:
        self.exec()
        return self.choice


def button(text: str, slot, kind: str = "", tip: str = "") -> QPushButton:
    b = QPushButton(text)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if kind:
        b.setObjectName(kind)
    if tip:
        b.setToolTip(tip)
    b.clicked.connect(slot)
    return b


def id_edit(placeholder: str = "Channel ID") -> QLineEdit:
    e = QLineEdit()
    e.setPlaceholderText(placeholder)
    e.setValidator(QRegularExpressionValidator(QRegularExpression(r"\d{0,20}")))
    return e


def hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("hint")
    label.setWordWrap(True)
    return label


def form(group: QGroupBox) -> QFormLayout:
    f = QFormLayout(group)
    f.setHorizontalSpacing(16)
    f.setVerticalSpacing(12)
    f.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    return f


def stat_card(caption: str) -> tuple[QFrame, QLabel]:
    card = QFrame()
    card.setObjectName("card")
    v = QVBoxLayout(card)
    v.setContentsMargins(16, 12, 16, 12)
    v.setSpacing(2)
    cap = QLabel(caption.upper())
    cap.setObjectName("statLabel")
    value = QLabel("-")
    value.setObjectName("statValue")
    v.addWidget(cap)
    v.addWidget(value)
    return card, value


def page(title: str, subtitle: str, body: QWidget, scroll: bool = True) -> QWidget:
    """A page with a big title, a subtitle and the content below."""
    wrapper = QWidget()
    wrapper.setObjectName("page")
    v = QVBoxLayout(wrapper)
    v.setContentsMargins(28, 24, 28, 20)
    v.setSpacing(4)
    t = QLabel(title)
    t.setObjectName("pageTitle")
    s = QLabel(subtitle)
    s.setObjectName("pageSubtitle")
    v.addWidget(t)
    v.addWidget(s)
    v.addSpacing(14)
    body.setObjectName("page")
    if scroll:
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        area.setWidget(body)
        v.addWidget(area, 1)
    else:
        v.addWidget(body, 1)
    return wrapper


def vbox_layout(widget: QWidget, spacing: int = 16) -> QVBoxLayout:
    v = QVBoxLayout(widget)
    v.setContentsMargins(0, 0, 6, 0)
    v.setSpacing(spacing)
    return v


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

NAV = [
    (" ", "Dashboard"), (" ", "Discord"), (" ", "Virtual Machine"), (" ", "Commands"),
    (" ", "Moderation"), (" ", "Activity"), (" ", "Logs"),
]


class MainWindow(QMainWindow):
    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.vbox = VBox(config)
        self.pool = QThreadPool.globalInstance()
        self._tasks: set[Task] = set()
        self.bot_thread: BotThread | None = None
        self.bot_status = "offline"
        self.bot_started: datetime | None = None
        self.preview_busy = False
        self.log_entries: list[tuple[str, str, str]] = []
        self.usage: Counter[str] = Counter()
        self.total_commands = 0
        self.last_channels: list = []
        self.available_update: updater.Release | None = None
        self.update_prompted: set[str] = set()  # versions already offered this session

        self.signals = BotSignals()
        self.signals.log.connect(self.log)
        self.signals.command.connect(self.on_command)
        self.signals.status.connect(self.on_bot_status)
        self.signals.config_changed.connect(self.on_config_changed_by_bot)
        self.signals.channels.connect(self.on_channels)

        self.setWindowTitle(APP_NAME)
        self.resize(1320, 840)
        self.setMinimumSize(1000, 640)

        self.stack = QStackedWidget()
        pages = [
            page("Dashboard", "Watch the VM live and control it yourself.", self._build_dashboard(), scroll=False),
            page("Discord", "Bot account, channels and how the bot replies.", self._build_discord_tab()),
            page("Virtual Machine", "Pick the VM, manage power and snapshots.", self._build_vm_tab()),
            page("Commands", "Choose which commands people can use and set limits.", self._build_commands_tab()),
            page("Moderation", "Mods, bans and blocked keys or words.", self._build_moderation_tab()),
            page("Activity", "Every command people have run, and who runs the most.", self._build_activity_tab(), scroll=False),
            page("Logs", "Everything the bot and the panel did.", self._build_logs_tab(), scroll=False),
        ]
        for p in pages:
            self.stack.addWidget(p)

        root = QWidget()
        root.setObjectName("root")
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        h.addWidget(self._build_sidebar())
        h.addWidget(self.stack, 1)
        self.setCentralWidget(root)

        save = QAction(self, triggered=self.save_settings)
        save.setShortcut(QKeySequence.StandardKey.Save)
        self.addAction(save)
        self.go(0)

        self.populate()
        self.update_bot_ui()

        self.preview_timer = QTimer(self, timeout=self.refresh_preview)
        self.apply_preview_interval()
        self.preview_timer.start()
        QTimer(self, timeout=self.poll_vm_state, interval=5000).start()
        QTimer(self, timeout=self.tick, interval=1000).start()

        translate_tree(self)
        self.log("info", T("{app} started").format(app=APP_NAME) + f" (v{__version__})")
        self.check_vboxmanage()
        self.refresh_vms()
        # Look for updates shortly after start, then every 6 hours
        QTimer.singleShot(4000, lambda: self.check_updates(manual=False))
        QTimer(self, timeout=lambda: self.check_updates(manual=False), interval=6 * 3600 * 1000).start()

    # --- sidebar --------------------------------------------------------------

    def _build_sidebar(self) -> QFrame:
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(232)
        v = QVBoxLayout(side)
        v.setContentsMargins(14, 20, 14, 16)
        v.setSpacing(4)

        brand = QLabel("Uses VM")
        brand.setObjectName("brand")
        sub = QLabel("Discord control panel")
        sub.setObjectName("brandSub")
        v.addWidget(brand)
        v.addWidget(sub)
        vrow = QHBoxLayout()
        vrow.setSpacing(8)
        version = QLabel(f"v{__version__}")
        version.setObjectName("brandSub")
        vrow.addWidget(version)
        vrow.addWidget(button("Check for updates", lambda: self.check_updates(manual=True), "link"))
        vrow.addStretch()
        v.addLayout(vrow)
        v.addSpacing(18)
        section = QLabel("MENU")
        section.setObjectName("navSection")
        v.addWidget(section)
        v.addSpacing(4)

        self.nav = QButtonGroup(self)
        self.nav.setExclusive(True)
        for i, (icon, name) in enumerate(NAV):
            b = QPushButton(f"  {icon}   {name}")
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            self.nav.addButton(b, i)
            v.addWidget(b)
        self.nav.idClicked.connect(self.go)
        v.addStretch()

        self.update_btn = button("", lambda: self.show_update_dialog(self.available_update), "primary")
        self.update_btn.hide()
        v.addWidget(self.update_btn)
        v.addSpacing(6)
        self.sidebar_status = QLabel()
        self.sidebar_status.setObjectName("statusPill")
        v.addWidget(self.sidebar_status)
        v.addSpacing(8)
        self.btn_start = button("▶  Start bot", self.start_bot, "primary")
        self.btn_stop = button("■  Stop bot", self.stop_bot, "danger")
        v.addWidget(self.btn_start)
        v.addWidget(self.btn_stop)
        v.addSpacing(10)

        self.lock_toggle = Toggle("Lockdown")
        self.lock_toggle.setToolTip("When on, only mods can use commands")
        self.lock_toggle.toggled.connect(self.set_lockdown)
        v.addWidget(self.lock_toggle)
        self.theme_toggle = Toggle("Dark mode")
        self.theme_toggle.setChecked(self.config.dark_theme)
        self.theme_toggle.toggled.connect(self.set_theme)
        v.addWidget(self.theme_toggle)
        v.addSpacing(6)
        lrow = QHBoxLayout()
        lrow.setSpacing(8)
        lrow.addWidget(QLabel("🌐"))
        self.lang_combo = QComboBox()
        self.lang_combo.setToolTip("Language")
        for code, name in LANGUAGES.items():
            self.lang_combo.addItem(name, code)
        self.lang_combo.setCurrentIndex(max(0, self.lang_combo.findData(self.config.language)))
        self.lang_combo.currentIndexChanged.connect(self.set_ui_language)
        lrow.addWidget(self.lang_combo, 1)
        v.addLayout(lrow)
        v.addSpacing(8)
        v.addWidget(button("Save settings", self.save_settings, tip="Ctrl+S"))
        return side

    def go(self, index: int):
        self.stack.setCurrentIndex(index)
        self.nav.button(index).setChecked(True)
        if index == 0:
            self.refresh_preview(force=True)

    # --- dashboard ------------------------------------------------------------

    def _build_dashboard(self) -> QWidget:
        w = QWidget()
        v = vbox_layout(w)

        # Stat cards
        cards = QHBoxLayout()
        cards.setSpacing(12)
        for caption, attr in (("Bot", "lbl_bot"), ("VM", "lbl_vm"), ("Uptime", "lbl_uptime"),
                              ("Commands", "lbl_commands"), ("Users", "lbl_users"), ("Lockdown", "lbl_lock")):
            card, value = stat_card(caption)
            setattr(self, attr, value)
            cards.addWidget(card, 2 if attr == "lbl_vm" else 1)
        self.lbl_commands.setText("0")
        self.lbl_users.setText("0")
        v.addLayout(cards)

        # Preview card
        self.preview = PreviewLabel()
        self.preview.clicked.connect(self.preview_clicked)
        self.chk_autorefresh = Toggle("Auto refresh")
        self.chk_autorefresh.setChecked(True)
        self.chk_preview_control = Toggle("Click to control")
        self.chk_preview_control.setToolTip("Left/right/middle click on the preview clicks inside the VM")

        preview_box = QGroupBox("Live preview")
        pv = QVBoxLayout(preview_box)
        pv.setSpacing(10)
        top = QHBoxLayout()
        top.setSpacing(16)
        top.addWidget(self.chk_autorefresh)
        top.addWidget(self.chk_preview_control)
        top.addStretch()
        top.addWidget(button("Refresh", lambda: self.refresh_preview(force=True), "icon"))
        top.addWidget(button("Save image", self.save_screenshot, "icon"))
        pv.addLayout(top)
        pv.addWidget(self.preview, 1)

        self.local_type = QLineEdit()
        self.local_type.setPlaceholderText("Type text into the VM…")
        self.local_type.returnPressed.connect(self.local_send_text)
        self.local_key = QLineEdit()
        self.local_key.setPlaceholderText("Key combo, e.g. ctrl+alt+del")
        self.local_key.returnPressed.connect(self.local_send_key)
        trow = QHBoxLayout()
        trow.setSpacing(8)
        trow.addWidget(self.local_type, 3)
        trow.addWidget(button("Type", self.local_send_text))
        trow.addWidget(button("Send", lambda: self.local_send_text(enter=True), "primary",
                              tip="Type the text, then press Enter"))
        trow.addSpacing(8)
        trow.addWidget(self.local_key, 2)
        trow.addWidget(button("Press", self.local_send_key, "primary"))
        pv.addLayout(trow)

        qrow = QHBoxLayout()
        qrow.setSpacing(6)
        for label, combo in (("Win", "win"), ("Enter", "enter"), ("Esc", "esc"), ("Tab", "tab"),
                             ("Backspace", "backspace"), ("Alt+Tab", "alt+tab"), ("Alt+F4", "alt+f4"),
                             ("Ctrl+Alt+Del", "ctrl+alt+del"), ("Up", "up"), ("Down", "down"),
                             ("Left", "left"), ("Right", "right")):
            chip = button(label, lambda _=False, c=combo: self.send_combo(c), "chip", tip=combo)
            chip.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            qrow.addWidget(chip)
        qrow.addStretch()
        pv.addLayout(qrow)

        # Right column
        vm_box = QGroupBox("Quick actions")
        vg = QGridLayout(vm_box)
        vg.setSpacing(8)
        vg.addWidget(button("Start", self.vm_start), 0, 0)
        vg.addWidget(button("Shut down", lambda: self.vm_action("acpi_shutdown", "ACPI shutdown sent")), 0, 1)
        vg.addWidget(button("Pause", lambda: self.vm_action("pause", "VM paused")), 1, 0)
        vg.addWidget(button("Resume", lambda: self.vm_action("resume", "VM resumed")), 1, 1)
        vg.addWidget(button("Reset", lambda: self.vm_action("reset", "VM reset", confirm="Hard reset the VM?")), 2, 0)
        vg.addWidget(button("Power off", lambda: self.vm_action("poweroff", "VM powered off", confirm="Power off the VM?"), "danger"), 2, 1)
        vg.addWidget(button("Revert to clean snapshot", self.vm_revert, "primary"), 3, 0, 1, 2)

        ann_box = QGroupBox("Announce")
        al = QVBoxLayout(ann_box)
        al.setSpacing(8)
        al.addWidget(hint("Posts a message as the bot."))
        self.announce_target = QComboBox()
        self.announce_target.setToolTip("Where to send it. Channels appear once the bot is online.")
        trow = QHBoxLayout()
        trow.setSpacing(8)
        trow.addWidget(self.announce_target, 1)
        trow.addWidget(button("⟳", self.refresh_channels, "icon", tip="Reload channel list"))
        al.addLayout(trow)
        self.announce_edit = QPlainTextEdit()
        self.announce_edit.setPlaceholderText("Write a message…")
        self.announce_edit.setMaximumHeight(90)
        al.addWidget(self.announce_edit)
        al.addWidget(button("Send", self.announce, "primary"))
        self.on_channels([])

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(16)
        rv.addWidget(vm_box)
        rv.addWidget(ann_box)
        rv.addStretch()
        right.setMinimumWidth(280)
        right.setMaximumWidth(340)

        split = QSplitter()
        split.setChildrenCollapsible(False)
        split.addWidget(preview_box)
        split.addWidget(right)
        split.setStretchFactor(0, 1)
        v.addWidget(split, 1)
        return w

    # --- discord ----------------------------------------------------------------

    def _build_discord_tab(self) -> QWidget:
        w = QWidget()
        v = vbox_layout(w)

        bot = QGroupBox("Bot account")
        f = form(bot)
        self.token_edit = QLineEdit()
        self.token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_edit.setPlaceholderText("Paste your bot token")
        show = Toggle("Show")
        show.toggled.connect(lambda on: self.token_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password))
        trow = QHBoxLayout()
        trow.setSpacing(8)
        trow.addWidget(self.token_edit, 1)
        trow.addWidget(show)
        f.addRow("Token", trow)
        brow = QHBoxLayout()
        brow.setSpacing(8)
        brow.addWidget(button("Invite bot to server", self.open_invite, "primary"))
        brow.addWidget(button("Developer Portal ↗", lambda: QDesktopServices.openUrl(
            QUrl("https://discord.com/developers/applications"))))
        brow.addStretch()
        f.addRow("", brow)
        self.prefix_edit = QLineEdit()
        self.prefix_edit.setMaxLength(5)
        self.prefix_edit.setMaximumWidth(90)
        f.addRow("Command prefix", self.prefix_edit)
        self.status_edit = QLineEdit()
        self.status_edit.setPlaceholderText("Shown as 'Playing …' (empty = none)")
        f.addRow("Status text", self.status_edit)
        f.addRow(hint("The bot needs <b>Message Content Intent</b> turned on in the Developer Portal (Bot page)."))
        v.addWidget(bot)

        ch = QGroupBox("Channels")
        cf = form(ch)
        self.channels_editor = ListEditor("Channel ID (right-click channel → Copy Channel ID)", numeric=True)
        cf.addRow("Command channels", self.channels_editor)
        cf.addRow("", hint("Leave empty to accept commands in any channel."))
        self.chk_reply_ss = Toggle("Reply to commands with a screenshot")
        cf.addRow("", self.chk_reply_ss)
        v.addWidget(ch)

        logs = QGroupBox("Log channel")
        lf = form(logs)
        lf.addRow(hint("The bot posts a record of what happens to this channel, so mods can see "
                       "who did what. Make it private to mods."))
        self.log_channel_edit = id_edit("Channel ID")
        self.log_channel_edit.setMaximumWidth(220)
        self.log_channel_pick = QComboBox()
        self.log_channel_pick.setToolTip("Channels appear once the bot is online")
        self.log_channel_pick.activated.connect(self.on_log_channel_picked)
        crow = QHBoxLayout()
        crow.setSpacing(8)
        crow.addWidget(self.log_channel_edit)
        crow.addWidget(self.log_channel_pick, 1)
        crow.addWidget(button("Reload", self.refresh_channels, "icon", tip="Reload channel list"))
        lf.addRow("Channel", crow)
        trow = QHBoxLayout()
        trow.setSpacing(8)
        trow.addWidget(button("Send test message", self.send_test_log, "primary"))
        trow.addWidget(button("Clear", lambda: self.log_channel_edit.clear()))
        trow.addStretch()
        lf.addRow("", trow)

        what = QVBoxLayout()
        what.setSpacing(10)
        self.log_toggles: dict[str, Toggle] = {}
        for field, label in LOG_CATEGORIES.items():
            t = Toggle(label)
            self.log_toggles[field] = t
            what.addWidget(t)
        lf.addRow("Post", what)
        extra = QVBoxLayout()
        extra.setSpacing(10)
        self.chk_log_failed_only = Toggle("Only log commands that failed")
        self.chk_log_ss = Toggle("Attach the screenshot to each command entry")
        extra.addWidget(self.chk_log_failed_only)
        extra.addWidget(self.chk_log_ss)
        lf.addRow("Options", extra)
        v.addWidget(logs)

        live = QGroupBox("Live screen")
        lsf = form(live)
        lsf.addRow(hint("The bot keeps one message in this channel updated with a fresh screenshot, "
                        "so people can watch without typing commands. Leave empty to turn it off."))
        self.live_channel_edit = id_edit("Channel ID")
        self.live_channel_edit.setMaximumWidth(220)
        self.live_channel_pick = QComboBox()
        self.live_channel_pick.setToolTip("Channels appear once the bot is online")
        self.live_channel_pick.activated.connect(
            lambda i: self.live_channel_pick.itemData(i) and self.live_channel_edit.setText(
                str(self.live_channel_pick.itemData(i))))
        lrow = QHBoxLayout()
        lrow.setSpacing(8)
        lrow.addWidget(self.live_channel_edit)
        lrow.addWidget(self.live_channel_pick, 1)
        lrow.addWidget(button("Clear", lambda: self.live_channel_edit.clear()))
        lsf.addRow("Channel", lrow)
        self.live_interval_spin = QSpinBox()
        self.live_interval_spin.setRange(15, 3600)
        self.live_interval_spin.setSuffix(" s")
        self.live_interval_spin.setMaximumWidth(140)
        lsf.addRow("Update every", self.live_interval_spin)
        v.addWidget(live)
        self.on_channels([])
        v.addStretch()
        return w

    # --- virtual machine --------------------------------------------------------

    def _build_vm_tab(self) -> QWidget:
        w = QWidget()
        v = vbox_layout(w)

        vb = QGroupBox("VirtualBox")
        f = form(vb)
        self.vbox_path_edit = QLineEdit()
        self.vbox_path_edit.editingFinished.connect(self.on_vbox_path_changed)
        prow = QHBoxLayout()
        prow.setSpacing(8)
        prow.addWidget(self.vbox_path_edit, 1)
        prow.addWidget(button("Browse…", self.browse_vboxmanage))
        f.addRow("VBoxManage", prow)
        self.lbl_vbox_version = QLabel("?")
        f.addRow("Version", self.lbl_vbox_version)
        self.vm_combo = QComboBox()
        self.vm_combo.setMinimumWidth(250)
        self.vm_combo.currentTextChanged.connect(self.on_vm_selected)
        vrow = QHBoxLayout()
        vrow.setSpacing(8)
        vrow.addWidget(self.vm_combo, 1)
        vrow.addWidget(button("⟳  Refresh", self.refresh_vms))
        f.addRow("VM", vrow)
        self.start_mode_combo = QComboBox()
        self.start_mode_combo.addItems(["headless", "gui", "separate"])
        self.start_mode_combo.setToolTip("headless = no window (recommended), gui = normal window")
        f.addRow("Start mode", self.start_mode_combo)
        self.chk_start_on_launch = Toggle("Start the VM when the bot starts (if it's off)")
        f.addRow("", self.chk_start_on_launch)
        self.chk_watchdog = Toggle("Watchdog: start the VM again if it crashes or is shut down from inside")
        self.chk_watchdog.setToolTip("Not when you power it off from this panel")
        f.addRow("", self.chk_watchdog)
        v.addWidget(vb)

        kb = QGroupBox("Keyboard")
        kf = form(kb)
        kf.addRow(hint("Pick the keyboard layout that is set inside the VM (in its Windows settings), "
                       "so typed text and keys come out right, e.g. ş ğ ı on Turkish or æ ø å on Danish."))
        self.layout_combo = QComboBox()
        self.layout_combo.setProperty("i18n", True)
        for layout_id, name in keyboard_layouts.LAYOUT_NAMES.items():
            self.layout_combo.addItem(name, layout_id)
        self.layout_combo.currentIndexChanged.connect(self.on_layout_changed)
        self.layout_combo.setMaximumWidth(320)
        kf.addRow("VM keyboard layout", self.layout_combo)
        self.layout_test_edit = QLineEdit("Hello, World! @#$%&/()=?+*<> ğüşıöç İ æøå é 123")
        trow = QHBoxLayout()
        trow.setSpacing(8)
        trow.addWidget(self.layout_test_edit, 1)
        trow.addWidget(button("⌨  Test typing", self.test_layout, "primary",
                              tip="Open Notepad in the VM first, then press this"))
        kf.addRow("Test", trow)
        kf.addRow("", hint("Open Notepad in the VM, press Test typing, and check the text matches."))
        v.addWidget(kb)

        power = QGroupBox("Power")
        pg = QHBoxLayout(power)
        pg.setSpacing(8)
        pg.addWidget(button("Start", self.vm_start, "primary"))
        pg.addWidget(button("ACPI shutdown", lambda: self.vm_action("acpi_shutdown", "ACPI shutdown sent")))
        pg.addWidget(button("Reset", lambda: self.vm_action("reset", "VM reset", confirm="Hard reset the VM?")))
        pg.addWidget(button("Pause", lambda: self.vm_action("pause", "VM paused")))
        pg.addWidget(button("Resume", lambda: self.vm_action("resume", "VM resumed")))
        pg.addWidget(button("Power off", lambda: self.vm_action("poweroff", "VM powered off", confirm="Power off the VM?"), "danger"))
        v.addWidget(power)

        snaps = QGroupBox("Snapshots")
        sv = QVBoxLayout(snaps)
        sv.setSpacing(10)
        self.snap_list = QListWidget()
        self.snap_list.setMinimumHeight(130)
        self.snap_list.setMaximumHeight(180)
        sv.addWidget(self.snap_list)
        srow = QHBoxLayout()
        srow.setSpacing(8)
        srow.addWidget(button("Take snapshot", self.take_snapshot, "primary"))
        srow.addWidget(button("Restore selected", self.restore_selected_snapshot))
        srow.addWidget(button("Refresh", self.refresh_snapshots))
        srow.addStretch()
        sv.addLayout(srow)
        sf = QFormLayout()
        sf.setHorizontalSpacing(16)
        sf.setVerticalSpacing(12)
        self.revert_combo = QComboBox()
        self.revert_combo.setToolTip("Snapshot used by !revert, auto revert and the Revert button")
        sf.addRow("Revert to", self.revert_combo)
        self.auto_revert_spin = QSpinBox()
        self.auto_revert_spin.setRange(0, 24 * 60)
        self.auto_revert_spin.setSuffix(" min")
        self.auto_revert_spin.setSpecialValueText("Off")
        self.auto_revert_spin.setMaximumWidth(140)
        sf.addRow("Auto revert every", self.auto_revert_spin)
        sv.addLayout(sf)
        v.addWidget(snaps)

        info = QGroupBox("VM details")
        iv = QVBoxLayout(info)
        iv.setSpacing(10)
        self.vm_info_text = QPlainTextEdit()
        self.vm_info_text.setReadOnly(True)
        self.vm_info_text.setMinimumHeight(170)
        iv.addWidget(self.vm_info_text)
        irow = QHBoxLayout()
        irow.addWidget(hint(
            "Strangers control this VM: disable its network adapter, shared folders, shared "
            "clipboard and drag-and-drop, and set Pointing Device to <b>USB Tablet</b>."
        ), 1)
        irow.addWidget(button("Refresh details", self.refresh_vm_info))
        iv.addLayout(irow)
        v.addWidget(info)
        v.addStretch()
        return w

    # --- commands ---------------------------------------------------------------

    def _build_commands_tab(self) -> QWidget:
        w = QWidget()
        v = vbox_layout(w)

        cmds = QGroupBox("Enabled commands")
        cv = QVBoxLayout(cmds)
        cv.setSpacing(12)
        g = QGridLayout()
        g.setHorizontalSpacing(24)
        g.setVerticalSpacing(12)
        self.cmd_checks: dict[str, Toggle] = {}
        for i, name in enumerate(ALL_COMMANDS):
            chk = Toggle(self.command_label(name))
            self.cmd_checks[name] = chk
            g.addWidget(chk, i // 4, i % 4)
        cv.addLayout(g)
        crow = QHBoxLayout()
        crow.setSpacing(8)
        crow.addWidget(button("Enable all", lambda: [c.setChecked(True) for c in self.cmd_checks.values()]))
        crow.addWidget(button("Disable all", lambda: [c.setChecked(False) for c in self.cmd_checks.values()]))
        crow.addStretch()
        cv.addLayout(crow)
        v.addWidget(cmds)

        row = QHBoxLayout()
        row.setSpacing(16)
        lim = QGroupBox("Limits && timing")
        f = form(lim)
        self.cooldown_spin = QDoubleSpinBox()
        self.cooldown_spin.setRange(0, 600)
        self.cooldown_spin.setSuffix(" s")
        f.addRow("Cooldown per user", self.cooldown_spin)
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(0, 30)
        self.delay_spin.setSingleStep(0.5)
        self.delay_spin.setSuffix(" s")
        f.addRow("Wait before screenshot", self.delay_spin)
        self.max_type_spin = QSpinBox()
        self.max_type_spin.setRange(1, 2000)
        f.addRow("Max !type length", self.max_type_spin)
        self.max_repeat_spin = QSpinBox()
        self.max_repeat_spin.setRange(1, 100)
        f.addRow("Max key repeat / scroll", self.max_repeat_spin)
        self.max_chain_spin = QSpinBox()
        self.max_chain_spin.setRange(2, 50)
        self.max_chain_spin.setSuffix(" commands")
        f.addRow("Max chained per message", self.max_chain_spin)
        self.max_chain_wait_spin = QDoubleSpinBox()
        self.max_chain_wait_spin.setRange(0, 300)
        self.max_chain_wait_spin.setSuffix(" s")
        f.addRow("Max total !wait per chain", self.max_chain_wait_spin)
        row.addWidget(lim, 1)

        ss = QGroupBox("Screenshots")
        sf = form(ss)
        self.chk_grid = Toggle("Always draw the coordinate grid (otherwise only on !grid)")
        sf.addRow(self.chk_grid)
        self.grid_spin = QSpinBox()
        self.grid_spin.setRange(20, 500)
        self.grid_spin.setSingleStep(10)
        self.grid_spin.setSuffix(" px")
        sf.addRow("Grid size", self.grid_spin)
        self.preview_spin = QDoubleSpinBox()
        self.preview_spin.setRange(0.5, 60)
        self.preview_spin.setSingleStep(0.5)
        self.preview_spin.setSuffix(" s")
        sf.addRow("Panel preview refresh", self.preview_spin)
        row.addWidget(ss, 1)
        v.addLayout(row)

        votes = QGroupBox("Votes for revert and reboot")
        vf = form(votes)
        vf.addRow(hint("Anyone can start a vote. It passes when enough of the people active in the "
                       "command channels agree. Mods skip the vote and it happens instantly."))
        self.vote_ratio_spin = QSpinBox()
        self.vote_ratio_spin.setRange(1, 100)
        self.vote_ratio_spin.setSuffix(" % of active chatters")
        vf.addRow("Votes needed", self.vote_ratio_spin)
        self.vote_min_spin = QSpinBox()
        self.vote_min_spin.setRange(1, 100)
        self.vote_min_spin.setSuffix(" votes")
        vf.addRow("At least", self.vote_min_spin)
        self.vote_window_spin = QDoubleSpinBox()
        self.vote_window_spin.setRange(1, 240)
        self.vote_window_spin.setDecimals(0)
        self.vote_window_spin.setSuffix(" min")
        vf.addRow("Active = chatted in the last", self.vote_window_spin)
        self.vote_timeout_spin = QSpinBox()
        self.vote_timeout_spin.setRange(15, 3600)
        self.vote_timeout_spin.setSuffix(" s")
        vf.addRow("Vote expires after", self.vote_timeout_spin)
        self.vote_cooldown_spin = QSpinBox()
        self.vote_cooldown_spin.setRange(0, 3600)
        self.vote_cooldown_spin.setSuffix(" s")
        vf.addRow("Wait after a revert/reboot", self.vote_cooldown_spin)
        v.addWidget(votes)

        macros = QGroupBox("Macros")
        mv = QVBoxLayout(macros)
        mv.setSpacing(10)
        mv.addWidget(hint("Shortcuts anyone can run with !m <name>. Write the commands with ! and "
                          "chain them, e.g. !run cmd !wait 2 !send dir"))
        self.macro_table = QTableWidget(0, 2)
        self.macro_table.setHorizontalHeaderLabels(["Name", "Commands"])
        self.macro_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.macro_table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
        self.macro_table.verticalHeader().setVisible(False)
        self.macro_table.setShowGrid(False)
        self.macro_table.setColumnWidth(0, 160)
        self.macro_table.setMinimumHeight(200)
        mv.addWidget(self.macro_table)
        mrow = QHBoxLayout()
        mrow.setSpacing(8)
        mrow.addWidget(button("Add macro", self.add_macro_row, "primary"))
        mrow.addWidget(button("Remove", self.remove_macro_rows))
        mrow.addStretch()
        mv.addLayout(mrow)
        v.addWidget(macros)
        v.addStretch()
        return w

    # --- moderation -------------------------------------------------------------

    def _build_moderation_tab(self) -> QWidget:
        w = QWidget()
        g = QGridLayout(w)
        g.setContentsMargins(0, 0, 6, 0)
        g.setSpacing(16)

        mods = QGroupBox("Mods")
        mv = QVBoxLayout(mods)
        mv.setSpacing(10)
        mf = QFormLayout()
        self.mod_role_edit = QLineEdit()
        mf.addRow("Mod role name", self.mod_role_edit)
        mv.addLayout(mf)
        self.mods_editor = ListEditor("Mod user ID", numeric=True)
        mv.addWidget(self.mods_editor)
        mv.addWidget(hint("People with Manage Server are always mods. Mods skip cooldowns and blocks."))
        g.addWidget(mods, 0, 0)

        bans = QGroupBox("Banned users")
        bl = QVBoxLayout(bans)
        bl.setSpacing(10)
        self.bans_editor = ListEditor("User ID", numeric=True)
        bl.addWidget(self.bans_editor)
        bl.addWidget(hint("Banned users are ignored. Mods can also use !ban / !unban."))
        g.addWidget(bans, 0, 1)

        keys = QGroupBox("Blocked key combos")
        kl = QVBoxLayout(keys)
        kl.setSpacing(10)
        self.blocked_keys_editor = ListEditor("e.g. ctrl+alt+del, alt+f4")
        kl.addWidget(self.blocked_keys_editor)
        g.addWidget(keys, 1, 0)

        words = QGroupBox("Blocked words for type command")
        wl = QVBoxLayout(words)
        wl.setSpacing(10)
        self.blocked_words_editor = ListEditor("Word or phrase")
        wl.addWidget(self.blocked_words_editor)
        g.addWidget(words, 1, 1)
        g.setRowStretch(2, 1)
        return w

    # --- activity ---------------------------------------------------------------

    def _build_activity_tab(self) -> QWidget:
        self.history = QTableWidget(0, 5)
        self.history.setHorizontalHeaderLabels(["Time", "User", "User ID", "Command", "Result"])
        hh = self.history.horizontalHeader()
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        hh.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
        self.history.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.history.setAlternatingRowColors(True)
        self.history.setShowGrid(False)
        self.history.verticalHeader().setVisible(False)
        self.history.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.history.customContextMenuRequested.connect(self.history_menu)

        self.top_users = QTableWidget(0, 2)
        self.top_users.setHorizontalHeaderLabels(["User", "Commands"])
        self.top_users.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.top_users.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
        self.top_users.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.top_users.setShowGrid(False)
        self.top_users.verticalHeader().setVisible(False)

        left = QGroupBox("Command history")
        lv = QVBoxLayout(left)
        lv.setSpacing(10)
        lv.addWidget(hint("Right-click a row to ban the user, make them a mod, or copy their ID."))
        lv.addWidget(self.history)
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(button("Export CSV…", self.export_history))
        row.addWidget(button("Clear", lambda: self.history.setRowCount(0)))
        row.addStretch()
        lv.addLayout(row)

        right = QGroupBox("Top users")
        rv = QVBoxLayout(right)
        rv.addWidget(self.top_users)

        split = QSplitter()
        split.setChildrenCollapsible(False)
        split.addWidget(left)
        split.addWidget(right)
        split.setSizes([800, 300])
        return split

    # --- logs ---------------------------------------------------------------------

    def _build_logs_tab(self) -> QWidget:
        box = QGroupBox("Log")
        v = QVBoxLayout(box)
        v.setSpacing(10)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.log_filter = QComboBox()
        self.log_filter.setProperty("i18n", True)
        self.log_filter.addItems(["All", "Info", "Warnings & errors", "Errors"])
        self.log_filter.currentIndexChanged.connect(self.rerender_logs)
        row.addWidget(self.log_filter)
        self.log_search = QLineEdit()
        self.log_search.setPlaceholderText("Search logs…")
        self.log_search.textChanged.connect(self.rerender_logs)
        row.addWidget(self.log_search, 1)
        self.chk_log_file = Toggle("Save to logs/ folder")
        self.chk_log_file.setChecked(True)
        row.addSpacing(8)
        row.addWidget(self.chk_log_file)
        row.addWidget(button("Export…", self.export_logs))
        row.addWidget(button("Clear", self.clear_logs))
        v.addLayout(row)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(MAX_LOG_ENTRIES)
        mono = QFont("Cascadia Mono")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setPointSize(10)
        self.log_view.setFont(mono)
        v.addWidget(self.log_view)
        return box

    # -----------------------------------------------------------------------
    # Settings <-> widgets
    # -----------------------------------------------------------------------

    def populate(self):
        c = self.config
        self.token_edit.setText(c.token)
        self.prefix_edit.setText(c.prefix)
        self.status_edit.setText(c.status_text)
        self.channels_editor.set_values(c.command_channel_ids)
        self.log_channel_edit.setText(str(c.log_channel_id) if c.log_channel_id else "")
        self.chk_reply_ss.setChecked(c.reply_screenshot)
        self.chk_log_ss.setChecked(c.log_screenshots)
        self.chk_log_failed_only.setChecked(c.log_failed_only)
        for field, t in self.log_toggles.items():
            t.setChecked(getattr(c, field))

        self.vbox_path_edit.setText(c.vboxmanage)
        self.start_mode_combo.setCurrentText(c.start_mode)
        self.chk_start_on_launch.setChecked(c.start_vm_on_launch)
        self.auto_revert_spin.setValue(c.auto_revert_minutes)
        self._set_revert_options([], "")

        for name, chk in self.cmd_checks.items():
            chk.setChecked(name not in c.disabled_commands)
        self.cooldown_spin.setValue(c.cooldown)
        self.delay_spin.setValue(c.screenshot_delay)
        self.max_type_spin.setValue(c.max_type_len)
        self.max_repeat_spin.setValue(c.max_repeat)
        self.max_chain_spin.setValue(c.max_chain_steps)
        self.max_chain_wait_spin.setValue(c.max_chain_wait)
        self.chk_grid.setChecked(c.grid)
        self.grid_spin.setValue(c.grid_size)
        self.preview_spin.setValue(c.preview_interval)
        self.vote_ratio_spin.setValue(round(c.vote_ratio * 100))
        self.vote_min_spin.setValue(c.vote_min)
        self.vote_window_spin.setValue(c.vote_window_minutes)
        self.vote_timeout_spin.setValue(c.vote_timeout)
        self.vote_cooldown_spin.setValue(c.vote_cooldown)
        self.chk_watchdog.setChecked(c.watchdog)
        self.layout_combo.blockSignals(True)
        self.layout_combo.setCurrentIndex(max(0, self.layout_combo.findData(c.keyboard_layout)))
        self.layout_combo.blockSignals(False)
        self.live_channel_edit.setText(str(c.live_channel_id) if c.live_channel_id else "")
        self.live_interval_spin.setValue(c.live_interval)
        self.macro_table.setRowCount(0)
        for name, text in sorted(c.macros.items()):
            self.add_macro_row(name, text)

        self.populate_moderation()

    def add_macro_row(self, name: str = "", text: str = ""):
        row = self.macro_table.rowCount()
        self.macro_table.insertRow(row)
        self.macro_table.setItem(row, 0, QTableWidgetItem(name or ""))
        self.macro_table.setItem(row, 1, QTableWidgetItem(text or "!"))
        if not name:
            self.macro_table.editItem(self.macro_table.item(row, 0))

    def remove_macro_rows(self):
        for row in sorted({i.row() for i in self.macro_table.selectedIndexes()}, reverse=True):
            self.macro_table.removeRow(row)

    def collect_macros(self) -> dict[str, str]:
        macros, bad = {}, []
        for row in range(self.macro_table.rowCount()):
            name = (self.macro_table.item(row, 0).text() if self.macro_table.item(row, 0) else "").strip().lower()
            text = (self.macro_table.item(row, 1).text() if self.macro_table.item(row, 1) else "").strip()
            if not name and text in ("", "!"):
                continue  # empty row
            if not name or " " in name or not text.startswith("!") or text == "!":
                bad.append(name or "?")
                continue
            macros[name] = text
        if bad:
            self.log("warn", T("Ignoring macros that need a one-word name and commands starting with !: {names}")
                     .format(names=", ".join(bad)))
        return macros

    def populate_moderation(self):
        c = self.config
        self.mod_role_edit.setText(c.mod_role)
        self.mods_editor.set_values(c.mod_user_ids)
        self.bans_editor.set_values(c.banned_user_ids)
        self.blocked_keys_editor.set_values(c.blocked_keys)
        self.blocked_words_editor.set_values(c.blocked_words)
        self.lock_toggle.blockSignals(True)
        self.lock_toggle.setChecked(c.lockdown)
        self.lock_toggle.blockSignals(False)
        self.lock_toggle.update()

    def collect(self):
        c = self.config
        c.token = self.token_edit.text().strip()
        c.prefix = self.prefix_edit.text().strip() or "!"
        c.status_text = self.status_edit.text()
        c.command_channel_ids = self.channels_editor.values()
        c.log_channel_id = int(self.log_channel_edit.text() or 0)
        c.reply_screenshot = self.chk_reply_ss.isChecked()
        c.log_screenshots = self.chk_log_ss.isChecked()
        c.log_failed_only = self.chk_log_failed_only.isChecked()
        for field, t in self.log_toggles.items():
            setattr(c, field, t.isChecked())

        c.vboxmanage = self.vbox_path_edit.text().strip()
        if self.vm_combo.currentText():
            c.vm_name = self.vm_combo.currentText()
        c.start_mode = self.start_mode_combo.currentText()
        c.start_vm_on_launch = self.chk_start_on_launch.isChecked()
        c.revert_snapshot = self.revert_combo.currentData() or ""
        c.auto_revert_minutes = self.auto_revert_spin.value()

        c.disabled_commands = [n for n, chk in self.cmd_checks.items() if not chk.isChecked()]
        c.cooldown = self.cooldown_spin.value()
        c.screenshot_delay = self.delay_spin.value()
        c.max_type_len = self.max_type_spin.value()
        c.max_repeat = self.max_repeat_spin.value()
        c.max_chain_steps = self.max_chain_spin.value()
        c.max_chain_wait = self.max_chain_wait_spin.value()
        c.grid = self.chk_grid.isChecked()
        c.grid_size = self.grid_spin.value()
        c.preview_interval = self.preview_spin.value()
        c.vote_ratio = self.vote_ratio_spin.value() / 100
        c.vote_min = self.vote_min_spin.value()
        c.vote_window_minutes = self.vote_window_spin.value()
        c.vote_timeout = self.vote_timeout_spin.value()
        c.vote_cooldown = self.vote_cooldown_spin.value()
        c.watchdog = self.chk_watchdog.isChecked()
        c.keyboard_layout = self.layout_combo.currentData() or "us"
        new_live = int(self.live_channel_edit.text() or 0)
        if new_live != c.live_channel_id:
            c.live_message_id = 0  # new channel: post a fresh message there
        c.live_channel_id = new_live
        c.live_interval = self.live_interval_spin.value()
        c.macros = self.collect_macros()

        c.mod_role = self.mod_role_edit.text().strip()
        c.mod_user_ids = self.mods_editor.values()
        c.banned_user_ids = self.bans_editor.values()
        bad = []
        for combo in self.blocked_keys_editor.values():
            try:
                normalize_combo(combo)
            except VBoxError:
                bad.append(combo)
        if bad:
            self.log("warn", T("Ignoring unknown blocked key combos: {combos}").format(combos=", ".join(bad)))
        c.blocked_keys = [k for k in self.blocked_keys_editor.values() if k not in bad]
        c.blocked_words = self.blocked_words_editor.values()
        c.lockdown = self.lock_toggle.isChecked()

    def save_settings(self):
        self.collect()
        try:
            self.config.save()
        except OSError as e:
            QMessageBox.critical(self, APP_NAME, T("Couldn't save settings:\n{error}").format(error=e))
            return
        self.apply_preview_interval()
        for name, chk in self.cmd_checks.items():
            chk.setText(self.command_label(name))
        if self.bot_thread:
            self.bot_thread.call(lambda: self.bot_thread.bot.refresh_presence())
        self.log("ok", T("Settings saved and applied to the running bot") if self.bot_running
                 else T("Settings saved"))
        self.statusBar().showMessage("✓ " + T("Settings saved"), 3000)

    def on_config_changed_by_bot(self):
        # A mod used !lock / !ban etc. in Discord
        self.populate_moderation()
        self.update_lock_label()

    # -----------------------------------------------------------------------
    # Bot control
    # -----------------------------------------------------------------------

    @property
    def bot_running(self) -> bool:
        return self.bot_thread is not None and self.bot_thread.isRunning()

    def start_bot(self):
        if self.bot_running:
            return
        self.save_settings()
        if not self.config.token:
            QMessageBox.warning(self, APP_NAME, T("Enter your bot token on the Discord page first."))
            self.go(1)
            return
        if not self.config.vm_name:
            QMessageBox.warning(self, APP_NAME, T("Choose a VM on the Virtual Machine page first."))
            self.go(2)
            return
        self.bot_thread = BotThread(self.config, self.signals)
        self.bot_thread.finished.connect(self.update_bot_ui)
        self.bot_thread.start()
        self.on_bot_status("connecting")
        self.log("info", T("Starting bot…"))

    def stop_bot(self):
        if self.bot_running:
            self.log("info", T("Stopping bot…"))
            self.on_bot_status("stopping")
            self.bot_thread.stop()

    def on_bot_status(self, status: str):
        self.bot_status = status
        if status == "online":
            self.bot_started = datetime.now()
            self.log("ok", T("Bot is online"))
        elif status == "offline":
            self.bot_started = None
            self.on_channels([])
        self.update_bot_ui()

    def update_bot_ui(self):
        running = self.bot_running
        status = self.bot_status if running else "offline"
        color = {"online": THEME["success"], "connecting": THEME["warning"],
                 "stopping": THEME["warning"]}.get(status, THEME["danger"])
        dot = f"<span style='color:{color}; font-size:13pt'>●</span>"
        self.lbl_bot.setText(f"{dot} {T(status.capitalize())}")
        self.sidebar_status.setText(f"{dot}&nbsp; " + T("Bot {status}").format(status=T(status)))
        self.btn_start.setEnabled(not running)
        self.btn_stop.setEnabled(running)
        self.update_lock_label()

    def command_label(self, name: str) -> str:
        tag = "  · mod" if name in MOD_COMMANDS else f"  · {T('vote')}" if name in VOTE_COMMANDS else ""
        return f"{self.config.prefix}{name}{tag}"

    def update_lock_label(self):
        self.lbl_lock.setText(T("On") if self.config.lockdown else T("Off"))

    def set_ui_language(self, index: int):
        code = self.lang_combo.itemData(index)
        self.config.language = code
        self.config.save()
        set_language(code, QApplication.instance())
        self.retranslate()
        self.log("info", T("Language: {name}").format(name=LANGUAGES[code]))

    def retranslate(self):
        """Redo every text in the panel in the current language."""
        translate_tree(self)
        for name, chk in self.cmd_checks.items():
            chk.setText(self.command_label(name))
        self.update_bot_ui()
        self.poll_vm_state()
        self._set_revert_options([], self.config.revert_snapshot)  # refresh_snapshots refills it when a VM is set
        self.refresh_snapshots()
        self.refresh_vm_info()
        self.on_channels(self.last_channels)
        if self.preview._pix is None:
            self.preview.setText(T("No preview yet"))

    def set_lockdown(self, on: bool):
        self.config.lockdown = on
        self.config.save()
        self.update_lock_label()
        self.log("warn" if on else "info",
                 T("Lockdown on") if on else T("Lockdown off"))
        self.discord_log("Lockdown on (only mods can use commands)" if on else "Lockdown off",
                         "log_mod_actions")

    def discord_log(self, text: str, category: str = "log_vm_events"):
        """Post a panel action to the Discord log channel, if the bot is online."""
        if self.bot_running and self.bot_status == "online":
            self.bot_thread.call(lambda: self.bot_thread.bot.panel_event(text, category))

    def send_test_log(self):
        if not self.bot_running or self.bot_status != "online":
            QMessageBox.information(self, APP_NAME, T("Start the bot first and wait until it's online."))
            return
        if not self.log_channel_edit.text():
            QMessageBox.information(self, APP_NAME, T("Pick a log channel first."))
            return
        self.save_settings()  # so the bot uses the channel shown here
        self.bot_thread.call(lambda: self.bot_thread.bot.send_test_log())

    def on_log_channel_picked(self, index: int):
        cid = self.log_channel_pick.itemData(index)
        if cid:
            self.log_channel_edit.setText(str(cid))

    def set_theme(self, dark: bool):
        self.config.dark_theme = dark
        apply_theme(QApplication.instance(), dark)
        set_dark_titlebar(self, dark)
        self.update_bot_ui()
        self.config.save()

    def announce(self):
        text = self.announce_edit.toPlainText().strip()
        if not text:
            return
        if not self.bot_running or self.bot_status != "online":
            QMessageBox.information(self, APP_NAME, T("Start the bot first and wait until it's online."))
            return
        target = self.announce_target.currentData()
        if not target and not (self.config.command_channel_ids or self.config.log_channel_id):
            QMessageBox.information(self, APP_NAME, T(
                "Pick a channel to send to in the Announce box\n"
                "(or set command channels on the Discord page)."
            ))
            return
        ids = [target] if target else None
        if self.bot_thread.call(lambda: self.bot_thread.bot.announce(text, ids)):
            self.announce_edit.clear()
            self.log("info", T("Sending announcement…"))

    def refresh_channels(self):
        if not (self.bot_thread and self.bot_thread.call(self._emit_channels)):
            self.statusBar().showMessage(T("Start the bot to load channels"), 3000)

    async def _emit_channels(self):
        self.bot_thread.bot.emit_channels()

    def on_channels(self, channels: list):
        self.last_channels = channels
        current = self.announce_target.currentData()
        self.announce_target.clear()
        self.announce_target.addItem(T("Command channels (from settings)"), 0)
        for cid, name in sorted(channels, key=lambda c: c[1].lower()):
            self.announce_target.addItem(name, cid)
        idx = self.announce_target.findData(current)
        self.announce_target.setCurrentIndex(max(0, idx))

        if hasattr(self, "log_channel_pick"):
            self.log_channel_pick.clear()
            self.log_channel_pick.addItem(
                T("Pick a channel…") if channels else T("Start the bot to pick from a list"), 0)
            for cid, name in sorted(channels, key=lambda c: c[1].lower()):
                self.log_channel_pick.addItem(name, cid)
            idx = self.log_channel_pick.findData(int(self.log_channel_edit.text() or 0))
            self.log_channel_pick.setCurrentIndex(max(0, idx))

        if hasattr(self, "live_channel_pick"):
            self.live_channel_pick.clear()
            self.live_channel_pick.addItem(
                T("Pick a channel…") if channels else T("Start the bot to pick from a list"), 0)
            for cid, name in sorted(channels, key=lambda c: c[1].lower()):
                self.live_channel_pick.addItem(name, cid)
            idx = self.live_channel_pick.findData(int(self.live_channel_edit.text() or 0))
            self.live_channel_pick.setCurrentIndex(max(0, idx))

    def open_invite(self):
        token = self.token_edit.text().strip()
        try:
            part = token.split(".")[0]
            client_id = base64.b64decode(part + "=" * (-len(part) % 4)).decode()
            int(client_id)
        except Exception:
            QMessageBox.warning(self, APP_NAME, T("Enter a valid bot token first."))
            return
        QDesktopServices.openUrl(QUrl(
            f"https://discord.com/oauth2/authorize?client_id={client_id}"
            f"&permissions={INVITE_PERMISSIONS}&scope=bot"
        ))

    # -----------------------------------------------------------------------
    # Activity
    # -----------------------------------------------------------------------

    def on_command(self, user: str, user_id: str, text: str, ok: bool, result: str):
        self.total_commands += 1
        self.usage[user] += 1

        self.history.insertRow(0)
        values = [datetime.now().strftime("%H:%M:%S"), user, user_id, text, result]
        for col, val in enumerate(values):
            item = QTableWidgetItem(val)
            if not ok:
                item.setForeground(QColor(LEVEL_COLORS["error"]))
            self.history.setItem(0, col, item)
        if self.history.rowCount() > 2000:
            self.history.removeRow(self.history.rowCount() - 1)

        top = self.usage.most_common(50)
        self.top_users.setRowCount(len(top))
        for i, (name, n) in enumerate(top):
            self.top_users.setItem(i, 0, QTableWidgetItem(name))
            count = QTableWidgetItem()
            count.setData(Qt.ItemDataRole.DisplayRole, n)
            self.top_users.setItem(i, 1, count)
        self.lbl_commands.setText(str(self.total_commands))
        self.lbl_users.setText(str(len(self.usage)))
        if ok:
            # The VM just changed; refresh the preview soon
            QTimer.singleShot(300, lambda: self.refresh_preview(force=True))

    def history_menu(self, pos):
        row = self.history.rowAt(pos.y())
        if row < 0:
            return
        user = self.history.item(row, 1).text()
        uid = self.history.item(row, 2).text()
        menu = QMenu(self)
        menu.addAction(T("Ban {user}").format(user=user),
                       lambda: self.add_id_to(self.bans_editor, uid, "Banned {user}", user))
        menu.addAction(T("Make {user} a mod").format(user=user),
                       lambda: self.add_id_to(self.mods_editor, uid, "{user} is now a mod", user))
        menu.addSeparator()
        menu.addAction(T("Copy user ID"), lambda: QApplication.clipboard().setText(uid))
        menu.addAction(T("Copy command"),
                       lambda: QApplication.clipboard().setText(self.history.item(row, 3).text()))
        menu.exec(self.history.viewport().mapToGlobal(pos))

    def add_id_to(self, editor: ListEditor, uid: str, message: str, user: str):
        if uid not in [str(v) for v in editor.values()]:
            editor.list.addItem(uid)
        self.save_settings()
        self.log("warn", T(message).format(user=user))
        self.discord_log(message.format(user=user), "log_mod_actions")  # Discord log stays English

    def export_history(self):
        path, _ = QFileDialog.getSaveFileName(self, T("Export history"), "history.csv", "CSV (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Time", "User", "User ID", "Command", "Result"])
            for r in range(self.history.rowCount()):
                writer.writerow([self.history.item(r, c).text() for c in range(5)])
        self.log("ok", T("History exported to {path}").format(path=path))

    # -----------------------------------------------------------------------
    # Logs
    # -----------------------------------------------------------------------

    def log(self, level: str, message: str):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_entries.append((ts, level, message))
        del self.log_entries[:-MAX_LOG_ENTRIES]
        if self._log_visible(level, message):
            self.log_view.appendHtml(self._log_html(ts, level, message))
        if level == "error":
            self.statusBar().showMessage(f"⚠  {message}", 6000)
        if self.chk_log_file.isChecked():
            try:
                LOG_DIR.mkdir(exist_ok=True)
                with open(LOG_DIR / f"{ts[:10]}.log", "a", encoding="utf-8") as f:
                    f.write(f"{ts} [{level.upper()}] {message}\n")
            except OSError:
                pass

    def _log_visible(self, level: str, message: str) -> bool:
        mode = self.log_filter.currentIndex()
        if mode == 1 and level not in ("info", "ok"):
            return False
        if mode == 2 and level not in ("warn", "error"):
            return False
        if mode == 3 and level != "error":
            return False
        q = self.log_search.text().strip().lower()
        return not q or q in message.lower()

    @staticmethod
    def _log_html(ts: str, level: str, message: str) -> str:
        color = LEVEL_COLORS.get(level, "#9aa0aa")
        return (f"<span style='color:#6b7079'>{ts[11:]}</span>&nbsp;&nbsp;"
                f"<span style='color:{color}'><b>{level.upper():5}</b></span>&nbsp;&nbsp;"
                f"{html.escape(message)}")

    def rerender_logs(self):
        self.log_view.clear()
        for ts, level, message in self.log_entries:
            if self._log_visible(level, message):
                self.log_view.appendHtml(self._log_html(ts, level, message))

    def clear_logs(self):
        self.log_entries.clear()
        self.log_view.clear()

    def export_logs(self):
        path, _ = QFileDialog.getSaveFileName(self, T("Export logs"), "vm-bot.log", "Log files (*.log *.txt)")
        if path:
            Path(path).write_text(
                "\n".join(f"{ts} [{lvl.upper()}] {msg}" for ts, lvl, msg in self.log_entries),
                encoding="utf-8",
            )
            self.log("ok", T("Logs exported to {path}").format(path=path))

    # -----------------------------------------------------------------------
    # VirtualBox (all calls run in the thread pool)
    # -----------------------------------------------------------------------

    def run_task(self, fn, *args, done=None, error=None, quiet=False):
        task = Task(fn, *args)
        self._tasks.add(task)

        def on_done(result):
            self._tasks.discard(task)
            if done:
                done(result)

        def on_error(message):
            self._tasks.discard(task)
            if not quiet:
                self.log("error", message)
            if error:
                error(message)

        task.signals.done.connect(on_done)
        task.signals.error.connect(on_error)
        self.pool.start(task)

    def check_vboxmanage(self):
        def done(version):
            self.lbl_vbox_version.setText(f"<span style='color:{THEME['success']}'>●</span> {version}")

        def error(message):
            self.lbl_vbox_version.setText(f"<span style='color:{THEME['danger']}'>●</span> {html.escape(message)}")

        self.run_task(self.vbox.version, done=done, error=error, quiet=True)

    def browse_vboxmanage(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Find VBoxManage", self.vbox_path_edit.text(),
            "VBoxManage (VBoxManage*);;All files (*)",
        )
        if path:
            self.vbox_path_edit.setText(path)
            self.on_vbox_path_changed()

    def on_vbox_path_changed(self):
        self.config.vboxmanage = self.vbox_path_edit.text().strip()
        self.check_vboxmanage()
        self.refresh_vms()

    def refresh_vms(self):
        def done(vms):
            wanted = self.config.vm_name
            self.vm_combo.blockSignals(True)
            self.vm_combo.clear()
            self.vm_combo.addItems(vms)
            if wanted and wanted not in vms:
                self.vm_combo.addItem(wanted)  # keep the saved choice visible
            self.vm_combo.blockSignals(False)
            if wanted:
                self.vm_combo.setCurrentText(wanted)
            elif vms:
                self.vm_combo.setCurrentIndex(0)
            self.on_vm_selected(self.vm_combo.currentText())
            self.log("info", T("Found {n} VM(s)").format(n=len(vms)))

        self.run_task(self.vbox.list_vms, done=done)

    def on_vm_selected(self, name: str):
        if not name:
            return
        if name != self.config.vm_name:
            self.config.vm_name = name
            self.log("info", T("Selected VM: {name}").format(name=name))
        self.preview.clear_image(T("Loading preview…"))
        self.refresh_snapshots()
        self.refresh_vm_info()
        self.poll_vm_state()
        self.refresh_preview(force=True)

    def poll_vm_state(self):
        if not self.config.vm_name:
            self.lbl_vm.setText(T("No VM selected"))
            return

        def done(state):
            color = {"running": THEME["success"], "paused": THEME["warning"]}.get(state, THEME["muted"])
            self.lbl_vm.setText(
                f"<span style='color:{color}; font-size:13pt'>●</span> "
                f"{html.escape(self.config.vm_name)} <span style='color:{THEME['muted']}; "
                f"font-size:10pt; font-weight:500'>{T(state)}</span>"
            )

        def error(message):
            self.lbl_vm.setText(f"<span style='color:{THEME['danger']}; font-size:13pt'>●</span> {T('unavailable')}")

        self.run_task(self.vbox.state, done=done, error=error, quiet=True)

    def refresh_vm_info(self):
        if not self.config.vm_name:
            return
        keys = [
            ("name", "Name"), ("ostype", "OS"), ("VMState", "State"), ("memory", "Memory (MB)"),
            ("cpus", "CPUs"), ("vram", "Video memory (MB)"), ("graphicscontroller", "Graphics"),
            ("nic1", "Network adapter 1"), ("clipboard", "Shared clipboard"),
            ("draganddrop", "Drag and drop"), ("pointingdevice", "Pointing device"),
            ("CfgFile", "Config file"),
        ]

        def done(info):
            lines = [f"{T(label):<22}{info.get(k, '?')}" for k, label in keys]
            warnings = []
            if info.get("nic1", "none") not in ("none", "null"):
                warnings.append(T("Network is enabled: anything people do online comes from your IP."))
            if info.get("clipboard", "disabled") != "disabled":
                warnings.append(T("Shared clipboard is on."))
            if info.get("draganddrop", "disabled") != "disabled":
                warnings.append(T("Drag and drop is on."))
            if any(k.startswith("SharedFolderName") for k in info):
                warnings.append(T("The VM has shared folders."))
            if info.get("pointingdevice") not in (None, "usbtablet", "usbmultitouch", "usbmtscreenpluspad"):
                warnings.append(T("Pointing device isn't USB Tablet; clicks may not work without Guest Additions."))
            self.vm_info_text.setPlainText("\n".join(lines + ([""] + warnings if warnings else [])))

        self.run_task(self.vbox.info, done=done, quiet=True)

    def refresh_snapshots(self):
        if not self.config.vm_name:
            return

        def done(result):
            names, current = result
            self.snap_list.clear()
            for n in names:
                self.snap_list.addItem(f"★  {n}   {T('(current)')}" if n == current else f"     {n}")
                self.snap_list.item(self.snap_list.count() - 1).setData(Qt.ItemDataRole.UserRole, n)
            self._set_revert_options(names, self.config.revert_snapshot)
            if not names:
                self.snap_list.addItem(T("No snapshots yet. Take one of a clean state for !revert."))

        self.run_task(self.vbox.snapshots, done=done, quiet=True)

    def _set_revert_options(self, names: list[str], selected: str):
        self.revert_combo.clear()
        self.revert_combo.addItem(T("(current snapshot)"), "")
        for n in names:
            self.revert_combo.addItem(n, n)
        if selected and selected not in names:
            self.revert_combo.addItem(selected, selected)
        idx = self.revert_combo.findData(selected)
        self.revert_combo.setCurrentIndex(max(0, idx))

    def take_snapshot(self):
        name, ok = QInputDialog.getText(self, T("Take snapshot"), T("Snapshot name:"),
                                        text=f"Clean {datetime.now():%Y-%m-%d %H%M}")
        if ok and name.strip():
            self.log("info", T("Taking snapshot '{name}'…").format(name=name))
            self.run_task(self.vbox.take_snapshot, name.strip(),
                          done=lambda _: (self.log("ok", T("Snapshot '{name}' taken").format(name=name)),
                                          self.refresh_snapshots(),
                                          self.discord_log(f"📸 Snapshot '{name}' taken")))

    def restore_selected_snapshot(self):
        item = self.snap_list.currentItem()
        name = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not name:
            QMessageBox.information(self, APP_NAME, T("Select a snapshot first."))
            return
        if QMessageBox.question(self, APP_NAME, T("Power off the VM and restore '{name}'?").format(name=name)) \
                != QMessageBox.StandardButton.Yes:
            return
        self.log("info", T("Restoring '{name}'…").format(name=name))
        self.hold_watchdog()
        self.run_task(self.vbox.revert, name, self.start_mode_combo.currentText(),
                      done=lambda _: (self.log("ok", T("Restored '{name}'").format(name=name)),
                                      self.refresh_snapshots(),
                                      self.discord_log(f"Restored snapshot '{name}'"),
                                      QTimer.singleShot(4000, lambda: self.refresh_preview(force=True))))

    def vm_start(self):
        mode = self.start_mode_combo.currentText()
        self.log("info", T("Starting VM ({mode})…").format(mode=mode))
        self.run_task(self.vbox.start, mode, done=lambda _: (
            self.log("ok", T("VM started")), self.poll_vm_state(), self.discord_log("VM started")))

    def vm_action(self, method: str, message: str, confirm: str = ""):
        # message is English for the Discord log; the panel shows it translated
        if confirm and QMessageBox.question(self, APP_NAME, T(confirm)) != QMessageBox.StandardButton.Yes:
            return
        if method in ("poweroff", "acpi_shutdown"):
            self.hold_watchdog()
        self.run_task(getattr(self.vbox, method),
                      done=lambda _: (self.log("ok", T(message)), self.poll_vm_state(), self.discord_log(message),
                                      QTimer.singleShot(1000, lambda: self.refresh_preview(force=True))))

    def on_layout_changed(self, index: int):
        # Applies right away, also to a running bot (it reads the same settings)
        self.config.keyboard_layout = self.layout_combo.itemData(index) or "us"
        self.config.save()
        self.log("info", T("VM keyboard layout: {name}").format(
            name=T(keyboard_layouts.layout_name(self.config.keyboard_layout))))

    def test_layout(self):
        text = self.layout_test_edit.text()
        missing = keyboard_layouts.unsupported(text, self.config.keyboard_layout)
        typeable = "".join(ch for ch in text if ch not in missing)
        if not typeable:
            return
        if missing:
            self.log("warn", T("Skipped characters this layout can't type: {chars}").format(chars=" ".join(missing)))
        self.run_task(self.vbox.send_text, typeable, done=lambda _: (
            self.log("ok", T("Typed the test text. Check it matches in the VM.")),
            QTimer.singleShot(500, lambda: self.refresh_preview(force=True))))

    def hold_watchdog(self):
        """The VM is being powered off on purpose: the bot's watchdog shouldn't start it again."""
        if self.bot_thread and self.bot_thread.bot:
            self.bot_thread.bot.watchdog_hold = True

    def vm_revert(self):
        snap = self.revert_combo.currentData() or ""
        label = f"'{snap}'" if snap else "the current snapshot"  # English, for the Discord log
        shown = f"'{snap}'" if snap else T("the current snapshot")
        if QMessageBox.question(self, APP_NAME, T("Power off the VM and revert to {label}?").format(label=shown)) \
                != QMessageBox.StandardButton.Yes:
            return
        self.log("info", T("Reverting to {label}…").format(label=shown))
        self.hold_watchdog()

        def done(_):
            self.log("ok", T("Reverted"))
            self.discord_log(f"Reverted to {label}")
            if self.bot_thread and self.bot_thread.bot:
                self.bot_thread.bot.last_revert = time.monotonic()
                self.bot_thread.bot.votes.clear()
            self.poll_vm_state()
            QTimer.singleShot(5000, lambda: self.refresh_preview(force=True))

        self.run_task(self.vbox.revert, snap, self.start_mode_combo.currentText(), done=done)

    # --- preview & local control ---------------------------------------------

    def apply_preview_interval(self):
        if hasattr(self, "preview_timer"):
            self.preview_timer.setInterval(int(self.config.preview_interval * 1000))

    def refresh_preview(self, force: bool = False):
        if self.preview_busy or not self.config.vm_name or not hasattr(self, "preview"):
            return
        if not force and (not self.chk_autorefresh.isChecked() or self.stack.currentIndex() != 0
                          or self.isMinimized()):
            return
        self.preview_busy = True

        def done(data):
            self.preview_busy = False
            self.preview.set_image(data)

        def error(message):
            self.preview_busy = False
            self.preview.set_message(f"{T('No preview')}\n{message}")

        self.run_task(self.vbox.screenshot, done=done, error=error, quiet=True)

    def save_screenshot(self):
        path, _ = QFileDialog.getSaveFileName(
            self, T("Save screenshot"), f"vm-{datetime.now():%Y%m%d-%H%M%S}.png", "PNG (*.png)")
        if path:
            self.run_task(self.vbox.screenshot, done=lambda data: (
                Path(path).write_bytes(data), self.log("ok", T("Saved {path}").format(path=path))))

    def preview_clicked(self, x: int, y: int, button_name: str):
        if not self.chk_preview_control.isChecked():
            return
        self.run_task(self.vbox.click, x, y, button_name,
                      done=lambda _: QTimer.singleShot(400, lambda: self.refresh_preview(force=True)))

    def send_combo(self, combo: str):
        try:
            normalize_combo(combo)
        except VBoxError as e:
            QMessageBox.warning(self, APP_NAME, str(e))
            return
        self.run_task(self.vbox.send_combo, combo,
                      done=lambda _: QTimer.singleShot(400, lambda: self.refresh_preview(force=True)))

    def local_send_key(self):
        combo = self.local_key.text().strip()
        if combo:
            self.send_combo(combo)
            self.local_key.clear()

    def local_send_text(self, enter: bool = False):
        text = self.local_type.text()
        if not text and not enter:
            return

        def type_it():
            if text:
                self.vbox.send_text(text)
            if enter:
                self.vbox.send_combo("enter")

        self.run_task(type_it, done=lambda _: QTimer.singleShot(400, lambda: self.refresh_preview(force=True)))
        self.local_type.clear()

    # --- misc -----------------------------------------------------------------

    # --- updates ------------------------------------------------------------------

    def check_updates(self, manual: bool):
        if not manual and not self.config.auto_check_updates:
            return

        def done(release):
            if release is None:
                self.update_btn.hide()
                if manual:
                    QMessageBox.information(self, APP_NAME, T("You have the latest version ({version}).")
                                            .format(version=f"v{__version__}"))
                return
            self.available_update = release
            self.update_btn.setText("⬆  " + T("Update to {version}").format(version=release.tag))
            self.update_btn.show()
            self.log("info", T("Update available: {version}").format(version=release.tag))
            # Pop up once per version per session, unless the user skipped that version
            if manual or (release.version != self.config.skipped_version
                          and release.version not in self.update_prompted):
                self.update_prompted.add(release.version)
                self.show_update_dialog(release)

        def error(message):
            self.log("warn", T("Couldn't check for updates:\n{error}").format(error=message).replace("\n", " "))
            if manual:
                QMessageBox.warning(self, APP_NAME, T("Couldn't check for updates:\n{error}").format(error=message))

        self.run_task(updater.newer_release, done=done, error=error, quiet=True)

    def show_update_dialog(self, release):
        if release is None:
            return
        dialog = UpdateDialog(self, release, self.config)
        choice = dialog.exec_choice()
        self.config.save()  # the "check automatically" switch
        if choice == "update":
            self.install_update(release)
        elif choice == "skip":
            self.config.skipped_version = release.version
            self.config.save()
            self.update_btn.hide()

    def install_update(self, release):
        was_running = self.bot_running
        progress = QProgressDialog(T("Downloading and installing {version}…").format(version=release.tag),
                                   "", 0, 0, self)
        progress.setWindowTitle(APP_NAME)
        progress.setCancelButton(None)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()
        self.log("info", T("Downloading and installing {version}…").format(version=release.tag))

        def done(report):
            progress.close()
            self.log("ok", T("Updated to {version}: {n} files, backup in {backup}")
                     .format(version=release.tag, n=report["files"], backup=report["backup"]))
            if report["deps"].startswith("failed"):
                QMessageBox.warning(self, APP_NAME, T("Updated, but installing new Python packages failed:\n{error}\n\n"
                                                      "Run: pip install -r requirements.txt")
                                    .format(error=report["deps"]))
            QMessageBox.information(self, APP_NAME, T("Updated to {version}. The panel will now restart.")
                                    .format(version=release.tag))
            self.restart_panel(start_bot=was_running)

        def error(message):
            progress.close()
            self.log("error", T("Update failed:\n{error}").format(error=message).replace("\n", " "))
            QMessageBox.critical(self, APP_NAME, T("Update failed:\n{error}").format(error=message))

        self.run_task(updater.install, release, done=done, error=error, quiet=True)

    def restart_panel(self, start_bot: bool):
        """Start a fresh copy of the panel (running the new code) and close this one."""
        self.collect()
        self.config.save()
        args = [str(Path(__file__).resolve())] + (["--start-bot"] if start_bot else [])
        QProcess.startDetached(sys.executable, args, str(Path(__file__).resolve().parent))
        self.close()

    def tick(self):
        if self.bot_started and self.bot_status == "online":
            secs = int((datetime.now() - self.bot_started).total_seconds())
            h, rem = divmod(secs, 3600)
            m, s = divmod(rem, 60)
            self.lbl_uptime.setText(f"{h:02}:{m:02}:{s:02}")
        else:
            self.lbl_uptime.setText("-")

    def showEvent(self, event):
        super().showEvent(event)
        set_dark_titlebar(self, self.config.dark_theme)

    def closeEvent(self, event):
        self.collect()
        try:
            self.config.save()
        except OSError:
            pass
        if self.bot_running:
            self.bot_thread.stop()
            self.bot_thread.wait(5000)
        self.pool.waitForDone(3000)
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    font = QFont()
    font.setFamilies(["Segoe UI Variable Text", "Segoe UI", "Inter", "Arial"])
    font.setPointSize(10)
    app.setFont(font)
    config = Config.load()
    set_language(config.language, app)
    apply_theme(app, config.dark_theme)
    window = MainWindow(config)
    window.show()
    if "--start-bot" in sys.argv:
        # Restarted after an update while the bot was running: start it again once the
        # old panel has had time to disconnect
        QTimer.singleShot(6000, window.start_bot)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
