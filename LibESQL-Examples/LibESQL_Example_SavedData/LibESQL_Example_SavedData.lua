-- LibESQL_Example_SavedData: a to-do list kept in a saved SQL table
-- An example for LibESQL. Copy it, rename it, change it.
-- Slash commands work on PC only; see LibESQL_Example_ConsolePanel for console.
--
--   /todo add Farm Kinras's Wrath     add an item
--   /todo                             list open items
--   /todo all                         list everything
--   /todo done 3   /todo undo 3       mark item 3 done / not done
--   /todo del 3                       delete item 3
--   /todo clean                       delete every done item
--
-- The table lives in LibESQL_SV, so the list is still there after /reloadui
-- or logging out. You can also read it in the ESQL window: SELECT * FROM todo

local function Print(fmt, ...)
    local msg = select("#", ...) > 0 and string.format(fmt, ...) or tostring(fmt)
    if CHAT_ROUTER then CHAT_ROUTER:AddSystemMessage("[SavedData] " .. msg) else d(msg) end
end

-- Run a statement and report errors in chat. Returns the result or nil.
local function run(sql, ...)
    -- n keeps a nil in the middle (a NULL) from cutting off the values after it
    local params = { ... }
    params.n = select("#", ...)
    local res, err = LibESQL.Query(sql, { params = params })
    if not res then Print("Error: %s", err) end
    return res
end

local function list(showAll)
    local rows = LibESQL.Select([[
        SELECT id, text, done, zone
        FROM todo
        WHERE ? OR NOT done
        ORDER BY done, id]], { showAll and true or false }) or {}
    if #rows == 0 then Print(showAll and "The list is empty." or "Nothing to do. /todo add <text>") return end
    for _, t in ipairs(rows) do
        Print("  %s %d. %s%s", t.done and "[x]" or "[ ]", t.id, t.text, t.zone and ("  (" .. t.zone .. ")") or "")
    end
end

local function setDone(id, done)
    local res = run("UPDATE todo SET done = ?, done_at = ? WHERE id = ?", done, done and GetTimeStamp() or nil, id)
    if res and res.rowsAffected == 0 then Print("No item %d.", id) elseif res then list() end
end

SLASH_COMMANDS["/todo"] = function(arg)
    local cmd, rest = (arg or ""):match("^%s*(%S*)%s*(.-)%s*$")
    cmd = cmd:lower()
    local id = tonumber(rest)

    if cmd == "" then
        list(false)
    elseif cmd == "all" then
        list(true)
    elseif cmd == "add" and rest ~= "" then
        -- the next id: one more than the highest so far
        local nextId = LibESQL.Scalar("SELECT COALESCE(MAX(id), 0) + 1 FROM todo")
        if run("INSERT INTO todo (id, text, done, zone, created_at) VALUES (?, ?, FALSE, ?, ?)",
                nextId, rest, zo_strformat("<<1>>", GetUnitZone("player")), GetTimeStamp()) then
            Print("Added %d. %s", nextId, rest)
        end
    elseif (cmd == "done" or cmd == "undo") and id then
        setDone(id, cmd == "done")
    elseif cmd == "del" and id then
        local res = run("DELETE FROM todo WHERE id = ?", id)
        if res then Print(res.rowsAffected > 0 and "Deleted %d." or "No item %d.", id) end
    elseif cmd == "clean" then
        local res = run("DELETE FROM todo WHERE done")
        if res then Print("Removed %d done item(s).", res.rowsAffected) end
    else
        Print("Usage: /todo [all] | add <text> | done <n> | undo <n> | del <n> | clean")
    end
end

-- Create the table once. LibESQL has loaded its SavedVariables before this
-- add-on's EVENT_ADD_ON_LOADED, so an existing table is already there and
-- IF NOT EXISTS leaves it alone.
EVENT_MANAGER:RegisterForEvent("LibESQL_Example_SavedData", EVENT_ADD_ON_LOADED, function(_, name)
    if name ~= "LibESQL_Example_SavedData" then return end
    EVENT_MANAGER:UnregisterForEvent("LibESQL_Example_SavedData", EVENT_ADD_ON_LOADED)
    run([[CREATE TABLE IF NOT EXISTS todo (
            id INT, text TEXT, done BOOL, zone TEXT, created_at INT, done_at INT)]])
end)
