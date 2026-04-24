-- =============================================================================
-- Claude AI Bridge for Fantasy Grounds Unity 5.x (D&D 5e)
-- scripts/claude_bridge.lua
--
-- COMMANDS (GM only):
--   /claude [anything]          — freeform: describe what Ireena is doing right now
--   /npctalk (npc) [prompt]     — NPC response: /npctalk (Ireena) how does she reply to Lumina?
--   /combatsummary              — narrative description of recent combat rolls and actions
--   /setscene [description]     — update scene context, reset conversation history
--   /claudereset                — clear conversation history
-- =============================================================================

function onInit()
    if not User.isHost() then return end

    Comm.registerSlashHandler("claude",        cmdClaude,        "/claude [message] - Freeform GM query (whisper)")
    Comm.registerSlashHandler("describe",      cmdDescribe,      "/describe [scene] - Post scene description to chat")
    Comm.registerSlashHandler("npctalk",       cmdNPCTalk,       "/npctalk (NPC name) [prompt] - NPC speaks in dialogue")
    Comm.registerSlashHandler("npcaction",     cmdNPCAction,     "/npcaction (NPC name) [prompt] - NPC action or reaction")
    Comm.registerSlashHandler("combatsummary", cmdCombatSummary, "/combatsummary - Narrative description of recent combat")
    Comm.registerSlashHandler("setscene",      cmdSetScene,      "/setscene [description] - Update scene, reset history")
    Comm.registerSlashHandler("claudereset",   cmdReset,         "/claudereset - Clear conversation history")

    ChatManager.SystemMessage("[Claude Bridge] Loaded.")
    ChatManager.SystemMessage("[Claude Bridge] /claude  /describe  /npctalk (Name)  /npcaction (Name)  /combatsummary  /setscene  /claudereset")
end

-- ---------------------------------------------------------------------------
-- Send a request to Python via console.log
-- ---------------------------------------------------------------------------
function sendRequest(reqType, message, npc)
    local function esc(s)
        s = (s or ""):gsub("\\", "\\\\"):gsub('"', '\\"'):gsub("\n", "\\n"):gsub("\r", "")
        return s
    end
    local payload = string.format(
        '{"type":"%s","message":"%s","npc":"%s"}',
        esc(reqType), esc(message), esc(npc or "")
    )
    print("CLAUDE_BRIDGE_REQUEST:" .. payload)
    Debug.console("[Claude Bridge] Request sent.")
end

-- ---------------------------------------------------------------------------
-- Command handlers
-- ---------------------------------------------------------------------------

-- /claude describe what Ireena is doing right now
function cmdClaude(sCommand, sParams)
    if not sParams or sParams:match("^%s*$") then
        ChatManager.SystemMessage("Usage: /claude [question or description request]")
        return
    end
    sendRequest("general", sParams, nil)
end

-- /npctalk (Ireena) how does she reply to Lumina?
function cmdNPCTalk(sCommand, sParams)
    if not sParams or sParams:match("^%s*$") then
        ChatManager.SystemMessage("Usage: /npctalk (NPC Name) [prompt]")
        ChatManager.SystemMessage("Example: /npctalk (Ireena) how does she reply to Lumina?")
        return
    end
    local npc, prompt = sParams:match("^%((.-)%)%s*(.+)$")
    if not npc then
        -- Allow bare /npctalk (Ireena) with no additional prompt
        npc = sParams:match("^%((.-)%)%s*$")
        prompt = ""
    end
    if not npc then
        ChatManager.SystemMessage("Usage: /npctalk (NPC Name) [optional prompt]  — NPC name must be in (parentheses)")
        return
    end
    sendRequest("npc_dialogue", prompt, npc)
end

-- /npcaction (Kiril) he's just been hit — what does he do?
function cmdNPCAction(sCommand, sParams)
    if not sParams or sParams:match("^%s*$") then
        ChatManager.SystemMessage("Usage: /npcaction (NPC Name) [optional prompt]")
        ChatManager.SystemMessage("Example: /npcaction (Kiril) he's just been wounded — what does he do?")
        return
    end
    local npc, prompt = sParams:match("^%((.-)%)%s*(.+)$")
    if not npc then
        -- Allow bare /npcaction (Ireena) with no additional prompt
        npc = sParams:match("^%((.-)%)%s*$")
        prompt = ""
    end
    if not npc then
        ChatManager.SystemMessage("Usage: /npcaction (NPC Name) [optional prompt]  — NPC name must be in (parentheses)")
        return
    end
    sendRequest("npc_action", prompt, npc)
end

-- /describe the party approaching old bonegrinder at dusk
function cmdDescribe(sCommand, sParams)
    if not sParams or sParams:match("^%s*$") then
        ChatManager.SystemMessage("Usage: /describe [what to describe]")
        return
    end
    sendRequest("describe", sParams, nil)
end

-- /combatsummary
function cmdCombatSummary(sCommand, sParams)
    sendRequest("combat_summary", "Describe the recent combat actions and rolls.", nil)
end

-- /setscene the party emerges from the forest into the village of Vallaki
function cmdSetScene(sCommand, sParams)
    if not sParams or sParams:match("^%s*$") then
        ChatManager.SystemMessage("Usage: /setscene [description of new location or situation]")
        return
    end
    sendRequest("set_scene", sParams, nil)
end

-- /claudereset
function cmdReset(sCommand, sParams)
    sendRequest("reset", "reset", nil)
end
