"""The Discord bot: runs commands on the VM, then replies with a screenshot."""
import asyncio
import io
import math
import re
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

import discord
from discord.ext import commands

from config import MOD_COMMANDS, VOTE_COMMANDS, Config
from vbox_control import ALIASES, KEYS, VBox, VBoxError, add_grid, normalize_combo


class Events:
    """Hooks the GUI overrides. The default just prints (headless mode)."""

    def log(self, level: str, message: str) -> None:
        print(f"[{level}] {message}")

    def command(self, user: str, user_id: int, text: str, ok: bool, result: str) -> None:
        pass

    def status(self, status: str) -> None:
        pass

    def config_changed(self) -> None:
        pass

    def channels(self, channels: list[tuple[int, str]]) -> None:
        """Text channels the bot can post in: [(id, "Server / #name"), ...]"""
        pass


class Denied(commands.CheckFailure):
    """A check failure the user should be told about."""


@dataclass
class Step:
    """One VM action from a command; a chain is a list of these."""
    label: str
    action: Callable[[], None] | None  # blocking VirtualBox call
    wait: float = 0.0  # seconds to sleep afterwards (!wait)
    snapshot: bool = False  # take a screenshot at this point (!screen / !grid)
    grid: bool = False


# Commands that can be chained in one message, e.g. "!combo win+r !wait 2 !send notepad"
CHAINABLE = ["key", "combo", "type", "send", "click", "move", "drag", "scroll", "wait", "screen", "grid"]

USAGE = {
    "key": "{p}key <key> [times]",
    "combo": "{p}combo <key+key…> [times]",
    "type": "{p}type <text>",
    "send": "{p}send <text>",
    "click": "{p}click <x> <y> [left|right|middle|double]",
    "move": "{p}move <x> <y>",
    "drag": "{p}drag <x1> <y1> <x2> <y2>",
    "scroll": "{p}scroll <up|down> [amount] [x y]",
    "wait": "{p}wait [seconds]",
    "screen": "{p}screen",
    "grid": "{p}grid",
}


def _cooldown(ctx: commands.Context):
    # Mods skip the cooldown
    if ctx.bot.is_mod(ctx.author):
        return None
    return commands.Cooldown(1, ctx.bot.config.cooldown)


cooldown = commands.dynamic_cooldown(_cooldown, commands.BucketType.user)


def mod_only():
    async def predicate(ctx: commands.Context) -> bool:
        if not ctx.bot.is_mod(ctx.author):
            raise Denied("🛡️ Mods only.")
        return True
    return commands.check(predicate)


