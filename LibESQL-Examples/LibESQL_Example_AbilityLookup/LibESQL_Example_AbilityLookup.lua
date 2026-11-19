-- LibESQL_Example_AbilityLookup: Ability lookup by id or name
-- An example for LibESQL. Copy it, rename it, change it.
-- Slash commands work on PC only; see LibESQL_Example_ConsolePanel for console.

local function Print(fmt, ...)
    local msg = select("#", ...) > 0 and string.format(fmt, ...) or tostring(fmt)
    if CHAT_ROUTER then CHAT_ROUTER:AddSystemMessage("[AbilityLookup] " .. msg) else d(msg) end
end

-- /abil 46340      look up one id (instant, no index needed)
-- /abil whip       search names (the first time builds the ability index in the background)
SLASH_COMMANDS["/abil"] = function(arg)
    arg = (arg or ""):gsub("^%s+", ""):gsub("%s+$", "")
    if arg == "" then Print("Usage: /abil <id or name>") return end

    local id = tonumber(arg)
    if id then
        local rows = LibESQL.Select([[SELECT id, name, duration_ms, cost, cost_mechanic, target, max_range, description
                                      FROM abilities WHERE id = ?]], { id })
        local a = rows and rows[1]
        if not a then Print("No ability %d", id) return end
        Print("%d %s: %.1fs, %d %s, %s, %dm", a.id, a.name or "?", (a.duration_ms or 0) / 1000,
            a.cost or 0, a.cost_mechanic or "-", a.target or "-", (a.max_range or 0) / 100)
        Print("  %s", a.description or "")
        return
    end

    if not LibESQL.IsScanned("abilities") then Print("Building the ability index once, this takes a few seconds...") end
    -- QueryAsync spreads the work over frames, so the game doesn't freeze
    LibESQL.QueryAsync("SELECT id, name FROM abilities WHERE name LIKE ? ORDER BY name, id LIMIT 20",
        function(res, err)
            if not res then Print("Error: %s", err) return end
            Print("%d match(es) for '%s':", #res.rows, arg)
            for _, r in ipairs(res.rows) do Print("  %d  %s", r[1], r[2]) end
        end,
        { params = { "%" .. arg .. "%" } })
end
