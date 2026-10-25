"""Settings shared by the bot and the GUI, stored in config.json next to this file."""
import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

CONFIG_PATH = Path(__file__).with_name("config.json")
DEFAULT_VBOXMANAGE = r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe"

PUBLIC_COMMANDS = [
    "key", "combo", "type", "send", "click", "move", "drag", "scroll",
    "screen", "grid", "wait", "chain", "startvm", "keys", "help", "vminfo", "stats",
]
# Anyone can vote for these; a mod's vote runs them instantly
VOTE_COMMANDS = ["revert", "reboot"]
MOD_COMMANDS = ["lock", "unlock", "ban", "unban"]
ALL_COMMANDS = PUBLIC_COMMANDS + VOTE_COMMANDS + MOD_COMMANDS

# What gets posted to the log channel: config field -> label in the GUI
LOG_CATEGORIES = {
    "log_commands": "Commands people run",
    "log_blocked": "Blocked attempts (bans, lockdown, blocked keys/words, disabled commands)",
    "log_mod_actions": "Mod actions (lock, ban, instant revert/reboot)",
    "log_bot_status": "Bot online / offline",
    "log_vm_events": "VM events (auto revert, power and snapshot actions from the panel)",
    "log_announcements": "Announcements",
}


@dataclass
class Config:
    # Discord
    token: str = ""
    prefix: str = "!"
    command_channel_ids: list[int] = field(default_factory=list)  # empty = any channel
    log_channel_id: int = 0
    status_text: str = "Discord Uses VM | !help"
    reply_screenshot: bool = True

    # Log channel
    log_screenshots: bool = False
    log_failed_only: bool = False  # only log commands that failed
    log_commands: bool = True
    log_blocked: bool = True
    log_mod_actions: bool = True
    log_bot_status: bool = True
    log_vm_events: bool = True
    log_announcements: bool = True

    # VirtualBox
    vboxmanage: str = DEFAULT_VBOXMANAGE
    vm_name: str = ""
    start_vm_on_launch: bool = True
    start_mode: str = "headless"  # headless | gui | separate
    revert_snapshot: str = ""  # empty = current snapshot
    auto_revert_minutes: int = 0  # 0 = off

    # Commands & limits
    disabled_commands: list[str] = field(default_factory=list)
    cooldown: float = 3.0
    screenshot_delay: float = 1.5
    max_type_len: int = 200
    max_repeat: int = 20
    max_chain_steps: int = 10  # commands per message when chaining
    max_chain_wait: float = 30  # total !wait seconds per chained message
    grid: bool = False  # always draw the grid; otherwise only on !grid
    grid_size: int = 100

    # Votes for !revert / !reboot
    vote_ratio: float = 0.5  # share of active chatters needed
    vote_min: int = 1  # never fewer votes than this
    vote_window_minutes: float = 10  # "active" = sent a message in a command channel this recently
    vote_timeout: int = 120  # seconds before an unfinished vote resets
    vote_cooldown: int = 60  # seconds after a revert/reboot before a new vote can start

    # Moderation
    mod_role: str = "VM Mod"
    mod_user_ids: list[int] = field(default_factory=list)
    banned_user_ids: list[int] = field(default_factory=list)
    blocked_keys: list[str] = field(default_factory=list)  # e.g. "ctrl+alt+del"
    blocked_words: list[str] = field(default_factory=list)
    lockdown: bool = False  # only mods can use commands

    # GUI
    preview_interval: float = 2.0
    dark_theme: bool = True
    language: str = "en"  # control panel language: en | da

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "Config":
        cfg = cls()
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            known = {f.name for f in fields(cls)}
            for k, v in data.items():
                if k in known:
                    setattr(cfg, k, v)
        return cfg

    def save(self, path: Path = CONFIG_PATH) -> None:
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
