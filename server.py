#!/usr/bin/env python3
"""
Claude AI Bridge — Live Session Monitor
=========================================
Feeds FGU chatlog events into Claude's conversation history in real-time.
Claude silently accumulates session context as it happens.
When the GM issues a slash command, Claude already knows everything.

Requirements:
    pip install anthropic pyperclip

Usage:
    python server.py

Files (all in the same folder as server.py):
    bridge_config.json   — machine-readable settings (model, scene, tone)
    campaign_history.md  — what has been: PCs, world, session recaps, lore
    session_notes.md     — what is to be: tonight's scenes, NPCs, GM notes
"""

import os, sys, json, time, signal, re
from pathlib import Path
from html import unescape

import anthropic
import pyperclip

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
CHATLOG_PATH     = Path("G:/FGU/campaigns/CoS/chatlog.html")
CONSOLE_LOG_PATH = Path("G:/FGU/console.log")

CONFIG_FILE  = Path("bridge_config.json")
HISTORY_FILE = Path("campaign_history.md")
NOTES_FILE   = Path("session_notes.md")

POLL_INTERVAL    = 0.4   # seconds between file checks
EVENT_FLUSH_SEC  = 3.0   # batch chatlog events and flush every N seconds
HISTORY_LIMIT    = 80    # max messages in conversation history before trimming

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
conversation_history : list[dict] = []
pending_events       : list[str]  = []
last_flush_time      : float      = 0.0
config               : dict       = {}
campaign_history     : str        = ""
session_notes        : str        = ""
chatlog_position     : int        = 0
consolelog_position  : int        = 0

# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
def load_config() -> dict:
    if not CONFIG_FILE.exists():
        print(f"ERROR: {CONFIG_FILE} not found.")
        sys.exit(1)
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


def extract_field(text: str, field: str) -> str:
    """Extract a **Field:** value from a markdown file. Returns empty string if not found."""
    escaped = re.escape(field)
    m = re.search(r'^\*\*' + escaped + r':\*\*\s*(.+)$', text, re.MULTILINE)
    return m.group(1).strip() if m else ""


def load_meta_from_markdown(history: str, notes: str) -> dict:
    """
    Read campaign_name from campaign_history.md and
    current_scene and tone from session_notes.md.
    These replace the equivalent fields previously in bridge_config.json.
    """
    campaign_name  = extract_field(history, "Campaign")  or "Unknown Campaign"
    current_scene  = extract_field(notes,   "Opening Scene") or "Unknown location"
    tone           = extract_field(notes,   "Tone") or "Classic heroic fantasy"

    print(f"  Campaign     : {campaign_name}")
    print(f"  Opening scene: {current_scene}")
    print(f"  Tone         : {tone[:60]}{'...' if len(tone) > 60 else ''}")

    return {
        "campaign_name":  campaign_name,
        "current_scene":  current_scene,
        "tone":           tone,
    }

def load_markdown(path: Path, label: str) -> str:
    if not path.exists():
        print(f"  WARNING: {path} not found — Claude will run without {label}.")
        return ""
    with open(path, encoding="utf-8") as f:
        text = f.read().strip()
    print(f"  {label}: {path}  ({len(text.split()):,} words)")
    return text

def init_file_positions():
    global chatlog_position, consolelog_position
    for path, attr, label in [
        (CHATLOG_PATH,     "chatlog_position",    "Chatlog"),
        (CONSOLE_LOG_PATH, "consolelog_position", "Console log"),
    ]:
        if path.exists():
            size = path.stat().st_size
            globals()[attr] = size
            print(f"  {label}: {path}  ({size:,} bytes — skipping existing content)")
        else:
            print(f"  {label}: not found at {path} — will watch for it.")

# ---------------------------------------------------------------------------
# Chatlog HTML parser
# ---------------------------------------------------------------------------
def parse_chatlog_line(raw: str) -> str | None:
    """
    Convert one FGU chatlog HTML line to plain text, or None to skip.

    Colour codes:
      #261A12 = chat messages and turn markers
      #660066 = game mechanics (rolls, attacks, damage, initiative)
      #880000 = ruleset/system notices  → skip
      #000000 = extension load notices  → skip
    """
    m = re.match(r'<font color="(#[0-9A-Fa-f]+)">(.*?)</font>(.*)', raw, re.DOTALL)
    if not m:
        return None
    color, content, extra = m.groups()

    if color.lower() in ('#880000', '#000000'):
        return None

    # Skip bridge system messages and Claude's own responses
    # to prevent them feeding back into Claude's context
    skip_prefixes = ('[Claude Bridge]', '[Claude]:', '[Claude Bridge] Request sent')
    for prefix in skip_prefixes:
        if content.strip().startswith(prefix):
            return None

    content = re.sub(r'<[^>]+>', '', unescape(content)).strip()
    extra   = re.sub(r'<br\s*/?>', '', re.sub(r'<[^>]+>', '', unescape(extra))).strip()

    if not content:
        return None

    combined = f"{content} {extra}".strip() if extra else content
    return f"[ROLL] {combined}" if color.lower() == '#660066' else combined

