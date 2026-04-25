# Claude AI Bridge for Fantasy Grounds Unity
## GM Tool — D&D 5e

Connects Fantasy Grounds Unity 5.x to Claude AI. Claude silently absorbs live
session events from your chatlog in real-time, so when you ask for NPC dialogue,
a scene description, or a combat summary, it already knows exactly what just
happened at the table.

Responses are copied to your clipboard automatically. Switch to FGU, click the
chat box, Ctrl+V, Enter. You can edit before sending.

---

## Commands

| Command | Example | Visible to players? |
|---|---|---|
| `/describe` | `/describe the party approaching Old Bonegrinder at dusk` | Yes |
| `/npctalk (Name)` | `/npctalk (Morgantha) how does she greet them?` | Yes |
| `/npcaction (Name)` | `/npcaction (Ireena) she's just seen the children` | Yes |
| `/combatsummary` | `/combatsummary` | Yes |
| `/claude` | `/claude what would Morgantha do if the party refuses to eat?` | No — GM whisper only |
| `/setscene` | `/setscene the party climbs to the upper floor` | No |
| `/claudereset` | `/claudereset` | No |

**`/describe`** — Pure sensory scene description posted to chat. What you see,
hear, smell, feel. No inner states, no feelings, no narrative closure. Use this
whenever you want to set a scene for your players.

**`/npctalk (Name)`** — The NPC's spoken words only. No action, no mannerism,
no stage direction. Paste directly into FGU while talking as that character.
Include an optional direction, or leave it bare and Claude reads the room:
```
/npctalk (Morgantha) how does she respond to Ireena's accusation?
/npctalk (Morgantha)
```

**`/npcaction (Name)`** — What the NPC physically does. No dialogue. Use
alongside `/npctalk` to separate speech from action:
```
/npcaction (Morgantha) she realises no one is going to eat the pastries
```

**`/combatsummary`** — Vivid narrative of recent combat actions drawn from the
live chatlog. No dice numbers or mechanics.

**`/claude`** — Freeform GM query. Response whispered to you only — players
never see it. Use for planning, what-ifs, or anything you need to think through:
```
/claude what leverage does Morgantha have if the party attacks?
```

**`/setscene`** — Updates Claude's current scene context. Does not clear
conversation history — Claude remembers everything from earlier in the session:
```
/setscene the party has reached the cage room and found the children
```

**`/claudereset`** — Clears all conversation history and the chatlog buffer.
Use this only when you want a genuine fresh start.

---

## How It Works

```
FGU chatlog.html  →  Python monitors in real-time
                      Claude silently absorbs session events (free — no API call)

GM types /npctalk  →  FGU writes request to console.log
                       Python detects it
                       Sends full context to Anthropic API
                       Response copied to clipboard  ←  Ctrl+V into FGU chat
```

Claude's awareness of the session builds continuously throughout play. Every
attack roll, piece of dialogue, and turn marker that appears in the chatlog is
fed into Claude's context. When you issue a command, Claude already knows what
just happened.

---

## Files

```
FGClaudeBridge\                    ← your working folder (run server.py from here)
    server.py                      ← the Python middleware — run before each session
    bridge_config.json             ← settings: model, scene, tone, token limits
    campaign_history.md            ← what has been: PCs, world, session recaps
    session_notes.md               ← what is to be: tonight's scenes and NPCs

[FGU data folder]\extensions\
    fg-claude-bridge\
        extension.xml
        scripts\
            claude_bridge.lua
```

---

## Requirements

- Fantasy Grounds Unity 5.x
- Python 3.10 or newer — https://python.org
- An Anthropic API key — https://console.anthropic.com

---

## Installation

### Step 1 — Install Python

Download from https://python.org. During installation tick
**"Add Python to PATH"** on the first screen — this is important.

Verify in a new Command Prompt:
```
python --version
```

### Step 2 — Install Python Dependencies

```
pip install anthropic pyperclip
```

### Step 3 — Set Your API Key Permanently

