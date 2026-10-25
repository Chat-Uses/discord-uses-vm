# Discord Uses VM

People type commands in a Discord channel. The bot runs them on a VirtualBox VM and replies with a screenshot. Everything is set up and controlled from a desktop control panel.

```
!key win              !key enter 3           !combo win+r
!combo ctrl+alt+del   !type hello            !send notepad      (type + Enter)
!click 500 300        !click 500 300 right   !drag 100 100 400 300   !scroll down 5
!screen   !grid   !wait 5   !startvm   !keys   !vminfo   !stats   !help
Votes: !revert  !reboot   (instant for mods; mods can also do !revert <snapshot>)
Mods: !lock  !unlock  !ban @user  !unban @user
```

**Chaining:** put several commands in one message and they run in order, with one screenshot at the end (plus one for each `!screen`/`!grid` in the chain):

```
!combo win+r !wait 2 !send cmd !wait 2 !send echo "hello, world!"
```

Chainable: key, combo, type, send, click, move, drag, scroll, wait, screen, grid. Limits (10 commands, 30 s of waiting per message) are on the Commands page.

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

## Notes

- Commands run one at a time, so every screenshot matches its command.
- Raise *Wait before screenshot* or use `!wait` if screenshots come back before the screen has updated.
- `!type` follows the guest's keyboard layout; a US layout in the guest works best.
- Mods are people with the mod role, the listed mod IDs, or *Manage Server*. Mods skip cooldowns and blocked keys/words.
