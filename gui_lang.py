"""Control panel translations. English is the source text; other languages map English -> translation.

T("text") translates one string. translate_tree(widget) translates every label, button, title,
placeholder and tooltip under a widget, and remembers the English original so the language
can be switched back and forth while the panel is open.
"""
import re

from PyQt6.QtCore import QLibraryInfo, QTranslator, Qt
from PyQt6.QtWidgets import (
    QAbstractButton, QAbstractSpinBox, QComboBox, QGroupBox, QLabel, QLineEdit, QPlainTextEdit,
    QTableWidget, QWidget,
)

LANGUAGES = {"en": "English", "da": "Dansk"}

DA = {
    # Sidebar
    "Discord control panel": "Discord-kontrolpanel",
    "Dashboard": "Oversigt",
    "Virtual Machine": "Virtuel maskine",
    "Commands": "Kommandoer",
    "commands": "kommandoer",
    "Moderation": "Moderering",
    "Activity": "Aktivitet",
    "Logs": "Log",
    "Start bot": "Start bot",
    "Stop bot": "Stop bot",
    "Lockdown": "Kun mods",
    "When on, only mods can use commands": "Når den er slået til, kan kun mods bruge kommandoer",
    "Dark mode": "Mørkt tema",
    "Save settings": "Gem indstillinger",
    "Language": "Sprog",
    "Bot {status}": "Bot {status}",
    "online": "online",
    "offline": "offline",
    "connecting": "forbinder",
    "stopping": "stopper",
    "Online": "Online",
    "Offline": "Offline",
    "Connecting": "Forbinder",
    "Stopping": "Stopper",
    "On": "Til",
    "Off": "Fra",

    # Page headers
    "Watch the VM live and control it yourself.": "Se VM'en live og styr den selv.",
    "Bot account, channels and how the bot replies.": "Botkonto, kanaler og hvordan botten svarer.",
    "Pick the VM, manage power and snapshots.": "Vælg VM'en, og styr strøm og snapshots.",
    "Choose which commands people can use and set limits.":
        "Vælg hvilke kommandoer folk kan bruge, og sæt grænser.",
    "Mods, bans and blocked keys or words.": "Mods, udelukkelser og blokerede taster eller ord.",
    "Every command people have run, and who runs the most.":
        "Alle kommandoer folk har kørt, og hvem der kører flest.",
    "Everything the bot and the panel did.": "Alt hvad botten og panelet har gjort.",

    # Dashboard
    "Uptime": "Oppetid",
    "Users": "Brugere",
    "Live preview": "Live-visning",
    "Auto refresh": "Opdater automatisk",
    "Click to control": "Klik for at styre",
    "Left/right/middle click on the preview clicks inside the VM":
        "Venstre-, højre- eller midterklik på visningen klikker inde i VM'en",
    "Refresh": "Opdater",
    "Save image": "Gem billede",
    "Type text into the VM…": "Skriv tekst i VM'en…",
    "Key combo, e.g. ctrl+alt+del": "Tastekombination, f.eks. ctrl+alt+del",
    "Type": "Skriv",
    "Type the text, then press Enter": "Skriv teksten, og tryk derefter på Enter",
    "Press": "Tryk",
    "Quick actions": "Hurtige handlinger",
    "Start": "Start",
    "Shut down": "Luk ned",
    "Pause": "Pause",
    "Resume": "Fortsæt",
    "Reset": "Genstart",
    "Power off": "Sluk",
    "Revert to clean snapshot": "Gendan rent snapshot",
    "Announce": "Meddelelse",
    "Posts a message as the bot.": "Sender en besked som botten.",
    "Where to send it. Channels appear once the bot is online.":
        "Hvor den skal sendes hen. Kanalerne vises, når botten er online.",
    "Reload channel list": "Genindlæs kanallisten",
    "Reload": "Genindlæs",
    "Write a message…": "Skriv en besked…",
    "Send": "Send",
    "No preview yet": "Ingen visning endnu",
    "Loading preview…": "Indlæser visning…",
    "No preview": "Ingen visning",
    "No VM selected": "Ingen VM valgt",
    "unavailable": "utilgængelig",
    "running": "kører",
    "poweroff": "slukket",
    "paused": "på pause",
    "saved": "gemt",
    "aborted": "afbrudt",

    # Discord page
    "Bot account": "Botkonto",
    "Token": "Token",
    "Paste your bot token": "Indsæt dit bot-token",
    "Show": "Vis",
    "Invite bot to server": "Inviter botten til serveren",
    "Command prefix": "Kommandopræfiks",
    "Status text": "Statustekst",
    "Shown as 'Playing …' (empty = none)": "Vises som 'Spiller …' (tom = ingen)",
    "The bot needs <b>Message Content Intent</b> turned on in the Developer Portal (Bot page).":
        "Botten skal have <b>Message Content Intent</b> slået til i Developer Portal (siden Bot).",
    "Channels": "Kanaler",
    "Command channels": "Kommandokanaler",
    "Channel ID (right-click channel → Copy Channel ID)": "Kanal-ID (højreklik på kanalen → Kopiér kanal-ID)",
    "Leave empty to accept commands in any channel.": "Lad den være tom for at tillade kommandoer i alle kanaler.",
    "Reply to commands with a screenshot": "Svar på kommandoer med et skærmbillede",
    "Log channel": "Logkanal",
    "The bot posts a record of what happens to this channel, so mods can see who did what. "
    "Make it private to mods.":
        "Botten skriver i denne kanal, hvad der sker, så mods kan se, hvem der gjorde hvad. "
        "Gør den privat for mods.",
    "Channel ID": "Kanal-ID",
    "Channels appear once the bot is online": "Kanalerne vises, når botten er online",
    "Channel": "Kanal",
    "Send test message": "Send testbesked",
    "Clear": "Ryd",
    "Post": "Del",
    "Options": "Indstillinger",
    "Commands people run": "Kommandoer folk kører",
    "Blocked attempts (bans, lockdown, blocked keys/words, disabled commands)":
        "Blokerede forsøg (udelukkelser, kun mods, blokerede taster/ord, slåede-fra kommandoer)",
    "Mod actions (lock, ban, instant revert/reboot)": "Mod-handlinger (lås, udeluk, øjeblikkelig gendannelse/genstart)",
    "Bot online / offline": "Bot online / offline",
    "VM events (auto revert, power and snapshot actions from the panel)":
        "VM-hændelser (automatisk gendannelse, strøm- og snapshot-handlinger fra panelet)",
    "Announcements": "Meddelelser",
    "Only log commands that failed": "Log kun kommandoer, der fejlede",
    "Attach the screenshot to each command entry": "Vedhæft skærmbilledet til hver kommando",
    "Command channels (from settings)": "Kommandokanaler (fra indstillinger)",
    "Pick a channel…": "Vælg en kanal…",
    "Start the bot to pick from a list": "Start botten for at vælge fra en liste",

    # Virtual machine page
    "Browse…": "Gennemse…",
    "Version": "Version",
    "Start mode": "Starttilstand",
    "headless = no window (recommended), gui = normal window":
        "headless = intet vindue (anbefalet), gui = normalt vindue",
    "Start the VM when the bot starts (if it's off)": "Start VM'en, når botten starter (hvis den er slukket)",
    "Power": "Strøm",
    "ACPI shutdown": "ACPI-nedlukning",
    "Snapshots": "Snapshots",
    "Take snapshot": "Tag snapshot",
    "Restore selected": "Gendan valgte",
    "Snapshot used by !revert, auto revert and the Revert button":
        "Snapshot, der bruges af !revert, automatisk gendannelse og Gendan-knappen",
    "Revert to": "Gendan til",
    "Auto revert every": "Gendan automatisk hvert",
    "VM details": "VM-detaljer",
    "Strangers control this VM: disable its network adapter, shared folders, shared clipboard and "
    "drag-and-drop, and set Pointing Device to <b>USB Tablet</b>.":
        "Fremmede styrer denne VM: slå netværkskort, delte mapper, delt udklipsholder og træk-og-slip "
        "fra, og sæt Pegeenhed til <b>USB Tablet</b>.",
    "Refresh details": "Opdater detaljer",
    "(current snapshot)": "(nuværende snapshot)",
    "(current)": "(nuværende)",
    "No snapshots yet. Take one of a clean state for !revert.":
        "Ingen snapshots endnu. Tag et af en ren tilstand til !revert.",
    "Name": "Navn",
    "OS": "OS",
    "State": "Tilstand",
    "Memory (MB)": "Hukommelse (MB)",
    "CPUs": "CPU'er",
    "Video memory (MB)": "Videohukommelse (MB)",
    "Graphics": "Grafik",
    "Network adapter 1": "Netværkskort 1",
    "Shared clipboard": "Delt udklipsholder",
    "Drag and drop": "Træk og slip",
    "Pointing device": "Pegeenhed",
    "Config file": "Konfigurationsfil",
    "Network is enabled: anything people do online comes from your IP.":
        "Netværket er slået til: alt, hvad folk gør online, kommer fra din IP.",
    "Shared clipboard is on.": "Delt udklipsholder er slået til.",
    "Drag and drop is on.": "Træk og slip er slået til.",
    "The VM has shared folders.": "VM'en har delte mapper.",
    "Pointing device isn't USB Tablet; clicks may not work without Guest Additions.":
        "Pegeenheden er ikke USB Tablet; klik virker måske ikke uden Guest Additions.",

    # Commands page
    "Enabled commands": "Aktive kommandoer",
    "Enable all": "Slå alle til",
    "Disable all": "Slå alle fra",
    "vote": "afstemning",
    "Limits && timing": "Grænser && timing",
    "Cooldown per user": "Ventetid pr. bruger",
    "Wait before screenshot": "Vent før skærmbillede",
    "Max !type length": "Maks. længde for !type",
    "Max key repeat / scroll": "Maks. gentagelser / scroll",
    "Max chained per message": "Maks. kædede pr. besked",
    "Max total !wait per chain": "Maks. samlet !wait pr. kæde",
    "Screenshots": "Skærmbilleder",
    "Always draw the coordinate grid (otherwise only on !grid)":
        "Tegn altid koordinatgitteret (ellers kun ved !grid)",
    "Grid size": "Gitterstørrelse",
    "Panel preview refresh": "Opdatering af visningen",
    "Votes for revert and reboot": "Afstemninger for revert og reboot",
    "Anyone can start a vote. It passes when enough of the people active in the command channels "
    "agree. Mods skip the vote and it happens instantly.":
        "Alle kan starte en afstemning. Den vedtages, når nok af de aktive i kommandokanalerne er "
        "enige. Mods springer afstemningen over, og så sker det med det samme.",
    "Votes needed": "Stemmer krævet",
    "of active chatters": "af de aktive i chatten",
    "At least": "Mindst",
    "votes": "stemmer",
    "Active = chatted in the last": "Aktiv = har skrevet inden for de sidste",
    "Vote expires after": "Afstemningen udløber efter",
    "Wait after a revert/reboot": "Ventetid efter gendannelse/genstart",

    # Moderation page
    "Mods": "Mods",
    "Mod role name": "Navn på mod-rolle",
    "Mod user ID": "Mod-bruger-ID",
    "People with Manage Server are always mods. Mods skip cooldowns and blocks.":
        "Folk med Administrer server er altid mods. Mods springer ventetider og blokeringer over.",
    "Banned users": "Udelukkede brugere",
    "User ID": "Bruger-ID",
    "Banned users are ignored. Mods can also use !ban / !unban.":
        "Udelukkede brugere ignoreres. Mods kan også bruge !ban / !unban.",
    "Blocked key combos": "Blokerede tastekombinationer",
    "e.g. ctrl+alt+del, alt+f4": "f.eks. ctrl+alt+del, alt+f4",
    "Blocked words for type command": "Blokerede ord for type-kommandoen",
    "Word or phrase": "Ord eller sætning",
    "Add": "Tilføj",
    "Remove": "Fjern",

    # Activity page
    "Time": "Tid",
    "User": "Bruger",
    "Command": "Kommando",
    "Result": "Resultat",
    "Command history": "Kommandohistorik",
    "Right-click a row to ban the user, make them a mod, or copy their ID.":
        "Højreklik på en række for at udelukke brugeren, gøre dem til mod eller kopiere deres ID.",
    "Export CSV…": "Eksportér CSV…",
    "Top users": "Topbrugere",
    "Ban {user}": "Udeluk {user}",
    "Make {user} a mod": "Gør {user} til mod",
    "Copy user ID": "Kopiér bruger-ID",
    "Copy command": "Kopiér kommando",
    "Banned {user}": "Udelukkede {user}",
    "{user} is now a mod": "{user} er nu mod",

    # Logs page
    "Log": "Log",
    "All": "Alle",
    "Info": "Info",
    "Warnings & errors": "Advarsler og fejl",
    "Errors": "Fejl",
    "Search logs…": "Søg i loggen…",
    "Save to logs/ folder": "Gem i mappen logs/",
    "Export…": "Eksportér…",

    # Dialogs and status bar
    "Couldn't save settings:\n{error}": "Kunne ikke gemme indstillingerne:\n{error}",
    "Enter your bot token on the Discord page first.": "Indtast først dit bot-token på Discord-siden.",
    "Choose a VM on the Virtual Machine page first.": "Vælg først en VM på siden Virtuel maskine.",
    "Start the bot first and wait until it's online.": "Start botten først, og vent til den er online.",
    "Pick a log channel first.": "Vælg først en logkanal.",
    "Pick a channel to send to in the Announce box\n(or set command channels on the Discord page).":
        "Vælg en kanal at sende til i Meddelelse-boksen\n(eller angiv kommandokanaler på Discord-siden).",
    "Enter a valid bot token first.": "Indtast først et gyldigt bot-token.",
    "Select a snapshot first.": "Vælg først et snapshot.",
    "Power off the VM and restore '{name}'?": "Sluk VM'en og gendan '{name}'?",
    "Hard reset the VM?": "Genstart VM'en hårdt?",
    "Power off the VM?": "Sluk VM'en?",
    "Power off the VM and revert to {label}?": "Sluk VM'en og gendan til {label}?",
    "the current snapshot": "det nuværende snapshot",
    "Snapshot name:": "Navn på snapshot:",
    "Settings saved": "Indstillinger gemt",
    "Start the bot to load channels": "Start botten for at indlæse kanaler",
    "Export history": "Eksportér historik",
    "Export logs": "Eksportér log",
    "Save screenshot": "Gem skærmbillede",

    # Panel log messages
    "{app} started": "{app} startet",
    "Settings saved and applied to the running bot": "Indstillinger gemt og anvendt på den kørende bot",
    "Starting bot…": "Starter bot…",
    "Stopping bot…": "Stopper bot…",
    "Bot is online": "Botten er online",
    "Found {n} VM(s)": "Fandt {n} VM('er)",
    "Selected VM: {name}": "Valgt VM: {name}",
    "Lockdown on": "Kun mods til",
    "Lockdown off": "Kun mods fra",
    "Sending announcement…": "Sender meddelelse…",
    "History exported to {path}": "Historik eksporteret til {path}",
    "Logs exported to {path}": "Log eksporteret til {path}",
    "Taking snapshot '{name}'…": "Tager snapshot '{name}'…",
    "Snapshot '{name}' taken": "Snapshot '{name}' taget",
    "Restoring '{name}'…": "Gendanner '{name}'…",
    "Restored '{name}'": "Gendannede '{name}'",
    "Starting VM ({mode})…": "Starter VM ({mode})…",
    "VM started": "VM startet",
    "Reverting to {label}…": "Gendanner til {label}…",
    "Reverted": "Gendannet",
    "Saved {path}": "Gemt: {path}",
    "Ignoring unknown blocked key combos: {combos}": "Ignorerer ukendte blokerede tastekombinationer: {combos}",
    "ACPI shutdown sent": "ACPI-nedlukning sendt",
    "VM paused": "VM sat på pause",
    "VM resumed": "VM fortsætter",
    "VM reset": "VM genstartet",
    "VM powered off": "VM slukket",
    "Language: {name}": "Sprog: {name}",

    # Macros, live screen, watchdog (v1.1)
    "Macros": "Makroer",
    "Shortcuts anyone can run with !m <name>. Write the commands with ! and chain them, "
    "e.g. !run cmd !wait 2 !send dir":
        "Genveje som alle kan køre med !m <navn>. Skriv kommandoerne med ! og kæd dem sammen, "
        "f.eks. !run cmd !wait 2 !send dir",
    "Commands": "Kommandoer",
    "Add macro": "Tilføj makro",
    "Ignoring macros that need a one-word name and commands starting with !: {names}":
        "Ignorerer makroer, der skal have et navn på ét ord og kommandoer, der starter med !: {names}",
    "Live screen": "Live-skærm",
    "The bot keeps one message in this channel updated with a fresh screenshot, so people can watch "
    "without typing commands. Leave empty to turn it off.":
        "Botten holder én besked i denne kanal opdateret med et nyt skærmbillede, så folk kan følge med "
        "uden at skrive kommandoer. Lad den være tom for at slå det fra.",
    "Update every": "Opdater hvert",
    "Watchdog: start the VM again if it crashes or is shut down from inside":
        "Vagthund: start VM'en igen, hvis den går ned eller bliver lukket indefra",
    "Not when you power it off from this panel": "Ikke når du slukker den fra dette panel",

    # Keyboard layouts (v1.2)
    "Keyboard": "Tastatur",
    "Pick the keyboard layout that is set inside the VM (in its Windows settings), so typed text and "
    "keys come out right, e.g. ş ğ ı on Turkish or æ ø å on Danish.":
        "Vælg det tastaturlayout, der er sat inde i VM'en (i dens Windows-indstillinger), så tekst og "
        "taster bliver rigtige, f.eks. ş ğ ı på tyrkisk eller æ ø å på dansk.",
    "VM keyboard layout": "VM'ens tastaturlayout",
    "Test": "Test",
    "Test typing": "Test skrivning",
    "Open Notepad in the VM first, then press this": "Åbn Notesblok i VM'en først, og tryk så her",
    "Open Notepad in the VM, press Test typing, and check the text matches.":
        "Åbn Notesblok i VM'en, tryk på Test skrivning, og tjek at teksten passer.",
    "VM keyboard layout: {name}": "VM'ens tastaturlayout: {name}",
    "Skipped characters this layout can't type: {chars}": "Sprang tegn over, som layoutet ikke kan skrive: {chars}",
    "Typed the test text. Check it matches in the VM.": "Testteksten er skrevet. Tjek at den passer i VM'en.",
    "English (US)": "Engelsk (USA)",
    "English (UK)": "Engelsk (UK)",
    "Danish": "Dansk",
    "German": "Tysk",
    "French (AZERTY)": "Fransk (AZERTY)",
    "Turkish Q": "Tyrkisk Q",
    "Turkish F": "Tyrkisk F",

    # Updates
    "Check for updates": "Søg efter opdateringer",
    "Update to {version}": "Opdater til {version}",
    "Update available": "Opdatering tilgængelig",
    "Update available: {version}": "Opdatering tilgængelig: {version}",
    "Version {new} is available. You have {current}.": "Version {new} er tilgængelig. Du har {current}.",
    "What's new": "Nyheder",
    "Your settings are kept. The panel restarts after updating, and if the bot is running it "
    "starts again by itself.":
        "Dine indstillinger bevares. Panelet genstarter efter opdateringen, og hvis botten kører, "
        "starter den selv igen.",
    "Check for updates automatically": "Søg automatisk efter opdateringer",
    "Skip this version": "Spring denne version over",
    "Later": "Senere",
    "Update now": "Opdater nu",
    "You have the latest version ({version}).": "Du har den nyeste version ({version}).",
    "Couldn't check for updates:\n{error}": "Kunne ikke søge efter opdateringer:\n{error}",
    "Downloading and installing {version}…": "Henter og installerer {version}…",
    "Updated to {version}: {n} files, backup in {backup}": "Opdateret til {version}: {n} filer, backup i {backup}",
    "Updated, but installing new Python packages failed:\n{error}\n\nRun: pip install -r requirements.txt":
        "Opdateret, men installation af nye Python-pakker mislykkedes:\n{error}\n\n"
        "Kør: pip install -r requirements.txt",
    "Updated to {version}. The panel will now restart.": "Opdateret til {version}. Panelet genstarter nu.",
    "Update failed:\n{error}": "Opdateringen mislykkedes:\n{error}",
}

