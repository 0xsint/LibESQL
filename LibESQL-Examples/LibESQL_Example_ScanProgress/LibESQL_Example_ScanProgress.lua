-- LibESQL_Example_ScanProgress: Build the ability and item indexes with progress
-- An example for LibESQL. Copy it, rename it, change it.
-- Slash commands work on PC only; see LibESQL_Example_ConsolePanel for console.

local function Print(fmt, ...)
    local msg = select("#", ...) > 0 and string.format(fmt, ...) or tostring(fmt)
    if CHAT_ROUTER then CHAT_ROUTER:AddSystemMessage("[ScanProgress] " .. msg) else d(msg) end
end

-- /esqlscan        index abilities (if needed), showing progress
-- /esqlscan items  index items
local function onProgress(tableName, fraction, found)
    if fraction > 0 and fraction < 1 then Print("%s: %d%% (%d found)", tableName, fraction * 100, found or 0) end
end

SLASH_COMMANDS["/esqlscan"] = function(arg)
    local tableName = (arg == "items") and "items" or "abilities"
    local done, count = LibESQL.IsScanned(tableName)
    if done then Print("%s already indexed: %d ids", tableName, count or 0) return end
    LibESQL.RegisterCallback("ScanProgress", onProgress)
    LibESQL.Scan(tableName, function(n, err)
        LibESQL.UnregisterCallback("ScanProgress", onProgress)
        if not n then Print("Scan failed: %s", err) return end
        Print("Done: %d %s ids. They are saved until the next game update.", n, tableName)
    end)
end