1. Press **Win + R**, type `sysdm.cpl`, Enter
2. **Advanced** tab → **Environment Variables…**
3. Under **User variables** → **New…**
4. Variable name: `ANTHROPIC_API_KEY`
5. Variable value: `sk-ant-your-key-here`
6. OK on all dialogs

Open a **new** Command Prompt to pick up the change. Verify:
```
echo %ANTHROPIC_API_KEY%
```

### Step 4 — Create Your Working Folder

Create a folder anywhere, e.g.:
```
C:\Users\YourName\Documents\FGClaudeBridge\
```
Copy `server.py`, `bridge_config.json`, `campaign_history.md`, and
`session_notes.md` into it.

### Step 5 — Install the FG Extension

FGU 5.x stores extensions in your configured FGU data folder — not in AppData.
To find it: open FGU → Settings → Folders.

Inside the extensions folder create this exact structure:
```
extensions\
└── fg-claude-bridge\
    ├── extension.xml
    └── scripts\
        └── claude_bridge.lua
```

### Step 6 — Update the File Paths in server.py

Open `server.py` in a text editor and update these two lines near the top:
```python
CHATLOG_PATH     = Path("G:/FGU/campaigns/CoS/chatlog.html")
CONSOLE_LOG_PATH = Path("G:/FGU/console.log")
```
Set them to match your FGU data folder and campaign folder name. The chatlog is
inside your campaign folder. The console log is in the root of your FGU data folder.

### Step 7 — Enable the Extension in FGU

On the FGU campaign select screen, find the **Extensions** panel on the right.
Set the dropdown to **ALL**. Tick **Claude AI Bridge**. Click **Start**.

You should see in the FGU chat window:
```
[Claude Bridge] Loaded.
[Claude Bridge] /claude  /describe  /npctalk (Name)  /npcaction (Name)  /combatsummary  /setscene  /claudereset
```

---

## Before Each Session

### 1. Fill in your notes files

**`campaign_history.md`** — your *what has been* file. Fill in PC details,
add a session recap after each session. The more specific this is, the better
Claude's responses will be.

**`session_notes.md`** — your *what is to be* file. Prepare tonight's scenes,
NPCs, encounters, and GM notes. Claude reads this at startup and uses it to
inform every response.

Both files are plain markdown — edit them in any text editor, or use a tool
like Obsidian or VS Code. You can use a Claude.ai project to help write and
maintain them between sessions.

### 2. Start the server

Open Command Prompt in your working folder and run:
```
python server.py
```

You should see your files load with word counts confirmed. Keep this terminal
open for the whole session.

**Important:** Start the server after FGU has launched and loaded your campaign.
FGU recreates `console.log` fresh each session — if the server starts before
FGU it will miss the file creation and not pick up commands.

---

## At the Table

All commands are typed in the **FGU chat box**. They are GM-only slash commands —
players never see them being typed.

### Describing a scene
```
/describe the windmill door opening and Morgantha in the frame
/describe the kitchen — warmth, smell, the barrel of black ichor near the stairs
```
Response posted to chat, visible to all players.

### NPC dialogue
```
/npctalk (Morgantha) how does she respond to Ayleior's suspicion?
/npctalk (Ireena) she's just seen Myrtle in the cage
/npctalk (Freek)
```
Response is the NPC's spoken words only — paste it while talking as that
character in FGU.

### NPC action
```
/npcaction (Morgantha) she realises no one is going to eat the pastries
/npcaction (Ireena)
```
Response is physical behaviour only — no dialogue.

### Combat summary
```
/combatsummary
```
Fire this at the end of a combat round for a narrative description of what
just happened. Claude reads the attack rolls, hits, misses, and damage from
the live chatlog.

### Private GM query
```
/claude what are Morgantha's options if the party tries to leave with the children?
/claude how would Ireena react to Bella's behaviour?
```
Response whispered to GM only via `/w GM`. Players never see it.

### Moving to a new scene
```
/setscene the party has found the children and Ireena has gone very quiet
/setscene combat has broken out on the ground floor
```
Updates Claude's scene context. Does NOT clear conversation history — Claude
remembers everything from earlier in the session.

