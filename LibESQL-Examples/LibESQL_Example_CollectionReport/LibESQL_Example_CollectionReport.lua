-- LibESQL_Example_CollectionReport: GROUP BY report of your collections
-- An example for LibESQL. Copy it, rename it, change it.
-- Slash commands work on PC only; see LibESQL_Example_ConsolePanel for console.

local function Print(fmt, ...)
    local msg = select("#", ...) > 0 and string.format(fmt, ...) or tostring(fmt)
    if CHAT_ROUTER then CHAT_ROUTER:AddSystemMessage("[CollectionReport] " .. msg) else d(msg) end
end

-- /mycollection   owned vs total per collectible category
SLASH_COMMANDS["/mycollection"] = function()
    LibESQL.QueryAsync([[
        SELECT category_type, SUM(unlocked) AS owned, COUNT(*) AS total,
               ROUND(100.0 * SUM(unlocked) / COUNT(*)) AS pct
        FROM collectibles
        GROUP BY category_type
        HAVING COUNT(*) >= 10
        ORDER BY pct DESC]], function(res, err)
        if not res then Print("Error: %s", err) return end
        for _, r in ipairs(LibESQL.ToObjects(res)) do
            Print("  %s: %d / %d (%d%%)", r.category_type or "?", r.owned or 0, r.total, r.pct or 0)
        end
    end)
end
