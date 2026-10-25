# Discord Uses VM

People type commands in a Discord channel. The bot runs them on a VirtualBox VM and replies with a screenshot. Everything is set up and controlled from a desktop control panel.

```
!key win              !key enter 3           !combo win+r
!combo ctrl+alt+del   !type hello            !send notepad      (type + Enter)
!run                  !run notepad           (open the Run box, optionally run something)
!click 500 300        !click 500 300 right   !drag 100 100 400 300   !scroll down 5
!m cmd                !macros                (saved macros)
!screen   !grid   !wait 5   !startvm   !keys   !vminfo   !stats   !help
Votes: !revert  !reboot   (instant for mods; mods can also do !revert <snapshot>)
Mods: !lock  !unlock  !ban @user  !unban @user
```

**Chaining:** put several commands in one message and they run in order, with one screenshot at the end (plus one for each `!screen`/`!grid` in the chain):

```
!combo win+r !wait 2 !send cmd !wait 2 !send echo "hello, world!"
```

Chainable: key, combo, type, send, run, click, move, drag, scroll, wait, screen, grid. Limits (10 commands, 30 s of waiting per message) are on the Commands page.

**Macros:** named chains you set up on the Commands page, which anyone runs with `!m <name>` (e.g. `!m cmd` → `!run cmd`). Write them with `!` even if you changed the prefix.

**Live screen:** pick a channel on the Discord page, and the bot keeps one message there updated with a fresh screenshot (every 30 s by default), so people can watch without typing.

**Watchdog:** if the VM crashes or someone shuts it down from inside (`!send shutdown /s`), the bot starts it again within about 30 seconds. Powering it off from the panel doesn't trigger it. Toggle it on the Virtual Machine page.

**Stats:** the `!stats` leaderboard is saved in `stats.json`, so it survives restarts and updates.

**Voting:** anyone can type `!revert` or `!reboot` to start or join a vote. It passes once 50% of the people who chatted in the command channels in the last 10 minutes have voted (rounded up, so 4 active people need 2 votes). Votes expire after 2 minutes, and there's a 1-minute wait after a revert/reboot before a new vote can start. All of these are adjustable on the Commands page. `!vminfo` shows the active count and current votes.

## Quick start

1. `pip install -r requirements.txt`
2. Double-click **Start GUI.bat** (or run `python gui.py`).
3. **Discord tab:** paste the bot token, add your command channel ID(s) and a log channel ID. Click **Invite bot** to add it to your server.
4. **Virtual Machine tab:** pick the VM from the list. Take a snapshot of a clean state.
5. Click **▶ Start bot**.

Settings are saved to `config.json`, which is created on first run (`config.example.json` shows every option). **It contains your bot token, so don't share it.** It's in `.gitignore`, so it's never committed.
`python bot.py` runs the bot without the GUI, using the same settings.

### Discord bot setup

At https://discord.com/developers/applications: **New Application** → **Bot** → **Reset Token** → copy it, and turn on **Message Content Intent**.

### VM setup (important)

Strangers control this VM:

- **Network → disable the adapter.** Otherwise anything people do online traces back to your IP.
- Shared clipboard and drag-and-drop: **Disabled**. No shared folders.
- **System → Pointing Device: USB Tablet**, so `!click` works.

The VM tab's details box warns you if any of these are wrong.

## Control panel features

| Tab | What's there |
|---|---|
| 🖥️ Dashboard | Live VM preview (click it to control the VM yourself), type/key box, quick keys, save screenshot, bot/VM status, uptime, command count, VM quick actions, announcements to channels |
| 💬 Discord | Token (hidden), invite link, prefix, "Playing…" status, command channels, log channel, screenshot options |
| 📦 Virtual Machine | VBoxManage path + version check, VM picker, start mode (headless/GUI), start/shutdown/reset/pause/resume/power off, snapshots (take/restore), which snapshot to revert to, auto-revert timer, VM details with safety warnings |
| ⌨️ Commands | Turn each command on/off, cooldown, screenshot delay, max type length, max repeats, grid on/off + size, preview refresh rate |
| 🛡️ Moderation | Mod role, mod user IDs, banned users, blocked key combos, blocked words |
| 📊 Activity | Live command history (right-click a row to ban, make mod, or copy ID), top users, export to CSV |
| 📜 Logs | Colored log with filter and search, export, daily log files in `logs/` |

Sidebar: start/stop the bot, save (Ctrl+S), **Lockdown** (only mods can use commands), dark/light theme, and the panel language (**English / Dansk**, switches instantly). Translations live in `gui_lang.py`.

`!startvm` lets anyone start the VM when it's shut down (or resume it if paused).

**Log channel** (Discord page): pick a channel from the list (or paste its ID) and press **Send test message**. Toggle what gets posted: commands, blocked attempts, mod actions, bot online/offline, VM events (auto revert and power/snapshot actions from the panel) and announcements. You can also log only failed commands and attach screenshots. Blocked attempts are logged at most once per user every 30 seconds, so spammers can't flood the channel.

## Updates

The panel checks GitHub for a new release when it starts and every 6 hours (switch this off in the update window). When one is out, an **Update to vX** button appears in the sidebar and a window shows what's new. **Update now** downloads the release from GitHub, replaces the program files, installs new Python packages if needed, and restarts the panel. If the bot was running, it starts again by itself.

- `config.json`, `logs/` and `assets/` are never touched.
- The old files are copied to `backup/v<old version>/` first.
- Downloads only come from GitHub, and are checked against GitHub's checksum.
- **Check for updates** under the version number in the sidebar checks right away.

### Publishing a release (maintainers)

1. Bump `__version__` in `version.py` (e.g. `1.1.0`) and commit.
2. Tag it `v1.1.0` and push the tag.
3. Create a GitHub release for the tag, with a `.zip` of the program attached (`git archive --format=zip -o discord-uses-vm-v1.1.0.zip v1.1.0`).

## Notes

- Commands run one at a time, so every screenshot matches its command.
- Raise *Wait before screenshot* or use `!wait` if screenshots come back before the screen has updated.
- `!type` follows the guest's keyboard layout; a US layout in the guest works best.
- Mods are people with the mod role, the listed mod IDs, or *Manage Server*. Mods skip cooldowns and blocked keys/words.
