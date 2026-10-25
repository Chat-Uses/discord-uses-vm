"""VirtualBox control through VBoxManage (keyboard, screenshots, power, snapshots)
and the COM API (mouse)."""
import io
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Keyboard: PS/2 scancode set 1. (extended, make_code); break code = make | 0x80
# ---------------------------------------------------------------------------

KEYS = {
    "esc": (False, 0x01), "backspace": (False, 0x0E), "tab": (False, 0x0F),
    "enter": (False, 0x1C), "ctrl": (False, 0x1D), "shift": (False, 0x2A),
    "rshift": (False, 0x36), "alt": (False, 0x38), "space": (False, 0x39),
    "capslock": (False, 0x3A), "numlock": (False, 0x45), "scrolllock": (False, 0x46),
    "-": (False, 0x0C), "=": (False, 0x0D), "[": (False, 0x1A), "]": (False, 0x1B),
    ";": (False, 0x27), "'": (False, 0x28), "`": (False, 0x29), "\\": (False, 0x2B),
    ",": (False, 0x33), ".": (False, 0x34), "/": (False, 0x35),
    # extended keys (E0 prefix)
    "rctrl": (True, 0x1D), "ralt": (True, 0x38), "home": (True, 0x47),
    "up": (True, 0x48), "pageup": (True, 0x49), "left": (True, 0x4B),
    "right": (True, 0x4D), "end": (True, 0x4F), "down": (True, 0x50),
    "pagedown": (True, 0x51), "insert": (True, 0x52), "delete": (True, 0x53),
    "win": (True, 0x5B), "rwin": (True, 0x5C), "menu": (True, 0x5D),
    "printscreen": (True, 0x37),
}
for i, ch in enumerate("1234567890"):
    KEYS[ch] = (False, 0x02 + i)
for row, start in (("qwertyuiop", 0x10), ("asdfghjkl", 0x1E), ("zxcvbnm", 0x2C)):
    for i, ch in enumerate(row):
        KEYS[ch] = (False, start + i)
for i in range(10):
    KEYS[f"f{i + 1}"] = (False, 0x3B + i)
KEYS["f11"] = (False, 0x57)
KEYS["f12"] = (False, 0x58)

ALIASES = {
    "windows": "win", "super": "win", "start": "win", "meta": "win", "lwin": "win",
    "control": "ctrl", "ctl": "ctrl", "lctrl": "ctrl", "lshift": "shift",
    "lalt": "alt", "altgr": "ralt", "return": "enter", "escape": "esc",
    "del": "delete", "ins": "insert", "bksp": "backspace", "bs": "backspace",
    "pgup": "pageup", "pgdn": "pagedown", "pgdown": "pagedown", "caps": "capslock",
    "prtsc": "printscreen", "spacebar": "space", "apps": "menu",
}


class VBoxError(Exception):
    pass


def canonical_key(name: str) -> str:
    name = name.strip().lower()
    name = ALIASES.get(name, name)
    if name not in KEYS:
        raise VBoxError(f"Unknown key `{name}`")
    return name


def normalize_combo(combo: str) -> str:
    """'Control+Alt+Del' -> 'alt+ctrl+delete', so blocked combos match in any order."""
    return "+".join(sorted(canonical_key(k) for k in combo.split("+") if k.strip()))


def combo_scancodes(combo: str) -> list[str]:
    """Press every key in order, then release them in reverse (e.g. ctrl+alt+del)."""
    resolved = [KEYS[canonical_key(k)] for k in combo.split("+") if k.strip()]
    if not resolved:
        raise VBoxError("No key given")
    codes = []
    for ext, code in resolved:
        codes += (["E0"] if ext else []) + [f"{code:02X}"]
    for ext, code in reversed(resolved):
        codes += (["E0"] if ext else []) + [f"{code | 0x80:02X}"]
    return codes


