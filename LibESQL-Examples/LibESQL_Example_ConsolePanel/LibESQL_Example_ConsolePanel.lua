-- LibESQL_Example_ConsolePanel: Settings panel with ready-made queries (works on console)
-- An example for LibESQL. Copy it, rename it, change it.

local function Print(fmt, ...)
    local msg = select("#", ...) > 0 and string.format(fmt, ...) or tostring(fmt)
    if CHAT_ROUTER then CHAT_ROUTER:AddSystemMessage("[ConsolePanel] " .. msg) else d(msg) end
end

-- A LibHarvensAddonSettings panel: pick a query, press Run, read the result in chat.
-- This is how an add-on uses LibESQL on console, where slash commands don't exist.
-- Settings > Addons > LibESQL Example.
local QUERIES = {
    { name = "My character", data = "SELECT name, level, class, race, zone FROM character" },
    { name = "My buffs", data = "SELECT name, ROUND(remaining_s) AS s FROM effects WHERE unit = 'player' ORDER BY s DESC LIMIT 10" },
    { name = "Gold and currencies", data = "SELECT name, total FROM currencies WHERE total > 0 ORDER BY total DESC" },
    { name = "Slotted skills", data = "SELECT bar, slot, name FROM hotbar ORDER BY bar, slot" },
    { name = "Set pieces in backpack", data = "SELECT set_name, COUNT(*) AS n FROM inventory WHERE bag = 'backpack' AND set_name IS NOT NULL GROUP BY set_name ORDER BY n DESC" },
}
local selected = QUERIES[1]

local function run()
    LibESQL.QueryAsync(selected.data, function(res, err)
        if not res then Print("Error: %s", err) return end
        Print("%s: %d row(s)", selected.name, #res.rows)
        for i = 1, math.min(10, #res.rows) do
            local parts = {}
            for c, name in ipairs(res.columns) do parts[c] = name .. "=" .. tostring(res.rows[i][c]) end
            Print("  %s", table.concat(parts, ", "))
        end
    end)
end

local function itemFrom(...)
    for i = 1, select("#", ...) do
        local v = select(i, ...)
        if type(v) == "table" and v.data then return v end
    end
end

EVENT_MANAGER:RegisterForEvent("LibESQL_Example_ConsolePanel", EVENT_ADD_ON_LOADED, function(_, name)
    if name ~= "LibESQL_Example_ConsolePanel" then return end
    EVENT_MANAGER:UnregisterForEvent("LibESQL_Example_ConsolePanel", EVENT_ADD_ON_LOADED)
    local LHAS = LibHarvensAddonSettings
    if not LHAS then Print("Install LibHarvensAddonSettings for this example.") return end
    local panel = LHAS:AddAddon("LibESQL Example", { allowDefaults = false })
    panel:AddSetting({
        type = LHAS.ST_DROPDOWN, label = "Query", items = QUERIES,
        getFunction = function() return selected.name end,
        setFunction = function(...) selected = itemFrom(...) or selected end,
    })
    panel:AddSetting({ type = LHAS.ST_BUTTON, label = "Run it", buttonText = "Run", clickHandler = run })
end)
