-- LibESQL_Example_CustomFunction: Add your own SQL functions
-- An example for LibESQL. Copy it, rename it, change it.
-- Slash commands work on PC only; see LibESQL_Example_ConsolePanel for console.

local function Print(fmt, ...)
    local msg = select("#", ...) > 0 and string.format(fmt, ...) or tostring(fmt)
    if CHAT_ROUTER then CHAT_ROUTER:AddSystemMessage("[CustomFunction] " .. msg) else d(msg) end
end

-- Registers two SQL functions, usable in any query by any add-on (and in /esql):
--   SECONDS(ms) -> ms / 1000
--   METERS(cm)  -> cm / 100
LibESQL.RegisterFunction("SECONDS", function(ms) return ms and ms / 1000 end)
LibESQL.RegisterFunction("METERS", function(cm) return cm and cm / 100 end)

-- /esqlfn   your slotted skills with duration in seconds and range in meters
SLASH_COMMANDS["/esqlfn"] = function()
    local rows, err = LibESQL.Select([[
        SELECT h.bar, h.slot, h.name, SECONDS(a.duration_ms) AS secs, METERS(a.max_range) AS range_m
        FROM hotbar h JOIN abilities a ON a.id = h.ability_id
        ORDER BY h.bar, h.slot]])
    if not rows then Print("Error: %s", err) return end
    for _, r in ipairs(rows) do
        Print("  %s %d  %s  %.1fs  %dm", r.bar, r.slot, r.name or "?", r.secs or 0, r.range_m or 0)
    end
end