# ---------------------------------------------------------------------------
# Feed chatlog events into conversation history
# ---------------------------------------------------------------------------
def flush_events_to_history():
    global pending_events, last_flush_time

    if not pending_events:
        return

    batch = "\n".join(pending_events)
    pending_events = []
    last_flush_time = time.time()

    # Merge into existing TABLE block if last exchange was also a silent flush
    if (len(conversation_history) >= 2
            and conversation_history[-1]["role"] == "assistant"
            and conversation_history[-1]["content"] == "."
            and conversation_history[-2]["role"] == "user"
            and conversation_history[-2]["content"].startswith("[TABLE]")):
        conversation_history[-2]["content"] += "\n" + batch
    else:
        conversation_history.append({"role": "user",      "content": f"[TABLE]\n{batch}"})
        conversation_history.append({"role": "assistant", "content": "."})

    # Trim from the front in pairs to keep alternation valid
    while len(conversation_history) > HISTORY_LIMIT:
        conversation_history.pop(0)
        conversation_history.pop(0)

    line_count = batch.count("\n") + 1
    print(f"  [context] +{line_count} event(s) absorbed into session history")

def poll_chatlog():
    global chatlog_position

    if not CHATLOG_PATH.exists():
        return

    size = CHATLOG_PATH.stat().st_size
    if size < chatlog_position:
        print("  Chatlog recreated — resetting position.")
        chatlog_position = 0
    if size <= chatlog_position:
        return

    try:
        with open(CHATLOG_PATH, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(chatlog_position)
            new_content = f.read()
        chatlog_position = size
    except Exception as e:
        print(f"  Chatlog read error: {e}")
        return

    for raw in new_content.splitlines():
        parsed = parse_chatlog_line(raw)
        if parsed:
            pending_events.append(parsed)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
def build_system_prompt() -> list:
    """
    Returns a list of system prompt blocks with cache_control markers on the
    static markdown files. Anthropic caches these server-side for 5 minutes,
    charging ~90% less for cached input tokens on subsequent calls within
    that window. The instructions block is NOT cached as current_scene changes.
    """
    blocks = []

    if campaign_history:
        blocks.append({
            "type": "text",
            "text": (
                "================================================================================\n"
                "CAMPAIGN HISTORY — what has happened so far\n"
                "================================================================================\n"
                f"{campaign_history}\n"
                "================================================================================"
            ),
            "cache_control": {"type": "ephemeral"}
        })

    if session_notes:
        blocks.append({
            "type": "text",
            "text": (
                "================================================================================\n"
                "SESSION NOTES — current session scenes, NPCs, and GM notes\n"
                "================================================================================\n"
                f"{session_notes}\n"
                "================================================================================"
            ),
            "cache_control": {"type": "ephemeral"}
        })

    # Instructions block is NOT cached — current_scene changes with /setscene
    blocks.append({
        "type": "text",
        "text": f"""You are the narrating voice and NPC actor for a D&D 5e campaign.

CAMPAIGN: {config.get('campaign_name', 'Unknown Campaign')}
CURRENT SCENE: {config.get('current_scene', 'Unknown location')}
TONE: {config.get('tone', 'Classic heroic fantasy')}

HOW TO READ THIS CONVERSATION:
Messages prefixed with [TABLE] are live session events fed from the VTT —
player chat, GM narration, dice rolls, combat mechanics. Absorb these silently
as they arrive. Never respond to [TABLE] messages directly. Wait for a GM command.

When a GM command arrives, use everything you have observed to give a response
that is immediate, specific, and grounded in what just happened at the table.

RESPONSE RULES:
- /npctalk: return ONLY the NPC's spoken words. First person. 2-4 sentences.
  No action, no stage direction. Just what they say out loud.
- /npcaction: return ONLY what the NPC physically does or how they react.
  2-3 sentences of behaviour and body language. No spoken dialogue.
- /combatsummary: describe recent combat rolls and actions as vivid narrative.
  What the players see and feel. No mechanics or dice numbers.
- /describe: pure sensory description only. Address players as "you".
- /claude: answer the GM's question helpfully and specifically. Draw on all
  available context — history, session notes, and live table events.
- Never mention dice, stats, or game mechanics unless the GM explicitly asks.
- Never break the fourth wall.
- Never reveal GM secrets from the session notes (future plans, hidden motives,
  upcoming reveals). That knowledge informs your tone and consistency only.
- CRITICAL: Never ask the GM for more information. Never respond with questions
  or requests for clarification. If details are missing, make confident creative
  inferences based on context and respond fully. A non-answer is always worse
  than an informed assumption.
- Always address the players as "you" — never "the party" or "the adventurers".
- Never describe what a character feels, knows, senses, or thinks unless it is
  directly observable — no inner states, no emotional speculation.
- Never add concluding statements, narrative closure, or summarising sentences.
  Stop when the content stops. Do not round off.
- Be concise. This is a game, not a novel. Every sentence must earn its place.
- Tone: {config.get('tone', 'classic heroic fantasy')}."""
    })

    return blocks

# ---------------------------------------------------------------------------
# Request processing
# ---------------------------------------------------------------------------
def process_request(req: dict) -> tuple[str, str]:
    global conversation_history, config

    req_type = req.get("type", "general")

    if req_type == "reset":
        conversation_history = []
        pending_events.clear()
        return "Conversation history and event buffer cleared.", "system"

    if req_type == "set_scene":
        config["current_scene"] = req.get("message", "")
        return f"Scene updated: {config['current_scene']}", "system"

    # Flush any pending events before responding
    flush_events_to_history()

    message = req.get("message", "").strip()
    npc     = req.get("npc", "").strip()

    if req_type == "describe":
        user_msg = (f"Describe the following for the players: {message}\n"
                    f"Address the players directly as 'you' — never 'the party'. "
                    f"Pure sensory description only: what you see, hear, smell, feel. "
                    f"No feelings, emotions, or inner states of any character. "
                    f"No speculation about what anyone is thinking or knowing. "
                    f"No concluding statement or narrative closure. "
                    f"Stop when the description is complete. "
                    f"3-5 sentences unless the scene genuinely warrants more.")

    elif req_type == "npc_dialogue":
        direction = f"\nGM direction: {message}" if message else ""
        user_msg = (f"NPC: {npc}{direction}\n"
                    f"Return ONLY the exact words {npc} speaks out loud. "
                    f"First person. 2-4 sentences. "
                    f"Absolutely no action, mannerism, body language, or stage direction. "
                    f"No quotes around the words. Just the raw spoken dialogue.")

    elif req_type == "npc_action":
        direction = f"\nGM direction: {message}" if message else ""
        user_msg = (f"NPC: {npc}{direction}\n"
                    f"Describe ONLY what {npc} physically does or how they react. "
                    f"2-3 sentences of action and body language. "
                    f"Absolutely no spoken dialogue or quoted speech whatsoever.")

    elif req_type == "combat_summary":
        user_msg = ("Describe ONLY the combat actions and rolls that appear in the "
                    "session events above — nothing more. Be concise but retain "
                    "good narrative — vivid and grounded, not padded. "
                    "No invented atmosphere, no speculation about feelings or thoughts, "
                    "no concluding statements. Stop when the events stop. "
                    "No mechanics or dice numbers.")
    else:
        user_msg = message

    conversation_history.append({"role": "user", "content": user_msg})

    while len(conversation_history) > HISTORY_LIMIT:
        conversation_history.pop(0)
        conversation_history.pop(0)

    # Use a higher token limit for description-heavy commands
    if req_type in ("describe", "combat_summary", "general"):
        max_tok = config.get("max_tokens_long", 800)
    else:
        max_tok = config.get("max_tokens", 400)

    client   = anthropic.Anthropic()
    response = client.messages.create(
        model         = config.get("model", "claude-sonnet-4-6"),
        max_tokens    = max_tok,
        system        = build_system_prompt(),   # list of blocks with cache_control
        messages      = conversation_history,
        extra_headers = {"anthropic-beta": "prompt-caching-2024-07-31"}
    )
    reply = response.content[0].text.strip()
    conversation_history.append({"role": "assistant", "content": reply})

    # Show cache status in terminal so GM can see when caching is active
    usage = response.usage
    cached = getattr(usage, "cache_read_input_tokens", 0) or 0
    created = getattr(usage, "cache_creation_input_tokens", 0) or 0
    if cached > 0:
        print(f"  [cache] HIT — {cached:,} tokens read from cache ✓")
    elif created > 0:
        print(f"  [cache] BUILT — {created:,} tokens cached for next call")

    return reply, req_type

# ---------------------------------------------------------------------------
# Copy response to clipboard and display in terminal
# ---------------------------------------------------------------------------
def clean_response(text: str) -> str:
    """Strip quotes, leading/trailing whitespace, and any AI preamble."""
    text = text.strip()
    # Remove surrounding quotes if the whole response is wrapped in them
    if text.startswith('"') and text.endswith('"'):
        text = text[1:-1].strip()
    # Remove any lines that are just the command echo (e.g. "/npctalk")
    lines = [l for l in text.splitlines() if not l.strip().startswith('/')]
    text = "\n".join(lines).strip()
    return text


def deliver_response(text: str, req_type: str):
    """
    GM-only responses (/claude, /setscene, system) are prefixed /w GM so
    only the GM sees them when pasted into FGU chat.
    Player-visible responses (/npctalk, /npcaction, /combatsummary) are plain.
    All responses are cleaned of quotes and formatting artefacts before delivery.
    """
    text = clean_response(text)

    if req_type in ("general", "set_scene", "reset", "system"):
        chat_text = f"/w GM {text}"
        label = "GM ONLY — whisper"
    else:
        chat_text = text
        label = "POST TO CHAT"

    pyperclip.copy(chat_text)

    print(f"\n{'='*60}")
    print(f"  [{label}]  Ctrl+V into FGU chat → Enter")
    print(f"  {text}")
    print(f"{'='*60}\n")

# ---------------------------------------------------------------------------
# Console log monitor — GM slash commands
# ---------------------------------------------------------------------------
def poll_console_log():
    global consolelog_position

    if not CONSOLE_LOG_PATH.exists():
        return

    size = CONSOLE_LOG_PATH.stat().st_size
    if size < consolelog_position:
        print("  Console log recreated — resetting position.")
        consolelog_position = 0
    if size <= consolelog_position:
        return

    try:
        with open(CONSOLE_LOG_PATH, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(consolelog_position)
            new_content = f.read()
        consolelog_position = size
    except Exception as e:
        print(f"  Console log read error: {e}")
        return

    for line in new_content.splitlines():
        m = re.search(r"CLAUDE_BRIDGE_REQUEST:(\{.+\})", line)
        if not m:
            continue
        try:
            req = json.loads(m.group(1).strip())
        except json.JSONDecodeError as e:
            print(f"  JSON parse error: {e}")
            continue

        req_type = req.get("type", "general")
        print(f"[{time.strftime('%H:%M:%S')}] GM command: {req_type}"
              + (f" — {req.get('message','')[:50]}" if req.get('message') else "")
              + (f" (NPC: {req.get('npc','')})" if req.get('npc') else ""))

        try:
            reply, rtype = process_request(req)
            deliver_response(reply, rtype)
        except anthropic.APIError as e:
            print(f"  API error: {e}")
            deliver_response(f"[API Error] {e}", "system")
        except Exception as e:
            print(f"  Unexpected error: {e}")
            deliver_response(f"[Server Error] {e}", "system")

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def main():
    global config, campaign_history, session_notes, last_flush_time

    print("=" * 60)
    print("  Claude AI Bridge — Live Session Monitor")
    print("=" * 60)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\nERROR: ANTHROPIC_API_KEY environment variable not set.")
        print("Run:  set ANTHROPIC_API_KEY=sk-ant-your-key-here")
        sys.exit(1)

    print("\nLoading files:")
    config           = load_config()
    campaign_history = load_markdown(HISTORY_FILE, "Campaign history")
    session_notes    = load_markdown(NOTES_FILE,   "Session notes  ")

    # Read campaign_name, current_scene, tone from markdown files
    meta = load_meta_from_markdown(campaign_history, session_notes)
    config.update(meta)

    init_file_positions()
    last_flush_time  = time.time()

    print(f"\nModel    : {config.get('model','—')}  "
          f"(max {config.get('max_tokens','—')} tokens/response)")
    print(f"\nListening. Claude will silently absorb session events in real-time.")
    print(f"Commands in FGU: /claude  /npctalk (Name)  /npcaction (Name)"
          f"  /combatsummary  /setscene  /claudereset")
    print(f"\nResponses appear here and are copied to clipboard automatically.")
    print(f"Switch to FGU, click the chat box, Ctrl+V, Enter.\n")
    print(f"Press Ctrl-C to stop.\n")

    def _shutdown(sig, frame):
        print("\nShutting down.")
        sys.exit(0)
    signal.signal(signal.SIGINT, _shutdown)

    while True:
        poll_chatlog()
        poll_console_log()
        if pending_events and (time.time() - last_flush_time) >= EVENT_FLUSH_SEC:
            flush_events_to_history()
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
