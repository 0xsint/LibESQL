-- LibESQL_Example_CombatSummary: Top abilities after each fight
-- An example for LibESQL. Copy it, rename it, change it.

local function Print(fmt, ...)
    local msg = select("#", ...) > 0 and string.format(fmt, ...) or tostring(fmt)
    if CHAT_ROUTER then CHAT_ROUTER:AddSystemMessage("[CombatSummary] " .. msg) else d(msg) end
end

-- Records combat events while you fight, prints your top 5 damage abilities
-- when combat ends, then clears the log. No commands: just fight something.
local DAMAGE = "('damage', 'critical_damage', 'dot_tick', 'dot_tick_critical')"

local function onCombatState(_, inCombat)
    if inCombat then
        LibESQL.ClearCombatLog()
        LibESQL.SetCombatLogging(true)
        return
    end
    LibESQL.SetCombatLogging(false)
    local sum = LibESQL.Scalar("SELECT SUM(hit) FROM combat_log WHERE source_type = 'player' AND result IN " .. DAMAGE) or 0
    if sum == 0 then return end
    local rows = LibESQL.Select([[
        SELECT ability, SUM(hit) AS total, COUNT(*) AS hits,
               ROUND(100.0 * SUM(IIF(result LIKE '%critical%', 1, 0)) / COUNT(*)) AS crit_pct
        FROM combat_log
        WHERE source_type = 'player' AND result IN ]] .. DAMAGE .. [[
        GROUP BY ability
        ORDER BY total DESC
        LIMIT 5]]) or {}
    Print("Fight over: %d damage", sum)
    for i, r in ipairs(rows) do
        Print("  %d. %s  %d (%d%%) in %d hits, %d%% crit", i, r.ability or "?", r.total, r.total * 100 / sum, r.hits, r.crit_pct or 0)
    end
end

EVENT_MANAGER:RegisterForEvent("LibESQL_Example_CombatSummary", EVENT_PLAYER_COMBAT_STATE, onCombatState)
