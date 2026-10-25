r"""Keyboard layouts of the VM's guest OS.

VirtualBox sends physical key presses (scancodes). Which character a key produces depends on the
keyboard layout set inside the VM, so to type "ş" on Turkish Q we must press the key where
US keyboards have ";". Each layout below lists the character on every physical key for three
layers: no modifier, Shift and AltGr.

Rows, left to right (PS/2 set 1 scancodes):
  number row  `  1  2  3  4  5  6  7  8  9  0  -  =        (13 keys)
  top row     q  w  e  r  t  y  u  i  o  p  [  ]           (12)
  home row    a  s  d  f  g  h  j  k  l  ;  '  # / \       (12; last is the key next to Enter)
  bottom row  <  z  x  c  v  b  n  m  ,  .  /              (11; first is the extra ISO key)
"□" means the key has nothing on that layer.
"""
import unicodedata

ROWS = [
    [0x29, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D],
    [0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x1B],
    [0x1E, 0x1F, 0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2B],
    [0x56, 0x2C, 0x2D, 0x2E, 0x2F, 0x30, 0x31, 0x32, 0x33, 0x34, 0x35],
]
NONE = "□"
SPACE, ENTER, TAB = 0x39, 0x1C, 0x0F

# Combining accent -> dead key that types it (for é, ñ, ü… on layouts that compose them)
ACCENTS = {"\u0301": "´", "\u0300": "`", "\u0302": "^", "\u0308": "¨", "\u0303": "~"}

_RAW = {
    "us": ("English (US)", "", {
        "": ["`1234567890-=", "qwertyuiop[]", "asdfghjkl;'\\", "□zxcvbnm,./"],
        "shift": ["~!@#$%^&*()_+", "QWERTYUIOP{}", "ASDFGHJKL:\"|", "□ZXCVBNM<>?"],
    }),
    "uk": ("English (UK)", "", {
        "": ["`1234567890-=", "qwertyuiop[]", "asdfghjkl;'#", "\\zxcvbnm,./"],
        "shift": ["¬!\"£$%^&*()_+", "QWERTYUIOP{}", "ASDFGHJKL:@~", "|ZXCVBNM<>?"],
        "altgr": ["¦□□□€□□□□□□□□", "□□é□□□úíó□□□", "á□□□□□□□□□□□", "□□□□□□□□□□□"],
    }),
    "da": ("Danish", "´`¨^~", {
        "": ["½1234567890+´", "qwertyuiopå¨", "asdfghjklæø'", "<zxcvbnm,.-"],
        "shift": ["§!\"#¤%&/()=?`", "QWERTYUIOPÅ^", "ASDFGHJKLÆØ*", ">ZXCVBNM;:_"],
        "altgr": ["□□@£$€□{[]}□|", "□□€□□□□□□□□~", "□□□□□□□□□□□□", "\\□□□□□□µ□□□"],
    }),
    "de": ("German", "^´`", {
        "": ["^1234567890ß´", "qwertzuiopü+", "asdfghjklöä#", "<yxcvbnm,.-"],
        "shift": ["°!\"§$%&/()=?`", "QWERTZUIOPÜ*", "ASDFGHJKLÖÄ'", ">YXCVBNM;:_"],
        "altgr": ["□□²³□□□{[]}\\□", "@□€□□□□□□□□~", "□□□□□□□□□□□□", "|□□□□□□µ□□□"],
    }),
    "fr": ("French (AZERTY)", "^¨~`", {
        "": ["²&é\"'(-è_çà)=", "azertyuiop^$", "qsdfghjklmù*", "<wxcvbn,;:!"],
        "shift": ["□1234567890°+", "AZERTYUIOP¨£", "QSDFGHJKLM%µ", ">WXCVBN?./§"],
        "altgr": ["□□~#{[|`\\^@]}", "□□€□□□□□□□□¤", "□□□□□□□□□□□□", "□□□□□□□□□□□"],
    }),
    "tr_q": ("Turkish Q", "^¨~´`", {
        "": ["\"1234567890*-", "qwertyuıopğü", "asdfghjklşi,", "<zxcvbnmöç."],
        "shift": ["é!'^+%&/()=?_", "QWERTYUIOPĞÜ", "ASDFGHJKLŞİ;", ">ZXCVBNMÖÇ:"],
        "altgr": ["<>£#$½□{[]}\\|", "@□€□₺□□□□□¨~", "æß□□□□□□□´□`", "|□□□□□□□□□□"],
    }),
    "tr_f": ("Turkish F", "^", {
        "": ["+1234567890/-", "fgğıodrnhpqw", "uieaütkmlyşx", "<jövcçzsb.,"],
        "shift": ["*!\"^$%&'()=?_", "FGĞIODRNHPQW", "UİEAÜTKMLYŞX", ">JÖVCÇZSB:;"],
        "altgr": ["¬¹²#¼½¾{[]}\\|", "@□□□□□□□□□□□", "□□□□□□□□□□□□", "|□□□□□□□□□□"],
    }),
}