def fmt_duration(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h {m}m {s}s" if h else f"{m}m {s}s"


class VMBot(commands.Bot):
    def __init__(self, config: Config, events: Events | None = None):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(
            command_prefix=lambda bot, message: bot.config.prefix,
            intents=intents,
            help_command=None,
            case_insensitive=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        self.config = config
        self.events = events or Events()
        self.vbox = VBox(config)
        self.vm_lock = asyncio.Lock()  # one action at a time so screenshots match
        self.usage: Counter[str] = Counter()
        self.total_commands = 0
        self.started_at = time.time()
        self.last_revert = time.monotonic()
        self._auto_revert_task = None
        self._blocked_logged: dict[int, float] = {}  # user id -> last time, to avoid log spam
        self.chatters: dict[int, float] = {}  # user id -> last message in a command channel
        self.votes: dict[str, dict] = {}  # "revert"/"reboot" -> {"voters": set, "started": t}
        self.last_vote_action: dict[str, float] = {}  # for the cooldown after a revert/reboot

    # --- lifecycle ------------------------------------------------------------

    async def setup_hook(self) -> None:
        await self.add_cog(VMCog(self))
        self._auto_revert_task = asyncio.create_task(self._auto_revert_loop())

    async def on_ready(self) -> None:
        self.events.log("info", f"Logged in as {self.user} (ID {self.user.id})")
        self.events.status("online")
        self.emit_channels()
        await self.refresh_presence()
        if self.config.start_vm_on_launch and self.config.vm_name:
            try:
                state = await asyncio.to_thread(self.vbox.state)
                if state != "running":
                    self.events.log("info", f"VM is '{state}', starting it ({self.config.start_mode})")
                    await asyncio.to_thread(self.vbox.start, self.config.start_mode)
            except VBoxError as e:
                self.events.log("warn", f"Couldn't start VM: {e}")
        await self.log_event(
            "log_bot_status", f"🟢 **Bot online**, controlling **{self.config.vm_name or '?'}**",
            discord.Color.green(),
        )

    async def close(self) -> None:
        if self._auto_revert_task:
            self._auto_revert_task.cancel()
        if self.is_ready() and not self.is_closed():
            try:
                await asyncio.wait_for(self.log_event(
                    "log_bot_status", "🔴 **Bot offline**", discord.Color.red()), timeout=5)
            except Exception:
                pass
        self.events.status("offline")
        await super().close()

    async def refresh_presence(self) -> None:
        text = self.config.status_text.strip()
        await self.change_presence(activity=discord.Game(text) if text else None)

    async def on_message(self, message: discord.Message) -> None:
        if (not message.author.bot and self.in_command_channel(message.channel)
                and message.author.id not in self.config.banned_user_ids):
            self.chatters[message.author.id] = time.monotonic()
        if message.author.bot:
            return
        segments = self.split_chain(message.content)
        if segments and len(segments) > 1:
            # Several commands in one message: run them through the hidden !chain command,
            # so the usual checks (channel, ban, lockdown, cooldown) still apply
            ctx = await self.get_context(message)
            ctx.command = self.get_command("chain")
            ctx.invoked_with = segments[0][0]
            await self.invoke(ctx)
            return
        await self.process_commands(message)

    def split_chain(self, content: str) -> list[tuple[str, str]] | None:
        """'!combo win+r !wait 2 !send hi' -> [('combo', 'win+r'), ('wait', '2'), ('send', 'hi')].
        Returns None if the text doesn't start with a chainable command."""
        names = {}
        for canonical in CHAINABLE:
            cmd = self.get_command(canonical)
            if cmd is None:
                continue
            for n in [cmd.name, *cmd.aliases]:
                names[n.lower()] = canonical
        if not names:
            return None
        p = re.escape(self.config.prefix)
        alternatives = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
        # A command starts at the beginning or after whitespace, and ends at whitespace or the end
        pattern = re.compile(rf"(?:^|(?<=\s)){p}({alternatives})(?=\s|$)", re.IGNORECASE)
        content = content.strip()
        matches = list(pattern.finditer(content))
        if not matches or matches[0].start() != 0:
            return None
        segments = []
        for i, m in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            segments.append((names[m.group(1).lower()], content[m.end():end].strip()))
        return segments

    # --- votes --------------------------------------------------------------------

    def in_command_channel(self, channel) -> bool:
        ids = self.config.command_channel_ids
        return not ids or channel.id in ids

    def active_users(self) -> int:
        """People who sent a message in a command channel within the activity window."""
        cutoff = time.monotonic() - self.config.vote_window_minutes * 60
        self.chatters = {uid: t for uid, t in self.chatters.items() if t >= cutoff}
        return len(self.chatters)

    def votes_needed(self) -> int:
        active = max(1, self.active_users())
        return max(1, self.config.vote_min, math.ceil(active * self.config.vote_ratio))

    def vote_status(self, action: str) -> str:
        vote = self.votes.get(action)
        if not vote or time.monotonic() - vote["started"] > self.config.vote_timeout:
            return "no vote"
        return f"{len(vote['voters'])}/{self.votes_needed()}"

    # --- helpers ----------------------------------------------------------------

    def is_mod(self, user) -> bool:
        if user.id in self.config.mod_user_ids:
            return True
        if isinstance(user, discord.Member):
            return user.guild_permissions.manage_guild or any(
                r.name == self.config.mod_role for r in user.roles
            )
        return False

    async def get_channel_safe(self, channel_id: int):
        if not channel_id:
            return None
        channel = self.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.fetch_channel(channel_id)
            except discord.HTTPException as e:
                self.events.log("warn", f"Can't access channel {channel_id}: {e}")
                return None
        return channel

    async def send_log(self, **kwargs) -> bool:
        channel = await self.get_channel_safe(self.config.log_channel_id)
        if channel is None:
            return False
        try:
            await channel.send(**kwargs)
            return True
        except discord.Forbidden:
            self.events.log(
                "error", f"No permission in log channel #{getattr(channel, 'name', '?')}: "
                         "the bot needs Send Messages, Embed Links and Attach Files there."
            )
        except discord.HTTPException as e:
            self.events.log("warn", f"Couldn't post to log channel: {e}")
        return False

    async def log_event(self, category: str, text: str, color: discord.Color,
                        fields: tuple = (), user=None) -> None:
        """Post an embed to the log channel if that category is turned on."""
        if not self.config.log_channel_id or not getattr(self.config, category, True):
            return
        embed = discord.Embed(description=text[:4000], color=color,
                              timestamp=datetime.now(timezone.utc))
        if user is not None:
            embed.set_author(name=str(user), icon_url=user.display_avatar.url)
            embed.set_footer(text=f"User ID {user.id}")
        for name, value in fields:
            embed.add_field(name=name, value=str(value)[:1000] or "-")
        await self.send_log(embed=embed)

    async def log_blocked(self, ctx, reason: str) -> None:
        # At most one log entry per user every 30 s, so spammers can't flood the channel
        now = time.monotonic()
        if now - self._blocked_logged.get(ctx.author.id, 0) < 30:
            return
        self._blocked_logged[ctx.author.id] = now
        await self.log_event(
            "log_blocked",
            f"🚫 **Blocked** {ctx.author.mention} in {ctx.channel.mention}\n"
            f"```{ctx.message.content[:300].replace('`', 'ˋ')}```",
            discord.Color.dark_orange(), fields=(("Reason", reason),), user=ctx.author,
        )

    async def panel_event(self, text: str, category: str = "log_vm_events") -> None:
        """Something done from the control panel (used by the GUI)."""
        color = discord.Color.dark_purple() if category == "log_mod_actions" else discord.Color.orange()
        await self.log_event(category, f"🖥️ **Control panel:** {text}", color)

    async def send_test_log(self) -> None:
        """Post a test message to the log channel (used by the GUI)."""
        if not self.config.log_channel_id:
            self.events.log("warn", "No log channel set. Pick one on the Discord page.")
            return
        ok = await self.send_log(embed=discord.Embed(
            title="✅ Log channel works",
            description="Test message from the Discord Uses VM control panel.",
            color=discord.Color.green(), timestamp=datetime.now(timezone.utc),
        ))
        if ok:
            self.events.log("ok", "Test message posted to the log channel")
        else:
            self.events.log("error", "Couldn't post to the log channel. Check the channel ID and the bot's permissions.")

    def emit_channels(self) -> None:
        """Tell the GUI which text channels the bot can post in."""
        channels = []
        for guild in self.guilds:
            for ch in guild.text_channels:
                if ch.permissions_for(guild.me).send_messages:
                    channels.append((ch.id, f"{guild.name} / #{ch.name}"))
        self.events.channels(channels)

    async def on_guild_join(self, guild):
        self.emit_channels()

    async def on_guild_remove(self, guild):
        self.emit_channels()

    async def on_guild_channel_create(self, channel):
        self.emit_channels()

    async def on_guild_channel_delete(self, channel):
        self.emit_channels()

    async def on_guild_channel_update(self, before, after):
        self.emit_channels()

    async def announce(self, text: str, channel_ids: list[int] | None = None) -> None:
        """Send a message as the bot (used by the GUI). With no channel_ids it goes
        to the command channels, or the log channel if none are set."""
        ids = channel_ids or self.config.command_channel_ids or (
            [self.config.log_channel_id] if self.config.log_channel_id else []
        )
        if not ids:
            self.events.log(
                "warn",
                "Announcement not sent: pick a channel in the Announce box, "
                "or set command channels / a log channel on the Discord page.",
            )
            return
        sent = []
        for cid in ids:
            channel = await self.get_channel_safe(cid)
            if channel is None:
                continue
            try:
                await channel.send(f"📢 {text}", allowed_mentions=discord.AllowedMentions.none())
                sent.append(f"#{getattr(channel, 'name', cid)}")
            except discord.Forbidden:
                self.events.log("error", f"No permission to send messages in #{getattr(channel, 'name', cid)}")
            except discord.HTTPException as e:
                self.events.log("error", f"Couldn't announce in #{getattr(channel, 'name', cid)}: {e}")
        if sent:
            self.events.log("ok", f"Announced in {', '.join(sent)}: {text}")
            await self.log_event(
                "log_announcements", f"📢 **Announcement** in {', '.join(sent)}\n>>> {text}",
                discord.Color.blue(),
            )

    async def log_command(self, ctx, result: str, ok: bool, png: bytes | None) -> None:
        cfg = self.config
        name = ctx.command.name if ctx.command is not None else ""
        is_mod_action = name in MOD_COMMANDS or (name in VOTE_COMMANDS and self.is_mod(ctx.author))
        if is_mod_action:
            if not cfg.log_mod_actions:
                return
        elif not cfg.log_commands or (cfg.log_failed_only and ok):
            return
        embed = discord.Embed(
            title="🛡️ Mod action" if is_mod_action else None,
            description=f"{ctx.author.mention} in {ctx.channel.mention}\n"
                        f"```{ctx.message.content[:300].replace('`', 'ˋ')}```",
            color=(discord.Color.dark_purple() if is_mod_action else discord.Color.blurple())
            if ok else discord.Color.red(),
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_author(name=str(ctx.author), icon_url=ctx.author.display_avatar.url)
        embed.add_field(name="Result", value=result[:1000] or "-")
        embed.set_footer(text=f"User ID {ctx.author.id}")
        file = None
        if png and self.config.log_screenshots:
            file = discord.File(io.BytesIO(png), "log.png")
            embed.set_image(url="attachment://log.png")
        await self.send_log(embed=embed, **({"file": file} if file else {}))

    def record(self, ctx, ok: bool, result: str) -> None:
        self.total_commands += 1
        self.usage[str(ctx.author)] += 1
        self.events.command(str(ctx.author), ctx.author.id, ctx.message.content, ok, result)
        self.events.log("info" if ok else "warn", f"{ctx.author}: {ctx.message.content} -> {result}")

    async def _screenshot(self, grid: bool) -> bytes:
        png = await asyncio.to_thread(self.vbox.screenshot)
        if grid:
            png = await asyncio.to_thread(add_grid, png, self.config.grid_size)
        return png

    async def run_steps(self, ctx, steps: list[Step]) -> None:
        """Run steps in order on the VM, then reply with the screenshot(s).
        A chain shows one screenshot at the end, plus one for each !screen/!grid in it."""
        cfg = self.config
        shots: list[bytes] = []
        done: list[str] = []
        error = None
        async with self.vm_lock:
            async with ctx.typing():
                try:
                    for step in steps:
                        if step.action is not None:
                            await asyncio.to_thread(step.action)
                        if step.wait:
                            await asyncio.sleep(step.wait)
                        if step.snapshot:
                            shots.append(await self._screenshot(step.grid or cfg.grid))
                        done.append(step.label)
                    if not steps[-1].snapshot:
                        # Give the screen a moment to update after the last input
                        if steps[-1].action is not None:
                            await asyncio.sleep(cfg.screenshot_delay)
                        shots.append(await self._screenshot(cfg.grid))
                except VBoxError as e:
                    error = f"Step {len(done) + 1}: {e}" if len(steps) > 1 else str(e)

        if len(steps) == 1:
            label = steps[0].label
        else:
            label = "⛓️ " + " → ".join(done)
        label = label[:1800]
        self.record(ctx, error is None, error or label)
        if error:
            text = f"⚠️ {error}" + (f"\nDone before that: {' → '.join(done)}"[:1800] if done else "")
            await ctx.reply(text, mention_author=False)
        elif cfg.reply_screenshot and shots:
            files = [discord.File(io.BytesIO(png), f"vm{i}.png") for i, png in enumerate(shots[-10:], 1)]
            await ctx.reply(label, files=files, mention_author=False)
        else:
            await ctx.reply(label, mention_author=False)
        await self.log_command(ctx, error or label, error is None, shots[-1] if shots else None)

    async def act_and_show(self, ctx, action, label: str, delay: float | None = None,
                           grid: bool | None = None) -> None:
        """Run `action` (a blocking function) on the VM, wait, reply with a screenshot.
        grid=None uses the config setting; True/False forces the coordinate grid on/off."""
        cfg = self.config
        grid = cfg.grid if grid is None else grid
        png, error = None, None
        async with self.vm_lock:
            async with ctx.typing():
                try:
                    if action is not None:
                        await asyncio.to_thread(action)
                    await asyncio.sleep(cfg.screenshot_delay if delay is None else delay)
                    png = await asyncio.to_thread(self.vbox.screenshot)
                    if grid:
                        png = await asyncio.to_thread(add_grid, png, cfg.grid_size)
                except VBoxError as e:
                    error = str(e)

        self.record(ctx, error is None, error or label)
        if error:
            await ctx.reply(f"⚠️ {error}", mention_author=False)
        elif cfg.reply_screenshot and png:
            await ctx.reply(label, file=discord.File(io.BytesIO(png), "vm.png"), mention_author=False)
        else:
            await ctx.reply(label, mention_author=False)
        await self.log_command(ctx, error or label, error is None, png)

    def revert_vm(self) -> None:
        self.vbox.revert(self.config.revert_snapshot, self.config.start_mode)
        self.last_revert = time.monotonic()
        self.votes.clear()

    async def _auto_revert_loop(self) -> None:
        await self.wait_until_ready()
        while not self.is_closed():
            await asyncio.sleep(20)
            minutes = self.config.auto_revert_minutes
            if minutes <= 0 or time.monotonic() - self.last_revert < minutes * 60:
                continue
            self.events.log("info", "Auto revert")
            async with self.vm_lock:
                try:
                    await asyncio.to_thread(self.revert_vm)
                except VBoxError as e:
                    self.events.log("error", f"Auto revert failed: {e}")
                    self.last_revert = time.monotonic()
                    continue
            for cid in self.config.command_channel_ids:
                channel = await self.get_channel_safe(cid)
                if channel is not None:
                    await channel.send(f"⏪ Auto revert: the VM was reset to its clean snapshot (every {minutes} min).")
            await self.log_event(
                "log_vm_events", f"⏪ **Auto revert** (every {minutes} min)", discord.Color.orange()
            )

    async def on_command_error(self, ctx: commands.Context, error) -> None:
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.reply(
                f"⏳ Slow down, try again in {error.retry_after:.1f}s",
                mention_author=False, delete_after=5,
            )
        elif isinstance(error, Denied):
            await ctx.reply(str(error), mention_author=False, delete_after=8)
            await self.log_blocked(ctx, str(error))
        elif isinstance(error, commands.CheckFailure):
            return
        elif isinstance(error, (commands.UserInputError,)):
            name = ctx.command.qualified_name
            if name in USAGE or name == "chain":
                # These commands already put the usage in their error message
                await ctx.reply(f"❌ {error}", mention_author=False)
            else:
                usage = f"{self.config.prefix}{name} {ctx.command.signature}"
                await ctx.reply(f"❌ {error}\nUsage: `{usage}`", mention_author=False)
        else:
            original = getattr(error, "original", error)
            self.events.log("error", f"{ctx.message.content}: {original!r}")
            await ctx.reply("⚠️ Something went wrong.", mention_author=False)


class VMCog(commands.Cog):
    def __init__(self, bot: VMBot):
        self.bot = bot

    @property
    def cfg(self) -> Config:
        return self.bot.config

    @property
    def vbox(self) -> VBox:
        return self.bot.vbox

    async def cog_check(self, ctx: commands.Context) -> bool:
        cfg = self.cfg
        if cfg.command_channel_ids and ctx.channel.id not in cfg.command_channel_ids:
            return False
        if ctx.author.id in cfg.banned_user_ids:
            await self.bot.log_blocked(ctx, "🔨 Banned user")
            return False
        if ctx.command.name in cfg.disabled_commands:
            raise Denied(f"🚫 `{cfg.prefix}{ctx.command.name}` is disabled.")
        if cfg.lockdown and not self.bot.is_mod(ctx.author):
            raise Denied("🔒 The VM is locked right now.")
        return True

    # --- steps: every VM input command, usable alone or in a chain ----------------

    def _int(self, value: str, what: str) -> int:
        try:
            return int(value)
        except ValueError:
            raise commands.BadArgument(f"`{value}` isn't a number ({what}).")

    def _key_step(self, ctx, combo: str, times_arg: str | None) -> Step:
        try:
            normalized = normalize_combo(combo)
        except VBoxError as e:
            raise commands.BadArgument(f"{e}. Try `{self.cfg.prefix}keys`.")
        if not self.bot.is_mod(ctx.author):
            blocked = set()
            for b in self.cfg.blocked_keys:
                try:
                    blocked.add(normalize_combo(b))
                except VBoxError:
                    pass
            if normalized in blocked:
                raise Denied(f"🚫 `{combo}` is blocked.")
        times = self._int(times_arg, "times") if times_arg else 1
        times = max(1, min(times, self.cfg.max_repeat))
        label = f"⌨️ `{combo}`" + (f" ×{times}" if times > 1 else "")
        return Step(label, lambda: self.vbox.send_combo(combo, times))

    def _check_text(self, ctx, text: str) -> None:
        if len(text) > self.cfg.max_type_len:
            raise commands.BadArgument(f"Max {self.cfg.max_type_len} characters.")
        if not self.bot.is_mod(ctx.author):
            lowered = text.lower()
            if any(w.lower() in lowered for w in self.cfg.blocked_words if w.strip()):
                raise Denied("🚫 That text contains a blocked word.")

    def parse_step(self, ctx, name: str, args: str) -> Step:
        """Turn one command (name + its raw argument text) into a Step, checking limits."""
        p = self.cfg.prefix
        a = args.split()
        usage = USAGE.get(name, "").format(p=p)

        def need(n_min: int, n_max: int):
            if not n_min <= len(a) <= n_max:
                raise commands.BadArgument(f"Usage: `{usage}`")

        if name == "key":
            need(1, 2)
            if "+" in a[0].strip("+"):
                raise commands.BadArgument(f"For key combos use `{p}combo {a[0]}`.")
            return self._key_step(ctx, a[0], a[1] if len(a) > 1 else None)

        if name == "combo":
            need(1, 2)
            return self._key_step(ctx, a[0], a[1] if len(a) > 1 else None)

        if name in ("type", "send"):
            text = args.strip()
            if not text and name == "type":
                raise commands.BadArgument(f"Usage: `{usage}`")
            self._check_text(ctx, text)
            shown = discord.utils.escape_markdown(text)
            if name == "type":
                return Step(f"⌨️ typed “{shown}”", lambda: self.vbox.send_text(text))

            def send():
                if text:
                    self.vbox.send_text(text)
                self.vbox.send_combo("enter")
            return Step(f"⌨️ sent “{shown}” ⏎" if text else "⌨️ ⏎", send)

        if name == "click":
            need(2, 3)
            x, y = self._int(a[0], "x"), self._int(a[1], "y")
            button = a[2].lower() if len(a) > 2 else "left"
            if button not in ("left", "right", "middle", "double"):
                raise commands.BadArgument("Button must be left, right, middle or double.")
            return Step(f"🖱️ {button} click at ({x}, {y})", lambda: self.vbox.click(x, y, button))

        if name == "move":
            need(2, 2)
            x, y = self._int(a[0], "x"), self._int(a[1], "y")
            return Step(f"🖱️ moved to ({x}, {y})", lambda: self.vbox.mouse([(x, y, 0, 0)]))

        if name == "drag":
            need(4, 4)
            x1, y1, x2, y2 = (self._int(v, "coordinate") for v in a)
            return Step(f"🖱️ dragged ({x1}, {y1}) → ({x2}, {y2})", lambda: self.vbox.drag(x1, y1, x2, y2))

        if name == "scroll":
            need(1, 4)
            direction = a[0].lower()
            if direction not in ("up", "down"):
                raise commands.BadArgument("Direction must be up or down.")
            amount = self._int(a[1], "amount") if len(a) > 1 else 3
            amount = max(1, min(amount, self.cfg.max_repeat))
            x = self._int(a[2], "x") if len(a) > 2 else 400
            y = self._int(a[3], "y") if len(a) > 3 else 300
            signed = amount if direction == "down" else -amount
            return Step(f"🖱️ scrolled {direction} ×{amount}", lambda: self.vbox.scroll(x, y, signed))

        if name == "wait":
            need(0, 1)
            try:
                seconds = float(a[0]) if a else 3.0
            except ValueError:
                raise commands.BadArgument(f"`{a[0]}` isn't a number of seconds.")
            seconds = max(0.0, min(seconds, 15.0))
            return Step(f"⏱️ waited {seconds:g}s", None, wait=seconds)

        if name == "screen":
            return Step("📸", None, snapshot=True)

        if name == "grid":
            return Step(f"📐 Use these numbers with `{p}click <x> <y>`", None, snapshot=True, grid=True)

        raise commands.BadArgument(f"`{p}{name}` can't be used here.")

    async def _run_one(self, ctx, name: str, args: str) -> None:
        await self.bot.run_steps(ctx, [self.parse_step(ctx, name, args)])

    # --- keyboard -----------------------------------------------------------

    @commands.command(aliases=["press"])
    @cooldown
    async def key(self, ctx, *, args: str = ""):
        """Press one key: !key win, !key enter 3"""
        await self._run_one(ctx, "key", args)

    @commands.command(aliases=["hotkey"])
    @cooldown
    async def combo(self, ctx, *, args: str = ""):
        """Press keys together: !combo win+r, !combo ctrl+alt+del"""
        await self._run_one(ctx, "combo", args)

    @commands.command(name="type", aliases=["write"])
    @cooldown
    async def type_text(self, ctx, *, args: str = ""):
        """Type text: !type hello world"""
        await self._run_one(ctx, "type", args)

    @commands.command()
    @cooldown
    async def send(self, ctx, *, args: str = ""):
        """Type text, then press Enter: !send notepad"""
        await self._run_one(ctx, "send", args)

    # --- mouse --------------------------------------------------------------

    @commands.command()
    @cooldown
    async def click(self, ctx, *, args: str = ""):
        """Click: !click 500 300 [left|right|middle|double]"""
        await self._run_one(ctx, "click", args)

    @commands.command()
    @cooldown
    async def move(self, ctx, *, args: str = ""):
        """Move the mouse: !move 500 300"""
        await self._run_one(ctx, "move", args)

    @commands.command()
    @cooldown
    async def drag(self, ctx, *, args: str = ""):
        """Drag: !drag 100 100 400 300"""
        await self._run_one(ctx, "drag", args)

    @commands.command()
    @cooldown
    async def scroll(self, ctx, *, args: str = ""):
        """Scroll: !scroll down, !scroll up 5, !scroll down 3 500 300"""
        await self._run_one(ctx, "scroll", args)

    # --- screenshots ----------------------------------------------------------

    @commands.command(aliases=["ss", "screenshot"])
    @cooldown
    async def screen(self, ctx, *, args: str = ""):
        """Take a screenshot"""
        await self._run_one(ctx, "screen", "")

    @commands.command(aliases=["coords"])
    @cooldown
    async def grid(self, ctx, *, args: str = ""):
        """Screenshot with a coordinate grid, for aiming !click"""
        await self._run_one(ctx, "grid", "")

    @commands.command()
    @cooldown
    async def wait(self, ctx, *, args: str = ""):
        """Wait, then screenshot: !wait 5"""
        await self._run_one(ctx, "wait", args)

    # --- chaining ---------------------------------------------------------------

    @commands.command(hidden=True)
    @cooldown
    async def chain(self, ctx, *, rest: str = ""):
        """Several commands in one message: !combo win+r !wait 2 !send notepad"""
        cfg, p = self.cfg, self.cfg.prefix
        content = ctx.message.content
        if ctx.invoked_with == "chain" and content.lstrip().lower().startswith(f"{p}chain"):
            content = rest  # typed "!chain ..." explicitly
        segments = self.bot.split_chain(content)
        if not segments:
            raise commands.BadArgument(f"Nothing to run. Example: `{p}combo win+r {p}wait 2 {p}send notepad`")
        if len(segments) > cfg.max_chain_steps:
            raise Denied(f"⛓️ Max {cfg.max_chain_steps} commands per message.")
        steps, total_wait = [], 0.0
        for i, (name, args) in enumerate(segments, 1):
            if name in cfg.disabled_commands:
                raise Denied(f"🚫 `{p}{name}` is disabled.")
            try:
                step = self.parse_step(ctx, name, args)
            except commands.BadArgument as e:
                shown = f"{p}{name} {args}".strip()
                raise commands.BadArgument(f"Step {i} (`{shown}`): {e}")
            total_wait += step.wait
            steps.append(step)
        if total_wait > cfg.max_chain_wait:
            raise Denied(f"⛓️ The waits add up to {total_wait:g}s; max is {cfg.max_chain_wait:g}s per message.")
        await self.bot.run_steps(ctx, steps)

    @commands.command(aliases=["start", "poweron"])
    @cooldown
    async def startvm(self, ctx):
        """Start the VM if it's shut down (anyone can use it)"""
        try:
            state = await asyncio.to_thread(self.vbox.state)
        except VBoxError as e:
            await ctx.reply(f"⚠️ {e}", mention_author=False)
            return
        if state == "running":
            await ctx.reply("✅ The VM is already running.", mention_author=False, delete_after=10)
            return
        if state == "paused":
            await self.bot.act_and_show(ctx, self.vbox.resume, "⏯️ VM resumed")
            return
        if state not in ("poweroff", "aborted", "saved"):
            await ctx.reply(f"⏳ The VM is busy ({state}), try again in a moment.", mention_author=False)
            return
        await ctx.reply("▶️ Starting the VM… screenshot in a few seconds.", mention_author=False)
        await self.bot.act_and_show(
            ctx, lambda: self.vbox.start(self.cfg.start_mode), "▶️ VM started", delay=10
        )
        await self.bot.log_event("log_vm_events", f"▶️ **VM started** by {ctx.author.mention}",
                                 discord.Color.green(), user=ctx.author)

    @commands.command()
    async def keys(self, ctx):
        """List key names"""
        names = sorted(KEYS, key=lambda k: (len(k) > 1, k))
        await ctx.reply(
            "**Keys:** " + " ".join(f"`{n}`" for n in names)
            + "\n**Aliases:** " + ", ".join(f"`{a}`→`{t}`" for a, t in ALIASES.items())
            + f"\nPress keys together with `{self.cfg.prefix}combo`, e.g. `{self.cfg.prefix}combo ctrl+shift+esc`",
            mention_author=False,
        )

    @commands.command()
    @cooldown
    async def vminfo(self, ctx):
        """VM status"""
        try:
            info = await asyncio.to_thread(self.vbox.info)
        except VBoxError as e:
            await ctx.reply(f"⚠️ {e}", mention_author=False)
            return
        embed = discord.Embed(title=f"🖥️ {self.cfg.vm_name}", color=discord.Color.blurple())
        embed.add_field(name="State", value=info.get("VMState", "?"))
        embed.add_field(name="OS", value=info.get("ostype", "?"))
        embed.add_field(name="Memory", value=f"{info.get('memory', '?')} MB")
        embed.add_field(name="CPUs", value=info.get("cpus", "?"))
        embed.add_field(name="Locked", value="🔒 yes" if self.cfg.lockdown else "no")
        embed.add_field(name="Bot uptime", value=fmt_duration(time.time() - self.bot.started_at))
        if self.cfg.auto_revert_minutes > 0:
            left = self.cfg.auto_revert_minutes * 60 - (time.monotonic() - self.bot.last_revert)
            embed.add_field(name="Next auto revert", value=f"in {fmt_duration(max(0, left))}")
        embed.add_field(name="Active chatters", value=str(self.bot.active_users()))
        embed.add_field(name="Votes needed", value=str(self.bot.votes_needed()))
        embed.add_field(
            name="Current votes",
            value=f"revert {self.bot.vote_status('revert')} · reboot {self.bot.vote_status('reboot')}",
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(aliases=["leaderboard", "top"])
    async def stats(self, ctx):
        """Command leaderboard"""
        top = self.bot.usage.most_common(10)
        lines = [f"**{i}.** {discord.utils.escape_markdown(name)}: {n}" for i, (name, n) in enumerate(top, 1)]
        embed = discord.Embed(
            title="📊 Stats",
            description="\n".join(lines) or "No commands yet.",
            color=discord.Color.gold(),
        )
        embed.set_footer(text=f"{self.bot.total_commands} commands since the bot started")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="help", aliases=["commands"])
    async def help_cmd(self, ctx):
        p = self.cfg.prefix
        lines = {
            "key": f"`{p}key <key> [times]` press one key, e.g. `{p}key enter`",
            "combo": f"`{p}combo <key+key…>` press keys together, e.g. `{p}combo win+r`",
            "type": f"`{p}type <text>` type text",
            "send": f"`{p}send <text>` type text and press Enter",
            "click": f"`{p}click <x> <y> [left|right|middle|double]` click (use `{p}grid` to find x/y)",
            "grid": f"`{p}grid` screenshot with a coordinate grid, for aiming clicks",
            "move": f"`{p}move <x> <y>` move the mouse",
            "drag": f"`{p}drag <x1> <y1> <x2> <y2>` drag",
            "scroll": f"`{p}scroll <up|down> [n] [x y]` scroll",
            "screen": f"`{p}screen` screenshot",
            "wait": f"`{p}wait [seconds]` wait then screenshot",
            "keys": f"`{p}keys` list key names",
            "startvm": f"`{p}startvm` start the VM if it's shut down",
            "vminfo": f"`{p}vminfo` VM status",
            "stats": f"`{p}stats` leaderboard",
            "revert": f"`{p}revert` vote to reset the VM to its clean snapshot",
            "reboot": f"`{p}reboot` vote to restart the VM",
        }
        mod_lines = {
            "lock": f"`{p}lock`", "unlock": f"`{p}unlock`",
            "ban": f"`{p}ban <user>`", "unban": f"`{p}unban <user>`",
        }
        disabled = set(self.cfg.disabled_commands)
        text = "**Discord Uses VM** 🖥️\n" + "\n".join(
            v for k, v in lines.items() if k not in disabled
        )
        if "chain" not in disabled:
            text += (f"\n⛓️ **Chain** up to {self.cfg.max_chain_steps} commands in one message: "
                     f"`{p}combo win+r {p}wait 2 {p}send notepad`")
        if not {"revert", "reboot"} <= disabled:
            pct = round(self.cfg.vote_ratio * 100)
            text += (f"\n🗳️ Revert/reboot need votes from {pct}% of active chatters "
                     f"(currently {self.bot.votes_needed()}). Mods skip the vote.")
        mods = [v for k, v in mod_lines.items() if k not in disabled]
        if mods:
            text += "\n**Mods:** " + " · ".join(mods)
        if self.cfg.lockdown:
            text += "\n🔒 *The VM is currently locked to mods.*"
        await ctx.reply(text, mention_author=False)

    # --- votes ----------------------------------------------------------------

    async def _vote(self, ctx, action: str, verb: str, run) -> None:
        """Mods run `action` instantly; everyone else adds a vote until enough people agree."""
        bot, cfg, p = self.bot, self.cfg, self.cfg.prefix
        now = time.monotonic()
        if bot.is_mod(ctx.author):
            bot.votes.clear()
            bot.last_vote_action[action] = now
            await run(by_vote=False)
            return

        wait = cfg.vote_cooldown - (now - bot.last_vote_action.get(action, -1e9))
        if wait > 0:
            raise Denied(f"⏳ The VM was just {verb}ed. A new vote can start in {math.ceil(wait)}s.")

        vote = bot.votes.get(action)
        if vote is None or now - vote["started"] > cfg.vote_timeout:
            vote = bot.votes[action] = {"voters": set(), "started": now}
        needed = bot.votes_needed()
        if ctx.author.id in vote["voters"]:
            await ctx.reply(f"🗳️ You already voted to {verb} ({len(vote['voters'])}/{needed}).",
                            mention_author=False, delete_after=8)
            return

        vote["voters"].add(ctx.author.id)
        have = len(vote["voters"])
        if have >= needed:
            bot.votes.clear()
            bot.last_vote_action[action] = now
            await ctx.reply(f"🗳️ Vote passed ({have}/{needed})! Time to {verb} the VM.", mention_author=False)
            await run(by_vote=True)
            return

        left = max(0, cfg.vote_timeout - (now - vote["started"]))
        result = f"🗳️ voted to {verb} ({have}/{needed})"
        bot.record(ctx, True, result)
        await ctx.reply(
            f"🗳️ **{discord.utils.escape_markdown(ctx.author.display_name)}** wants to {verb} the VM: "
            f"**{have}/{needed}** votes. Type `{p}{action}` to agree (vote ends in {fmt_duration(left)}).",
            mention_author=False,
        )
        await bot.log_command(ctx, result, True, None)

    @commands.command()
    async def revert(self, ctx, snapshot: str = ""):
        """Vote to restore the clean snapshot (instant for mods, who can also name a snapshot)"""
        async def run(by_vote: bool):
            snap = (snapshot if not by_vote else "") or self.cfg.revert_snapshot

            def action():
                self.vbox.revert(snap, self.cfg.start_mode)
                self.bot.last_revert = time.monotonic()

            await ctx.reply(f"⏪ Reverting to {f'`{snap}`' if snap else 'the clean snapshot'}…", mention_author=False)
            await self.bot.act_and_show(ctx, action, "⏪ Reverted" + (" (vote passed)" if by_vote else ""), delay=8)

        await self._vote(ctx, "revert", "revert", run)

    @commands.command()
    async def reboot(self, ctx):
        """Vote to hard reset the VM (instant for mods)"""
        async def run(by_vote: bool):
            await self.bot.act_and_show(
                ctx, self.vbox.reset, "🔄 VM reset" + (" (vote passed)" if by_vote else ""), delay=5
            )

        await self._vote(ctx, "reboot", "reboot", run)

    # --- mods ---------------------------------------------------------------

    def _save_config(self):
        self.cfg.save()
        self.bot.events.config_changed()

    @commands.command()
    @mod_only()
    async def lock(self, ctx):
        """Only mods can use the VM"""
        self.cfg.lockdown = True
        self._save_config()
        self.bot.record(ctx, True, "locked")
        await ctx.reply("🔒 VM locked. Only mods can use commands.", mention_author=False)
        await self.bot.log_command(ctx, "🔒 locked", True, None)

    @commands.command()
    @mod_only()
    async def unlock(self, ctx):
        """Everyone can use the VM again"""
        self.cfg.lockdown = False
        self._save_config()
        self.bot.record(ctx, True, "unlocked")
        await ctx.reply("🔓 VM unlocked.", mention_author=False)
        await self.bot.log_command(ctx, "🔓 unlocked", True, None)

    @commands.command()
    @mod_only()
    async def ban(self, ctx, user: discord.User):
        """Block a user from the bot"""
        if user.id not in self.cfg.banned_user_ids:
            self.cfg.banned_user_ids.append(user.id)
            self._save_config()
        self.bot.record(ctx, True, f"banned {user}")
        await ctx.reply(f"🔨 {user.mention} can no longer use the VM.", mention_author=False)
        await self.bot.log_command(ctx, f"🔨 banned {user} ({user.id})", True, None)

    @commands.command()
    @mod_only()
    async def unban(self, ctx, user: discord.User):
        """Unblock a user"""
        if user.id in self.cfg.banned_user_ids:
            self.cfg.banned_user_ids.remove(user.id)
            self._save_config()
        self.bot.record(ctx, True, f"unbanned {user}")
        await ctx.reply(f"✅ {user.mention} can use the VM again.", mention_author=False)
        await self.bot.log_command(ctx, f"✅ unbanned {user} ({user.id})", True, None)