TRANSLATIONS = {"da": DA}
_lower = {code: {k.lower(): v for k, v in table.items()} for code, table in TRANSLATIONS.items()}
_lang = "en"
_qt_translator: QTranslator | None = None

# Leading emoji/symbols/spaces ("⏪  Revert…") and trailing spaces stay as they are
_SPLIT = re.compile(r"^([^\w(\"'<!]*)(.*?)(\s*)$", re.S)


def set_language(code: str, app=None) -> None:
    """Switch the panel language; with app, also translate Qt's own dialogs (Yes/No, …)."""
    global _lang, _qt_translator
    _lang = code if code in LANGUAGES else "en"
    if app is None:
        return
    if _qt_translator is not None:
        app.removeTranslator(_qt_translator)
        _qt_translator = None
    if _lang != "en":
        tr = QTranslator()
        if tr.load(f"qtbase_{_lang}", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
            app.installTranslator(tr)
            _qt_translator = tr


def T(text: str) -> str:
    """Translate one English string into the current language (unknown strings stay English)."""
    if _lang == "en" or not text:
        return text
    table = TRANSLATIONS[_lang]
    if text in table:
        return table[text]
    prefix, core, tail = _SPLIT.match(text).groups()
    if core in table:
        return prefix + table[core] + tail
    if core.isupper() and core.lower() in _lower[_lang]:
        return prefix + _lower[_lang][core.lower()].upper() + tail
    return text


def _retranslate(obj, key: str, get, set_) -> None:
    current = get()
    if not current:
        return
    stored = obj.property(f"i18n_{key}")
    # If the text still is what we set last time, translate from the stored English original;
    # otherwise the code changed it since, so the current text is the new original
    original = stored[0] if stored and current == stored[1] else current
    shown = T(original)
    obj.setProperty(f"i18n_{key}", [original, shown])
    if shown != current:
        set_(shown)


ROLE = Qt.ItemDataRole.UserRole + 77


def translate_tree(root: QWidget) -> None:
    """Translate every static text under root into the current language."""
    for w in [root, *root.findChildren(QWidget)]:
        _retranslate(w, "tip", w.toolTip, w.setToolTip)
        if isinstance(w, QAbstractButton):
            _retranslate(w, "text", w.text, w.setText)
        elif isinstance(w, QLabel):
            _retranslate(w, "text", w.text, w.setText)
        elif isinstance(w, QGroupBox):
            _retranslate(w, "title", w.title, w.setTitle)
        elif isinstance(w, (QLineEdit, QPlainTextEdit)):
            _retranslate(w, "ph", w.placeholderText, w.setPlaceholderText)
        elif isinstance(w, QAbstractSpinBox):
            if hasattr(w, "suffix"):
                _retranslate(w, "suffix", w.suffix, w.setSuffix)
            _retranslate(w, "special", w.specialValueText, w.setSpecialValueText)
        elif isinstance(w, QComboBox) and w.property("i18n"):
            for i in range(w.count()):
                stored = w.itemData(i, ROLE)
                current = w.itemText(i)
                original = stored[0] if stored and current == stored[1] else current
                shown = T(original)
                w.setItemData(i, [original, shown], ROLE)
                w.setItemText(i, shown)
        elif isinstance(w, QTableWidget):
            for i in range(w.columnCount()):
                item = w.horizontalHeaderItem(i)
                if item is None:
                    continue
                stored = item.data(ROLE)
                current = item.text()
                original = stored[0] if stored and current == stored[1] else current
                shown = T(original)
                item.setData(ROLE, [original, shown])
                item.setText(shown)
