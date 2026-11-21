# LibESQL Examples

Eleven small add-ons that show how to use [LibESQL](../LibESQL/README.md). Each folder is a complete add-on with a manifest and one Lua file, so you can install it as is, or copy it and rename it as the start of your own add-on.

## Install

1. Install **LibESQL**.
2. Copy the example folders you want into `Documents/Elder Scrolls Online/live/AddOns/`. Each example goes directly in `AddOns/`, not inside `LibESQL/`.
3. Enable them in the add-on list and `/reloadui`.

Slash commands work on PC/Mac only. For console, start from **ConsolePanel**.

## The examples

| Example | Try it | Shows |
|---|---|---|
| [Basics](LibESQL_Example_Basics/LibESQL_Example_Basics.lua) | `/esqlbasics` | `Query`, `Scalar`, `Select`, `?` parameters, error text |
| [AbilityLookup](LibESQL_Example_AbilityLookup/LibESQL_Example_AbilityLookup.lua) | `/abil 46340`, `/abil whip` | Instant lookup by key; a name search with `QueryAsync` that builds the ability index the first time |
| [SetSearch](LibESQL_Example_SetSearch/LibESQL_Example_SetSearch.lua) | `/setsearch critical` | `JOIN` of `sets` and `set_bonuses` |
| [BuffWatcher](LibESQL_Example_BuffWatcher/LibESQL_Example_BuffWatcher.lua) | `/mybuffs`, `/targetdebuffs` | The live `effects` table, `IIF`, `GROUP BY 1`, `GROUP_CONCAT` |
| [CombatSummary](LibESQL_Example_CombatSummary/LibESQL_Example_CombatSummary.lua) | Fight something | Turning combat logging on and off, then aggregating `combat_log` after each fight |
| [CustomTable](LibESQL_Example_CustomTable/LibESQL_Example_CustomTable.lua) | Die, then `/mydeaths` | `RegisterTable` with a lazy column; the new table works in every query, including the ESQL window |
| [CustomFunction](LibESQL_Example_CustomFunction/LibESQL_Example_CustomFunction.lua) | `/esqlfn` | `RegisterFunction`, and a join of `hotbar` with `abilities` |
| [ScanProgress](LibESQL_Example_ScanProgress/LibESQL_Example_ScanProgress.lua) | `/esqlscan`, `/esqlscan items` | `IsScanned`, `Scan`, and the `ScanProgress` callback |
| [CollectionReport](LibESQL_Example_CollectionReport/LibESQL_Example_CollectionReport.lua) | `/mycollection` | `GROUP BY`, `HAVING`, summing booleans, `ToObjects` |
| [SavedData](LibESQL_Example_SavedData/LibESQL_Example_SavedData.lua) | `/todo add <text>`, `/todo`, `/todo done 1`, `/todo del 1`, `/todo clean` | A to-do list in a saved table: `CREATE TABLE IF NOT EXISTS`, `INSERT`, `UPDATE`, `DELETE`, `rowsAffected`, and NULL parameters |
| [ConsolePanel](LibESQL_Example_ConsolePanel/LibESQL_Example_ConsolePanel.lua) | Settings > Addons > LibESQL Example | A LibHarvensAddonSettings panel with ready-made queries. It works on console. |

## Tips

- Put player text into a query with `?` parameters, never by joining strings. For a `LIKE` search, also escape it, so a `%` or `_` the player typed matches itself: `LibESQL.Select("... WHERE name LIKE ? ESCAPE '\\'", { "%" .. LibESQL.Escape(text) .. "%" })`.
- The first query on `abilities` or `items` scans every id. Run it with `QueryAsync` or `Scan`. Afterwards the index is saved until the next game update.
- `SHOW TABLES` and `DESCRIBE <table>` (or `LibESQL.GetColumns`) list what you can query.
- Keep your add-on's own data in a table you create (see SavedData). It is saved in `LibESQL_SV` and every add-on, and the ESQL window, can query it.
- CombatSummary turns combat logging on for every fight. Disable that example if you don't want it.

## License

MIT. See [LICENSE](LICENSE). Copy and change these examples freely.