def add_grid(png: bytes, size: int = 100) -> bytes:
    """Overlay a coordinate grid so people can aim clicks."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return png
    size = max(20, size)
    img = Image.open(io.BytesIO(png)).convert("RGB")
    draw = ImageDraw.Draw(img, "RGBA")
    w, h = img.size
    for x in range(size, w, size):
        draw.line([(x, 0), (x, h)], fill=(255, 0, 0, 60))
        draw.text((x + 2, 2), str(x), fill=(255, 40, 40, 255))
    for y in range(size, h, size):
        draw.line([(0, y), (w, y)], fill=(255, 0, 0, 60))
        draw.text((2, y + 2), str(y), fill=(255, 40, 40, 255))
    out = io.BytesIO()
    img.save(out, "PNG")
    return out.getvalue()


# Don't flash a console window for every VBoxManage call when run from the GUI
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


class VBox:
    """Reads the VBoxManage path and VM name from the config on every call,
    so changing them in the GUI takes effect immediately."""

    def __init__(self, config):
        self.config = config

    @property
    def vm(self) -> str:
        if not self.config.vm_name:
            raise VBoxError("No VM selected")
        return self.config.vm_name

    def run(self, *args: str, timeout: float = 60) -> str:
        try:
            result = subprocess.run(
                [self.config.vboxmanage, *args],
                capture_output=True, text=True, timeout=timeout,
                creationflags=NO_WINDOW,
            )
        except FileNotFoundError:
            raise VBoxError(f"VBoxManage not found at {self.config.vboxmanage}")
        except subprocess.TimeoutExpired:
            raise VBoxError("VBoxManage timed out")
        if result.returncode != 0:
            msg = (result.stderr or result.stdout).strip().splitlines()
            msg = [m for m in msg if not m.startswith("VBoxManage: error: Details")]
            raise VBoxError(
                (msg[0] if msg else f"VBoxManage failed ({result.returncode})")
                .replace("VBoxManage: error: ", "")
            )
        return result.stdout

    # --- info -------------------------------------------------------------

    def version(self) -> str:
        return self.run("--version", timeout=10).strip()

    def list_vms(self) -> list[str]:
        return re.findall(r'^"(.+)" \{[^}]+\}$', self.run("list", "vms"), re.M)

    def info(self) -> dict[str, str]:
        data = {}
        for line in self.run("showvminfo", self.vm, "--machinereadable").splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                data[k.strip('"')] = v.strip('"')
        return data

    def state(self) -> str:
        return self.info().get("VMState", "unknown")

    # --- power ------------------------------------------------------------

    def start(self, mode: str = "headless") -> None:
        self.run("startvm", self.vm, "--type", mode)

    def poweroff(self) -> None:
        self.run("controlvm", self.vm, "poweroff")

    def acpi_shutdown(self) -> None:
        self.run("controlvm", self.vm, "acpipowerbutton")

    def reset(self) -> None:
        self.run("controlvm", self.vm, "reset")

    def pause(self) -> None:
        self.run("controlvm", self.vm, "pause")

    def resume(self) -> None:
        self.run("controlvm", self.vm, "resume")

    # --- snapshots ----------------------------------------------------------

    def snapshots(self) -> tuple[list[str], str]:
        try:
            out = self.run("snapshot", self.vm, "list", "--machinereadable")
        except VBoxError as e:
            if "does not have any snapshots" in str(e):
                return [], ""
            raise
        names, current = [], ""
        for line in out.splitlines():
            k, _, v = line.partition("=")
            v = v.strip('"')
            if k.startswith("SnapshotName"):
                names.append(v)
            elif k == "CurrentSnapshotName":
                current = v
        return names, current

    def take_snapshot(self, name: str) -> None:
        self.run("snapshot", self.vm, "take", name, timeout=300)

    def revert(self, snapshot: str = "", mode: str = "headless") -> None:
        """Power off, restore a snapshot (or the current one), start again."""
        if self.state() in ("running", "paused", "stuck"):
            self.poweroff()
        # The session takes a moment to unlock after poweroff
        for attempt in range(15):
            try:
                if snapshot:
                    self.run("snapshot", self.vm, "restore", snapshot, timeout=300)
                else:
                    self.run("snapshot", self.vm, "restorecurrent", timeout=300)
                break
            except VBoxError:
                if attempt == 14:
                    raise
                time.sleep(1)
        self.start(mode)

    # --- input / output ---------------------------------------------------------

    def screenshot(self) -> bytes:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "screen.png"
            self.run("controlvm", self.vm, "screenshotpng", str(path))
            return path.read_bytes()

    def send_combo(self, combo: str, times: int = 1) -> None:
        self.run("controlvm", self.vm, "keyboardputscancode", *(combo_scancodes(combo) * times))

    def send_text(self, text: str) -> None:
        self.run("controlvm", self.vm, "keyboardputstring", text)

    def mouse(self, events: list[tuple[int, int, int, int]]) -> None:
        """Send (x, y, wheel, buttons) events through the VirtualBox COM API.

        buttons bitmask: 1 = left, 2 = right, 4 = middle. Needs pywin32 and
        the VM's pointing device set to "USB Tablet" (or Guest Additions).
        """
        try:
            import pythoncom
            import win32com.client
        except ImportError:
            raise VBoxError("Mouse needs pywin32: pip install pywin32")

        pythoncom.CoInitialize()
        try:
            client = win32com.client.Dispatch("VirtualBox.VirtualBoxClient")
            machine = client.VirtualBox.FindMachine(self.vm)
            session = client.Session
            machine.LockMachine(session, 1)  # LockType.Shared
            try:
                mouse = session.Console.Mouse
                if not mouse.AbsoluteSupported:
                    raise VBoxError(
                        "Guest doesn't support absolute mouse. Set Pointing Device "
                        "to USB Tablet or install Guest Additions."
                    )
                for x, y, wheel, buttons in events:
                    # VirtualBox absolute coordinates are 1-based
                    mouse.PutMouseEventAbsolute(x + 1, y + 1, wheel, 0, buttons)
                    time.sleep(0.05)
            finally:
                session.UnlockMachine()
        except VBoxError:
            raise
        except Exception as e:
            raise VBoxError(f"Mouse error: {e}")
        finally:
            pythoncom.CoUninitialize()

    def click(self, x: int, y: int, button: str = "left") -> None:
        seq = {"left": [1, 0], "right": [2, 0], "middle": [4, 0], "double": [1, 0, 1, 0]}
        if button not in seq:
            raise VBoxError("Button must be left, right, middle or double")
        self.mouse([(x, y, 0, 0)] + [(x, y, 0, b) for b in seq[button]])

    def drag(self, x1: int, y1: int, x2: int, y2: int, steps: int = 10) -> None:
        events = [(x1, y1, 0, 0), (x1, y1, 0, 1)]
        for i in range(1, steps + 1):
            events.append((x1 + (x2 - x1) * i // steps, y1 + (y2 - y1) * i // steps, 0, 1))
        events.append((x2, y2, 0, 0))
        self.mouse(events)

    def scroll(self, x: int, y: int, amount: int) -> None:
        """amount > 0 scrolls down, < 0 scrolls up."""
        step = 1 if amount > 0 else -1
        self.mouse([(x, y, 0, 0)] + [(x, y, step, 0)] * abs(amount))
