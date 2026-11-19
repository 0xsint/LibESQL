-- LibESQL_Example_CustomTable: Register your own table and query it
-- An example for LibESQL. Copy it, rename it, change it.
-- Slash commands work on PC only; see LibESQL_Example_ConsolePanel for console.

local function Print(fmt, ...)
    local msg = select("#", ...) > 0 and string.format(fmt, ...) or tostring(fmt)
    if CHAT_ROUTER then CHAT_ROUTER:AddSystemMessage("[CustomTable] " .. msg) else d(msg) end
end

-- Logs your deaths into a table called my_deaths that any SQL query can read,
-- including the ESQL window: SELECT * FROM my_deaths
-- /mydeaths   deaths per zone
local deaths = {}

LibESQL.RegisterTable({
    name = "my_deaths",
    desc = "Deaths this session (LibESQL_Example_CustomTable)",
    live = true,                      -- rebuild every query: the list keeps growing
    columns = {
        { "n", "int", "Death number" },
        { "time", "int", "Unix time" },
        { "zone", "text", "Zone" },
        { "killer", "text", "Last enemy that hit you" },
        -- a lazy column: only computed when a query reads it
        { "clock", "text", "Time of day", function(row) return os and os.date and os.date("%H:%M:%S", row.time) or tostring(row.time) end },
    },
    build = function(rows)
        for i, d in ipairs(deaths) do
            rows[i] = { n = i, time = d.time, zone = d.zone, killer = d.killer }
        end
    end,
})

local lastAttacker
EVENT_MANAGER:RegisterForEvent("LibESQL_Example_CustomTable", EVENT_COMBAT_EVENT,
    function(_, result, isError, _, _, _, sourceName, _, _, targetType)
        if targetType == COMBAT_UNIT_TYPE_PLAYER and sourceName and sourceName ~= "" then
            lastAttacker = zo_strformat("<<1>>", sourceName)
        end
    end)
EVENT_MANAGER:RegisterForEvent("LibESQL_Example_CustomTable", EVENT_PLAYER_DEAD, function()
    deaths[#deaths + 1] = { time = GetTimeStamp(), zone = zo_strformat("<<1>>", GetUnitZone("player")), killer = lastAttacker }
end)

SLASH_COMMANDS["/mydeaths"] = function()
    local rows = LibESQL.Select("SELECT zone, COUNT(*) AS n, MAX(clock) AS last FROM my_deaths GROUP BY zone ORDER BY n DESC") or {}
    if #rows == 0 then Print("No deaths yet. Nice.") return end
    for _, r in ipairs(rows) do Print("  %s: %d (last at %s)", r.zone, r.n, r.last) end
end
