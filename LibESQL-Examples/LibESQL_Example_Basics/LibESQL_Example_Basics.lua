-- LibESQL_Example_Basics: Basics: Query, Select, Scalar and ? parameters
-- An example for LibESQL. Copy it, rename it, change it.
-- Slash commands work on PC only; see LibESQL_Example_ConsolePanel for console.

local function Print(fmt, ...)
    local msg = select("#", ...) > 0 and string.format(fmt, ...) or tostring(fmt)
    if CHAT_ROUTER then CHAT_ROUTER:AddSystemMessage("[Basics] " .. msg) else d(msg) end
end

-- /esqlbasics : the four ways to read data.
SLASH_COMMANDS["/esqlbasics"] = function()
    -- 1. Query: a result with columns and rows (arrays). nil + error text on failure.
    local res, err = LibESQL.Query("SELECT name, level, class, zone FROM character")
    if not res then Print("Error: %s", err) return end
    local row = res.rows[1]
    Print("You are %s, level %d %s in %s", row[1], row[2], row[3], row[4])

    -- 2. Scalar: one value.
    local done = LibESQL.Scalar("SELECT COUNT(*) FROM achievements WHERE completed")
    local total = LibESQL.Scalar("SELECT COUNT(*) FROM achievements")
    Print("Achievements: %d of %d", done or 0, total or 0)

    -- 3. Select: rows as objects, with ? parameters (never paste player text into SQL).
    local rows = LibESQL.Select("SELECT name, total FROM currencies WHERE total > ? ORDER BY total DESC LIMIT ?", { 0, 5 })
    for _, c in ipairs(rows or {}) do
        Print("  %s: %s", c.name, ZO_CommaDelimitNumber and ZO_CommaDelimitNumber(c.total) or c.total)
    end

    -- 4. Errors come back as text.
    local _, e = LibESQL.Query("SELECT nope FROM character")
    Print("An error looks like: %s", e)
end