def _build():
    layouts = {}
    for layout_id, (name, dead, layers) in _RAW.items():
        chars: dict[str, tuple[int, str]] = {}  # char -> (scancode, layer)
        for layer, rows in layers.items():
            for row_codes, text in zip(ROWS, rows):
                if len(text) != len(row_codes):
                    raise ValueError(f"{layout_id} {layer or 'base'} row {text!r} has {len(text)} keys, "
                                     f"expected {len(row_codes)}")
                for code, ch in zip(row_codes, text):
                    if ch != NONE and ch not in chars:
                        chars[ch] = (code, layer)
        layouts[layout_id] = {"name": name, "chars": chars, "dead": set(dead)}
    return layouts


LAYOUTS = _build()
LAYOUT_NAMES = {k: v["name"] for k, v in LAYOUTS.items()}


def _layout(layout_id: str) -> dict:
    return LAYOUTS.get(layout_id) or LAYOUTS["us"]


def layout_name(layout_id: str) -> str:
    return _layout(layout_id)["name"]


def _press(code: int, layer: str = "") -> list[str]:
    before, after = {"shift": (["2A"], ["AA"]), "altgr": (["E0", "38"], ["E0", "B8"])}.get(layer, ([], []))
    return before + [f"{code:02X}", f"{code | 0x80:02X}"] + after


def base_key(char: str, layout_id: str) -> int | None:
    """The physical key that types `char` without Shift/AltGr (for shortcuts like ctrl+c)."""
    hit = _layout(layout_id)["chars"].get(char)
    return hit[0] if hit and hit[1] == "" else None


def char_scancodes(char: str, layout_id: str) -> list[str] | None:
    """Key presses that type one character, or None if the layout can't type it."""
    if char == " ":
        return _press(SPACE)
    if char == "\n":
        return _press(ENTER)
    if char == "\t":
        return _press(TAB)
    layout = _layout(layout_id)
    chars = layout["chars"]
    if char in chars:
        codes = _press(*chars[char])
        if char in layout["dead"]:
            codes += _press(SPACE)  # a dead key on its own: press space to get the character
        return codes
    # Accented letter typed with a dead key, e.g. é = ´ then e
    decomposed = unicodedata.normalize("NFD", char)
    if len(decomposed) == 2 and decomposed[1] in ACCENTS:
        dead = ACCENTS[decomposed[1]]
        if dead in layout["dead"] and dead in chars and decomposed[0] in chars:
            return _press(*chars[dead]) + _press(*chars[decomposed[0]])
    return None


def unsupported(text: str, layout_id: str) -> list[str]:
    """Characters in text that the layout can't type (each listed once)."""
    missing = []
    for ch in text:
        if ch not in missing and char_scancodes(ch, layout_id) is None:
            missing.append(ch)
    return missing


def text_scancodes(text: str, layout_id: str) -> list[str]:
    codes = []
    for ch in text:
        seq = char_scancodes(ch, layout_id)
        if seq is None:
            raise ValueError(ch)
        codes += seq
    return codes