### Full reset
```
/claudereset
```
Clears all history. Use only when you want a genuine fresh start.

---

## How Responses Are Delivered

1. Response appears in your **terminal window**
2. Automatically **copied to clipboard**
3. Switch to FGU → click chat box → **Ctrl+V** → edit if needed → **Enter**

Player-visible responses (`/describe`, `/npctalk`, `/npcaction`, `/combatsummary`)
are plain text — paste and send.

GM-only responses (`/claude`) are prefixed `/w GM` — only you see them when sent.

---

## The Notes Files

### campaign_history.md — what has been

The persistent backbone of Claude's campaign knowledge. Contains:
- The world and its tone
- PC profiles — race, class, personality, backstory, relationships
- Session recaps — bullet points after each session
- Established facts the party has discovered
- NPC relationship tracker
- Ongoing story threads

Update this after every session. The better it is, the more Claude can make
natural callbacks to past events.

### session_notes.md — what is to be

Everything Claude needs for tonight. Contains:
- Session overview and key dramatic beats
- Scene descriptions for every location the party might visit
- Full NPC profiles — personality, voice, manner, combat behaviour
- GM notes (Claude reads these but never reveals them to players)
- Available bargains, foreshadowing, secrets

Prepare this before each session. Add new scene sections as the campaign
progresses. When a session is done, move the key events into
`campaign_history.md` and refresh this file for next time.

### bridge_config.json — settings

```json
{
  "model": "claude-haiku-4-5",
  "max_tokens": 400,
  "max_tokens_long": 800
}
```

`bridge_config.json` contains only technical settings. You should not need to
edit it between sessions.

`max_tokens` applies to `/npctalk` and `/npcaction` — dialogue and actions
should be short. `max_tokens_long` applies to `/describe`, `/combatsummary`,
and `/claude` where more room is needed.

For available model identifiers see: https://docs.anthropic.com/en/docs/about-claude/models

### Campaign name, scene, and tone — read from markdown

`campaign_name`, `current_scene`, and `tone` are no longer in `bridge_config.json`.
The server reads them directly from your markdown files at startup using these
labelled fields:

In `campaign_history.md`:
```
**Campaign:** Curse of Strahd
```

In `session_notes.md`:
```
**Opening Scene:** Old Bonegrinder — Ground Floor (Area O1)
**Tone:** Gothic horror / dark fairy tale. Hags are charming, not monstrous.
```

Update these fields in your markdown files as part of normal session prep.
The `Opening Scene` sets the starting value of `current_scene` — use `/setscene`
during play to update it as the party moves around.

---

## Approximate API Cost

At typical usage (15–25 queries per 3-hour session) with Haiku:
roughly £0.01–0.05 per session.

Cost per call increases gradually through a session as conversation history
accumulates. `/claudereset` resets the cost baseline if needed.

---

## Troubleshooting

**"Bridge Loaded" doesn't appear in FGU chat**
Check the extension is ticked in the Extensions panel (dropdown set to ALL).
Check `extension.xml` is directly inside `fg-claude-bridge\`, not inside `scripts\`.

**Commands fire but nothing appears in the terminal**
- Check `CONSOLE_LOG_PATH` in `server.py` points to the right file
- Make sure you started the server **after** FGU loaded the campaign
- Restart `server.py` if FGU was restarted — FGU recreates `console.log` fresh each time

**Responses are generic / Claude doesn't know the scene**
Check that `campaign_history.md` and `session_notes.md` are in the same folder
as `server.py`. The startup output should confirm their word counts. Fill in
your PC details in `campaign_history.md` — placeholder text produces weak responses.

**Response was truncated**
Increase `max_tokens_long` in `bridge_config.json`. 800 should be sufficient
for most descriptions; try 1200 for very detailed scenes.

**ModuleNotFoundError**
```
pip install anthropic pyperclip
```

**ANTHROPIC_API_KEY not set**
Follow Step 3 again. Open a new Command Prompt after setting the variable —
existing windows don't pick up environment variable changes.
