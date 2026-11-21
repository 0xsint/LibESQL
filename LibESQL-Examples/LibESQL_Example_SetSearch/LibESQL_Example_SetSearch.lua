-- LibESQL_Example_SetSearch: Join sets with their bonuses
-- An example for LibESQL. Copy it, rename it, change it.
-- Slash commands work on PC only; see LibESQL_Example_ConsolePanel for console.

local function Print(fmt, ...)
    local msg = select("#", ...) > 0 and string.format(fmt, ...) or tostring(fmt)
    if CHAT_ROUTER then CHAT_ROUTER:AddSystemMessage("[SetSearch] " .. msg) else d(msg) end
end

-- /setsearch critical   sets whose full bonus mentions the text
SLASH_COMMANDS["/setsearch"] = function(text)
    if not text or text == "" then Print("Usage: /setsearch <bonus text>") return end
    local rows, err = LibESQL.Select([[
        SELECT s.name, s.set_type, b.description
        FROM sets s
        JOIN set_bonuses b ON b.set_id = s.id
        WHERE b.num_required = s.max_equipped AND b.description LIKE ? ESCAPE '\'
        ORDER BY s.set_type, s.name
        LIMIT 15]], { "%" .. LibESQL.Escape(text) .. "%" })
    if not rows then Print("Error: %s", err) return end
    Print("%d set(s) with '%s' in the full bonus:", #rows, text)
    for _, r in ipairs(rows) do Print("  %s (%s): %s", r.name, r.set_type or "?", r.description) end
end
