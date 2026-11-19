-- LibESQL_Example_BuffWatcher: Buffs on you and debuffs on your target
-- An example for LibESQL. Copy it, rename it, change it.
-- Slash commands work on PC only; see LibESQL_Example_ConsolePanel for console.

local function Print(fmt, ...)
    local msg = select("#", ...) > 0 and string.format(fmt, ...) or tostring(fmt)
    if CHAT_ROUTER then CHAT_ROUTER:AddSystemMessage("[BuffWatcher] " .. msg) else d(msg) end
end

-- /mybuffs   your Major/Minor buffs from the live effects table, longest first
SLASH_COMMANDS["/mybuffs"] = function()
    local rows = LibESQL.Select([[
        SELECT name, ability_id, ROUND(remaining_s, 1) AS left_s, permanent
        FROM effects
        WHERE unit = 'player' AND (name LIKE 'major %' OR name LIKE 'minor %')
        ORDER BY permanent DESC, remaining_s DESC]]) or {}
    if #rows == 0 then Print("No Major/Minor buffs on you.") return end
    for _, b in ipairs(rows) do
        Print("  %s (%d) %s", b.name, b.ability_id, b.permanent and "permanent" or (tostring(b.left_s) .. "s"))
    end
end

-- /targetdebuffs   debuffs on your target, grouped by who applied them
SLASH_COMMANDS["/targetdebuffs"] = function()
    local rows = LibESQL.Select([[
        SELECT IIF(cast_by_player, 'you', 'others') AS source, COUNT(*) AS n,
               GROUP_CONCAT(name, ', ') AS names
        FROM effects WHERE unit = 'reticleover' AND effect_type = 'debuff'
        GROUP BY 1]]) or {}
    if #rows == 0 then Print("No target, or no debuffs on it.") return end
    for _, r in ipairs(rows) do Print("  %s (%d): %s", r.source, r.n, r.names) end
end
