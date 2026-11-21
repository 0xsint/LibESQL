# LibESQL API Reference

Version 1.0.0 (`LibESQL.versionNumber` = 10000) · API 101049 / 101050 · PC/Mac and console

This page lists every public function: its arguments, what it returns (including the `nil` and `false` cases), and the data structures it uses. It also covers the SQL dialect and every built-in table.

Every table that comes with LibESQL is **built in and always read-only**. That covers the game data and the `tables`/`columns` lists. Your own data goes into tables you make with `CREATE TABLE` or `SELECT ... INTO`, and you change it with `INSERT`, `UPDATE` and `DELETE` (see [Writing to your own tables](#writing-to-your-own-tables)). Those tables are saved and come back after a reload. For a shorter introduction, read the [README](README.md). For complete add-ons, see [LibESQL-Examples](../LibESQL-Examples/README.md).

## Contents

- [Conventions](#conventions)
- [Data structures](#data-structures): [result](#result), [opts](#opts), [errors](#errors), [job](#job), [table definition](#table-definition), [column definition](#column-definition)
- [Querying](#querying): Query, QueryAsync, Select, Scalar, ToObjects, Quote, Highlight, Validate
- [Writing to your own tables](#writing-to-your-own-tables): CreateTable, Insert, Upsert, Update, Delete, DropTable
- [Schema](#schema): GetTableNames, GetColumns, GetTable, RegisterTable, Refresh
- [Id scans](#id-scans): Scan, IsScanned
- [SQL functions](#sql-functions-from-lua): RegisterFunction
- [Data collection](#data-collection): effect tracking, combat log
- [Callbacks](#callbacks)
- [Background jobs](#background-jobs): RunAsync, RunSync, Tick, CancelJob, CancelJobs, HasJobs
- [MySQL export](#mysql-export): ToMySQL, MySQLValue, MySQLColumnType, MySQLTableName
- [Other add-ons' saved data](#other-add-ons-saved-data): saved_variables, sv_tables, sv_values, generated sv_* tables
- [Utilities](#utilities)
- [Low-level: LibESQL.SQL](#low-level-libesqlsql)
- [Fields and limits](#fields-and-limits)
- [SavedVariables](#savedvariables)
- [SQL language](#sql-language)
- [Scalar functions](#scalar-functions)
- [Performance](#performance)
- [Tables](#tables)

---

## Conventions

- Everything is on the global `LibESQL`. Call functions with a dot: `LibESQL.Query(...)`, not `LibESQL:Query(...)`.
- A SQL `NULL` is a Lua `nil`, and SQL booleans are Lua `true`/`false`. Numbers are Lua numbers and text is Lua strings.
- Table and column names are lower case. Keywords and function names are case-insensitive.
- Functions that can fail return `nil, errorText` (or `false, errorText`), and they don't raise errors. The only exceptions are programming mistakes, such as calling `RegisterFunction` without a function or `Scan` on a table that isn't scanned. Those raise with `assert`.
- The library is ready when your own add-on's `EVENT_ADD_ON_LOADED` fires (LibESQL loads first). Before LibESQL's SavedVariables load, queries still work, but saved id indexes and user tables aren't available yet. Use the [`Loaded`](#callbacks) callback, or check `LibESQL.loaded`.

---

## Data structures

### result

What every query returns.

```lua
{
    columns   = { "id", "name" },             -- output column names, in order
    rows      = { { 46340, "Molten Whip" },   -- one array per row, values in column order
                  { 46348, nil } },           -- a NULL is a hole (nil) in the array
    truncated = false,                        -- true if opts.maxRows cut the result
    elapsedMs = 3,                            -- time to run (in-game clock)
    message   = nil,                          -- text for INTO / INSERT / UPDATE / DELETE / CREATE / DROP / REFRESH / SCAN statements
    rowsAffected = nil,                       -- INSERT / UPDATE / DELETE only: rows inserted, changed or removed
    inserted, updated, unchanged = nil,       -- upserts only: what happened to each row
}
```

- `INSERT`, `UPDATE`, `DELETE`, `CREATE TABLE`, `DROP TABLE`, `REFRESH`, `SCAN` and `HELP` return one `info` column with a line of text, which is also in `message`.
- Arrays can have `nil` holes, so read cells with `row[c]` for `c = 1, #result.columns`. Don't use `ipairs(row)` or `#row`.
- Column names are the alias if you gave one (`AS x`). For a plain column they are the column's name. Anything else is named by its expression text, for example `COUNT(*)`.
- `SELECT *` over a join prefixes names that appear in more than one table, for example `s.name` and `b.name`.

### opts

The optional last argument of `Query`, `QueryAsync` and `LibESQL.SQL.Run`.

| Field | Type | Meaning |
|---|---|---|
| `params` | array | Values for the `?` placeholders, in order. A `nil` in the array binds `NULL`. To bind a `NULL` as the last value, also set `params.n` (`{ 5, nil, n = 2 }`). |
| `maxRows` | number | The most rows to return. When the query produces more, `result.truncated` is set. Without `ORDER BY`, `GROUP BY` or `DISTINCT`, the query also stops producing rows early. |

### errors

Error text is a plain string meant for people, for example:

```
no table 'abilitys'. Try SHOW TABLES
no column 'nme' in abilities. Columns: id, name, description, ...
column 'name' is ambiguous; prefix it with a table alias
expected FROM near 'FORM abilities'
missing value for parameter 2
aggregate COUNT() is not allowed here
unterminated string starting at 31
```

Inside the engine, errors are tables (`{ esql = true, msg = "..." }`). `LibESQL.SQL.ErrorText(err)` turns either form into text. The public functions do that for you.

### job

Returned by `QueryAsync`, `Scan` and `RunAsync`. Treat it as an opaque handle that you can pass to [`CancelJob`](#background-jobs). A job runs in a coroutine and does a slice of work every frame (see [Background jobs](#background-jobs)).

### table definition

The argument of [`RegisterTable`](#libesqlregistertabledef).

| Field | Type | Required | Meaning |
|---|---|---|---|
| `name` | string | yes | Table name, lower-cased on registration. Registering an existing name replaces that table. |
| `desc` | string | no | One-line description, shown by `SHOW TABLES`. |
| `columns` | array | yes | [Column definitions](#column-definition), in display order. |
| `build` | `function(rows, def)` | yes* | Fills `rows` with row tables keyed by lower-case column name. Call `LibESQL.Tick()` in its loops. |
| `live` | boolean | no | `true` rebuilds the rows on every query. Otherwise rows are built once and cached until `Refresh`. |
| `key` | string | no | Primary-key column. On cached tables it makes `WHERE key = x` / `IN (...)` a direct lookup. |
| `lookup` | `function(keyValue) -> row or nil` | no | Your own lookup by key. It is used for `WHERE key = ...` and for joins on the key. |
| `scan` | table | no* | Makes an id-scan table like `abilities`. Its fields are `from`, `to`, `gap`, `minTo`, `exists(id)`, `makeRow(id)` and `label` (see [Id scans](#id-scans)). Use this instead of `build`. |
| `onRefresh` | `function(def)` | no | Called when the table's cache is cleared. |
| `update` | `function(row, changes, def)` | no | Makes the table accept `UPDATE` and `LibESQL.Update`. It is called once per matching row with the row table and `{ column = newValue }` (`nil` for NULL). Apply the changes to your data. The table's cache is cleared afterwards. |
| `delete` | `function(row, def)` | no | Makes the table accept `DELETE` and `LibESQL.Delete`. It is called once per matching row with the row table your `build` made. Remove it from your data. The table's cache is cleared afterwards. |
| `insert` | `function(row, def)` | no | Makes the table accept `INSERT` and `LibESQL.Insert`. It is called once per row with a table keyed by lower-case column name (missing columns are `nil`). Store the row wherever your add-on keeps its data. The table's cache is cleared afterwards. |

After registration the definition also has `kind` (`static`, `live`, `scan`, `user` or `temp`), `colIndex` (a map from lower-case name to column), and for cached tables `cache` and `index`.

### column definition

You can write a column as an array `{ name, type, description, getter }` or as a table `{ name = , type = , desc = , get = }`.

| Part | Meaning |
|---|---|
| `name` | Column name (lower-cased). It is also the key in row tables. |
| `type` | `"int"`, `"num"`, `"text"` or `"bool"`. This is for documentation only: values are never converted. |
| `description` | Shown by `DESCRIBE`. |
| `getter` | Optional `function(row) -> value`. It makes the column **lazy**: the value is computed only when a query reads it, then stored on the row. It runs inside `pcall`, and an error reads as `NULL`. A getter must not call `LibESQL.Tick()`. |

---

## Querying

### LibESQL.Query(sql, opts)

Runs a statement now, in the current frame.

- **Arguments:** `sql` (string), `opts` ([opts](#opts), optional).
- **Returns:** a [result](#result), or `nil, errorText`.
- **Note:** the first full read of `abilities` or `items` scans every id and blocks the frame for a few seconds. Do that first read with `QueryAsync` or `Scan`. Key lookups (`WHERE id = ...`) never need the scan.

```lua
local res, err = LibESQL.Query("SELECT name, level FROM character")
if res then d(res.rows[1][1]) else d(err) end
```

### LibESQL.QueryAsync(sql, callback, opts)

Runs a statement in the background, a slice per frame.

- **Arguments:** `sql` (string), `callback` (`function(result)` on success, `function(nil, errorText)` on failure; optional), `opts` (optional).
- **Returns:** a [job](#job). The callback runs on a later frame, never inside the call.

```lua
LibESQL.QueryAsync("SELECT id, name FROM abilities WHERE name LIKE ?", function(res, err)
    if not res then d(err) return end
    d(#res.rows .. " matches")
end, { params = { "%rune%" } })
```

### LibESQL.Select(sql, params)

Runs a query and returns the rows as objects.

- **Arguments:** `sql` (string), `params` (array of `?` values, optional; this is just the params array, not an opts table).
- **Returns:** an array of tables keyed by column name (`{ { id = 1, name = "x" }, ... }`), or `nil, errorText`. With no matching rows it returns an empty table, not `nil`.

### LibESQL.Scalar(sql, params)

- **Returns:** the first column of the first row. It returns `nil` when there are no rows or the value is `NULL`, and `nil, errorText` on error.

```lua
local n = LibESQL.Scalar("SELECT COUNT(*) FROM achievements WHERE completed")
```

### LibESQL.ToObjects(result)

- **Returns:** the rows of a [result](#result) as objects keyed by column name. If two columns share a name, the later one wins.

### LibESQL.Quote(value)

Formats a value as an SQL literal.

- **Returns:**
  - a string gives a quoted string with `'` doubled: `Kinras's` becomes `'Kinras''s'`
  - a number gives its text
  - `true` / `false` give `TRUE` / `FALSE`
  - `nil` gives `NULL`
- **Tip:** prefer `?` parameters. `Quote` is for building SQL text that you show to people.

### LibESQL.Highlight(sql, colors)

Colours SQL for display in a label, the way the ESQL window shows its query box.

- **Arguments:**
  - `sql`: string. `nil` counts as `""`.
  - `colors`: optional overrides of `LibESQL.SQL.HIGHLIGHT_COLORS`, as `{ kind = "RRGGBB" }`. Set a kind to `false` to leave it uncoloured.
- **Returns:** the text with `|cRRGGBB ... |r` markup around each coloured token. Every literal `|` is doubled so ESO displays it, and the rest of the text is unchanged. With the markup removed (and `||` turned back into `|`), you get exactly the input again.
- **Never fails:** half-typed SQL, such as an unclosed `'string` or `/* comment`, is coloured up to the end of the text. Nothing is parsed or run.

| Kind | Default | What |
|---|---|---|
| `keyword` | `4FC3F7` | SQL keywords and statement words: `SELECT`, `FROM`, `WHERE`, `INSERT`, `UPDATE`, `CREATE`, `SHOW`, ... |
| `function` | `FFD54F` | A built-in or registered function name followed by `(` |
| `table` | `80CBC4` | Names of tables that exist right now |
| `string` | `A5D6A7` | `'text'` |
| `number` | `FFAB91` | `42`, `3.5`, `1e3`, `0x1F` |
| `param` | `CE93D8` | `?` |
| `comment` | `7F8C8D` | `-- ...` and `/* ... */` |
| `operator` | `B0BEC5` | `= < + ( ) , *` and other symbols |
| `identifier` | `false` | Column names, aliases and quoted names (left uncoloured) |

```lua
label:SetText(LibESQL.Highlight("SELECT name FROM abilities WHERE id = ?"))
label:SetText(LibESQL.Highlight(sql, { keyword = "FF8800", table = false }))
```

### LibESQL.Escape(text, escapeChar)

Escapes `LIKE` wildcards so `text` matches itself. Every `%`, `_` and escape character gets the escape character in front.

- **Arguments:**
  - `text`: the text to escape
  - `escapeChar`: one character, default `\`
- **Returns:** the escaped text, `nil` for `nil`, or `nil, errorText` when `escapeChar` isn't a single character.
- **Use it with** the same character in `ESCAPE`.

```lua
LibESQL.Select("SELECT name FROM abilities WHERE name LIKE ? ESCAPE '\\'", { "%" .. LibESQL.Escape(playerText) .. "%" })
```

### LibESQL.Validate(sql)

Parses without running. `?` placeholders count as valid.

- **Returns:** `true`, or `false, errorText`.
- **Note:** it only checks syntax. Unknown tables and columns are found when the query runs.

---

## Writing to your own tables

Only tables created after LibESQL has loaded can be written to:
- tables made with `CREATE TABLE` or `SELECT ... INTO` (kind `user`)
- tables another add-on registers with its own `insert`, `update` or `delete` function

Every table LibESQL registers while it loads is **built in**. The list of built-in tables is kept inside the library, not on the table definitions, so changing a definition can't unlock one. For a built-in table:
- `INSERT`, `UPDATE` and `DELETE`, and `LibESQL.Insert/Update/Delete`, are refused, even if a write handler or `kind = "user"` is set on its definition.
- `DROP TABLE` is refused.
- `CREATE TABLE` and `SELECT ... INTO` with its name are refused.
- `RegisterTable` with its name raises an error.
- A saved user table with the same name is never loaded over it.

The same goes for another add-on's table that has no write functions: it can't be written to, dropped or replaced by a user table. `SHOW TABLES` / `SELECT name, builtin, writable FROM tables` shows which tables you can write to.

User tables:
- Are saved in `LibESQL_SV` after every change, and come back after a reload.
- Hold at most `LibESQL.USER_TABLE_MAX_ROWS` rows.
- Convert inserted and updated values to the column type:
  - `INT`: numeric text becomes a number, decimals are truncated, booleans become 1/0
  - `REAL`: numeric text becomes a number
  - `TEXT`: values are stored as text
  - `BOOL`: numbers and `'true'/'false'/'yes'/'no'/'1'/'0'` become booleans
- Leave values as they are in columns of type `any`, which is what `SELECT ... INTO` makes.

**Primary keys.** A table made with `CREATE TABLE` can have a `PRIMARY KEY`: on one column (`boss TEXT PRIMARY KEY`), or on several (`PRIMARY KEY (char, slot)`). After that:
- `INSERT` refuses a row whose key already exists or is `NULL`.
- `UPDATE` refuses a change that would make two rows share a key.
- Nothing is changed when a check fails.
- Keys match like `=`, so `'Zaan'` and `'zaan'` are the same key.
- The key is saved with the table, and `DESCRIBE` shows it as "primary key".

**Upsert.** Upsert inserts new rows and updates the ones that already exist. Rows are matched on the conflict columns: by default the primary key, or the columns named in `ON CONFLICT (a, b)`, which work on tables without a key.
- A row with a `NULL` in a conflict column never matches.
- Rows earlier in the same statement count too: two new rows with one key give one insert and one update.
- **`LibESQL.CreateTable`** understands `"boss TEXT PRIMARY KEY"` strings and `{ name = , type = , primaryKey = true }`.

### LibESQL.CreateTable(name, columns, ifNotExists)

- **Arguments:**
  - `name`: string
  - `columns`: an array of `"name TYPE"` strings (`{ "boss TEXT", "secs REAL" }`) or `{ name = , type = }` tables. A type is optional, and you can use any type name from [CREATE TABLE](#statements).
  - `ifNotExists`: boolean
- **Returns:** `true` when it creates the table, `false` when the table already exists and `ifNotExists` is set, or `nil, errorText`. It is an error when the name exists without `ifNotExists`, belongs to a built-in table, or no columns are given.
- **Same as** `CREATE TABLE [IF NOT EXISTS] name (...)`.

### LibESQL.Insert(tableName, row)

- **Arguments:**
  - `tableName`: string
  - `row`: one row table, such as `{ boss = "Zaan", secs = 61.5 }`, or an array of them. Keys are column names (case-insensitive), and missing columns are `NULL`.
- **Returns:** the number of rows inserted, or `nil, errorText`. It is an error when there is no such table, the table is read-only, a key isn't a column, or the row limit would be passed. Nothing is inserted if any row is invalid.
- **Fires:** `RowsInserted`.

### LibESQL.Upsert(tableName, rows, keyColumns)

- **Arguments:**
  - `tableName`: string
  - `rows`: one row table, such as `{ boss = "Zaan", secs = 58 }`, or an array of them. Keys are column names (case-insensitive).
  - `keyColumns`: optional. A column name, or an array of them, that identifies a row. The default is the table's `PRIMARY KEY`.
- **What it does:** each row is inserted, or, when a row with the same key exists, that row's other given columns are updated. The key keeps its stored spelling, and columns a row doesn't give are left alone. This is the same as `UPSERT INTO`.
- **Returns:** `inserted + updated, { inserted, updated, unchanged }`, or `nil, errorText`. It is an error when there is no such table, the table is read-only, a key isn't a column, the table has no `PRIMARY KEY` and you give no `keyColumns`, or the change would break the primary key.
- **Fires:** `RowsUpserted(tableName, inserted, updated)`, plus `RowsInserted` / `RowsUpdated` for each part.

```lua
LibESQL.Upsert("best", { boss = "Zaan", secs = 58 })                              -- PRIMARY KEY boss
LibESQL.Upsert("prices", { item = "Dreugh Wax", guild = "Alpha", price = 8500 }, { "item", "guild" })
```

### LibESQL.Update(tableName, changes, where, whereParams)

- **Arguments:**
  - `tableName`: string
  - `changes`: `{ column = newValue, ... }` (column names are case-insensitive). Lua tables can't hold `nil`, so use `LibESQL.NULL` to set a column to `NULL`.
  - `where`: optional SQL condition text. Leave it out to update every row.
  - `whereParams`: optional values for the `?` placeholders in `where`
- **Returns:** the number of rows changed (0 when nothing matched), or `nil, errorText`. It is an error when there is no such table, the table is read-only, a key isn't a column, or `where` isn't valid SQL.
- **Fires:** `RowsUpdated`.
- **Same as** `UPDATE tableName SET ... WHERE where`. The change values are passed as parameters, so they are never pasted into the SQL text.

```lua
LibESQL.Update("kills", { secs = 55 }, "boss = ? AND secs > ?", { "Zaan", 55 })
LibESQL.Update("kills", { note = LibESQL.NULL })          -- every row
```

### LibESQL.Delete(tableName, where, whereParams)

- **Arguments:**
  - `tableName`: string
  - `where`: optional SQL condition text. Leave it out to delete every row (the table itself stays).
  - `whereParams`: optional values for the `?` placeholders in `where`
- **Returns:** the number of rows removed (0 when nothing matched), or `nil, errorText`. It is an error when there is no such table, the table is read-only, or `where` isn't valid SQL.
- **Fires:** `RowsDeleted`.
- **Same as** `DELETE FROM tableName WHERE where`.

```lua
LibESQL.Delete("kills", "at < ?", { GetTimeStamp() - 7 * 86400 })   -- older than a week
LibESQL.Delete("kills")                                             -- empty the table
```

### LibESQL.DropTable(name)

- **Returns:** `true`, or `nil, errorText` for unknown or built-in tables.
- **Same as** `DROP TABLE name`.

---

## Schema

### LibESQL.GetTableNames()

- **Returns:** an array of every table name, in registration order (built-in tables first, then add-on tables and user tables).

### LibESQL.GetColumns(tableName)

- **Returns:** an array of `{ name, type, description, lazy }`, or `nil` if there is no such table.

### LibESQL.GetTable(tableName)

- **Returns:** the internal [table definition](#table-definition), or `nil`. Treat it as read-only.

### LibESQL.RegisterTable(def)

Adds a table (or replaces one with the same name), which then works in every query.

- **Arguments:** a [table definition](#table-definition).
- **Returns:** the definition.
- **Raises** when a column name appears twice, or when `name` is a built-in table (built-in tables can't be replaced).

```lua
LibESQL.RegisterTable({
    name = "my_parses", desc = "Saved parses", key = "id", live = true,
    columns = {
        { "id", "int", "Parse id" },
        { "boss", "text", "Boss name" },
        { "dps", "int", "DPS" },
        { "boss_upper", "text", "Upper-case boss", function(r) return r.boss:upper() end },  -- lazy
    },
    build = function(rows)
        for i, p in ipairs(MyAddon.parses) do
            LibESQL.Tick()
            rows[#rows + 1] = { id = i, boss = p.boss, dps = p.dps }
        end
    end,
})
```

`build` runs inside the query's coroutine. Call `LibESQL.Tick()` once per loop iteration so a long build spreads over frames. Never call `Tick()` inside `pcall`, a metamethod or a `table.sort` comparator: Lua 5.1 can't yield there.

### LibESQL.Refresh(tableName)

Drops cached rows (and the key index), so the next query rebuilds them.

- **Arguments:** a table name, or `nil` for every table. User tables are never touched.
- **Returns:** the number of tables cleared, or `nil, errorText` for an unknown table.
- **Same as** the SQL statements `REFRESH name` and `REFRESH ALL`.

---

## Id scans

`abilities` and `items` have no game function that lists them. LibESQL finds them by checking every id once (`DoesAbilityExist`, or a non-empty `GetItemLinkName`) and saves the ids found in `LibESQL_SV`, keyed by `GetAPIVersion()`. After a game update, the scan runs again on first use.

How a scan runs, using the fields of `def.scan`:
- It checks ids from `from` to `to`.
- It stops early once an id is past `minTo` and no id has been found in the last `gap` ids.
- It calls `exists(id)` inside `pcall` for each id.
- Rows are built from the saved ids on demand with `makeRow(id)`.

| Table | Range | Stop rule |
|---|---|---|
| `abilities` | 1–600000 | after 60000 empty ids past 250000 |
| `items` | 1–450000 | after 40000 empty ids past 230000 |

### LibESQL.Scan(tableName, callback, force)

Builds the index in the background.

- **Arguments:**
  - `tableName`: `"abilities"` or `"items"`
  - `callback`: optional; called as `function(count)` when done, or `function(nil, errorText)` on failure
  - `force`: `true` throws away the saved index and scans again
- **Returns:** a [job](#job).
- **Raises** if the table isn't a scan table.
- **Progress** is reported through the `ScanProgress` / `ScanDone` [callbacks](#callbacks).
- **Same as** the SQL statement `SCAN abilities`, which always forces a new scan.

### LibESQL.IsScanned(tableName)

- **Returns:** `true, count` once the index exists for the current API version (in memory or saved). Otherwise it returns `false`, or `false, oldCount` when the saved index is from an older API version. Tables that aren't scanned return `false`.

---

## SQL functions from Lua

### LibESQL.RegisterFunction(name, fn)

Adds a scalar SQL function, or replaces one, for every query.

- **Arguments:**
  - `name`: string, matched case-insensitively
  - `fn`: receives the evaluated arguments (`nil` for `NULL`) and returns one value
- **Raises** if the arguments have the wrong types.
- **Errors in `fn`:** they abort the query with the Lua error text. To fail with a clean message, call `LibESQL.SQL.Fail("message")` instead.
- **Names you can't use:** `COUNT SUM AVG MIN MAX TOTAL GROUP_CONCAT` are aggregates. A function you register under one of those names is never called.

```lua
LibESQL.RegisterFunction("SECONDS", function(ms) return ms and ms / 1000 end)
LibESQL.Query("SELECT name, SECONDS(duration_ms) FROM abilities WHERE id = 46340")
```

---

## Data collection

| Function | Returns | Meaning |
|---|---|---|
| `LibESQL.SetEffectTracking(on)` | none | Registers or unregisters `EVENT_EFFECT_CHANGED`. Every effect id that is gained or updated is added to `effects_seen`. The setting is saved, and the default is off. The ESQL add-on turns it on the first time it loads. |
| `LibESQL.IsEffectTracking()` | boolean | |
| `LibESQL.SetCombatLogging(on)` | none | Registers or unregisters `EVENT_COMBAT_EVENT` and records events into the `combat_log` ring buffer. It is not saved, and it is off at load. |
| `LibESQL.IsCombatLogging()` | boolean | |
| `LibESQL.ClearCombatLog()` | none | Empties the combat log. |

Caps:
- `effects_seen` holds at most `LibESQL.EFFECTS_SEEN_MAX` ids. New ids are ignored once it is full. Ids already in it keep updating.
- `combat_log` keeps the newest `LibESQL.COMBAT_LOG_MAX` events.

---

## Callbacks

### LibESQL.RegisterCallback(event, fn) / LibESQL.UnregisterCallback(event, fn)

- Registering the same function twice has no effect.
- Callbacks run inside `pcall`. An error in one is printed to chat and doesn't stop the others.

| Event | Arguments | When |
|---|---|---|
| `Loaded` | none | LibESQL's SavedVariables are ready (`LibESQL.loaded` is now `true`). |
| `ScanProgress` | `tableName, fraction, idsFound` | At 0, at every 10% step and at 1 during an id scan. |
| `ScanDone` | `tableName, count` | An id scan finished. |
| `UserTableCreated` | `name` | `CREATE TABLE name` created a table, or `SELECT ... INTO name` created or replaced one. |
| `UserTableDropped` | `name` | `DROP TABLE name`. |
| `SavedVariablesScanned` | `count` | Other add-ons' SavedVariables were scanned (see [Other add-ons' saved data](#other-add-ons-saved-data)). |
| `RowsInserted` | `tableName, count` | `INSERT` or `LibESQL.Insert` added rows. |
| `RowsUpdated` | `tableName, count` | `UPDATE` or `LibESQL.Update` finished. `count` is the number of rows changed, and can be 0. |
| `RowsDeleted` | `tableName, count` | `DELETE` or `LibESQL.Delete` finished. `count` is the number of rows removed, and can be 0. |
| `RowsUpserted` | `tableName, inserted, updated` | An upsert finished (any of the forms above, or `LibESQL.Upsert`). |

`LibESQL.FireCallbacks(event, ...)` fires an event. Add-ons can use it for events of their own.

---

## Background jobs

LibESQL does long work in coroutines driven by `EVENT_MANAGER:RegisterForUpdate`. Each frame, every job resumes until it has done `LibESQL.budget` units of work. All jobs together stop after about 8 ms per frame.

| Function | Returns | Meaning |
|---|---|---|
| `LibESQL.RunAsync(fn, onDone, label)` | job | Runs `fn(job)` in a coroutine. `onDone(true, returnValue)` or `onDone(false, err)` is called when it finishes. `err` may be an engine error table, so use `LibESQL.SQL.ErrorText(err)`. Without `onDone`, errors are printed to chat. |
| `LibESQL.RunSync(fn)` | `ok, valueOrError` | Runs `fn` now with yielding turned off (`pcall` semantics). |
| `LibESQL.Tick(n)` | none | Counts `n` units of work (default 1), and yields if the frame's budget is spent. It does nothing outside a job or inside `RunSync`. |
| `LibESQL.CancelJob(job)` | boolean | Removes one job. Its callback is not called. Returns `true` if the job was still queued. |
| `LibESQL.CancelJobs()` | none | Removes every job. |
| `LibESQL.HasJobs()` | boolean | Whether any job is queued. |

---

## MySQL export

These turn query results into SQL for MySQL / MariaDB, in the layout phpMyAdmin uses for its own dumps. `ESQL/tools/esql_to_mysql.py` follows the same rules, to build a dump from SavedVariables outside the game.

### LibESQL.ToMySQL(result, tableName, opts)

- **Arguments:**
  - `result`: a [result](#result)
  - `tableName`: string. It's made safe with `MySQLTableName`.
  - `opts`: optional; the fields are in the table below
- **Returns:** `dumpText, blocks`.
  - `dumpText` is the whole dump.
  - `blocks` is the same dump as `{ { text, first, last }, ... }`: whole statements in order. `first` and `last` are the result rows inside a block, and they are `nil` for the header and `CREATE TABLE` blocks. Join the texts with blank lines to get `dumpText`.
- **What it writes:**
  1. `SET SQL_MODE`, `START TRANSACTION`, `SET time_zone` and `SET NAMES utf8mb4`
  2. `DROP TABLE IF EXISTS`
  3. `CREATE TABLE ... ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci`
  4. multi-row `INSERT`s, with the "Dumping data" comment attached to the first one
  5. `COMMIT`
- **Ticks:** it calls `LibESQL.Tick()`, so big results spread over frames inside `QueryAsync` / `RunAsync`.

| `opts` field | Default | Meaning |
|---|---|---|
| `types` | inferred | `{ "int"\|"num"\|"text"\|"bool"\|"any", ... }` per column, as stored for user tables |
| `header` | `true` | `false` leaves out the `SET`/`START TRANSACTION` lines and `COMMIT` (to join several tables into one dump) |
| `dropTable` | `true` | `false` leaves out `DROP TABLE IF EXISTS` |
| `rowsPerInsert` | 500 | Rows per `INSERT` statement |
| `maxInsertBytes` | 1000000 | A new `INSERT` starts before one grows past this |
| `comment` | none | An extra comment line above the table |

Column types:
- declared `int` becomes `bigint(20)`, `num` becomes `double`, and `bool` becomes `tinyint(1)`
- inferred: all booleans give `tinyint(1)`; all whole numbers give `int(11)`, or `bigint(20)` past 2147483647; other numbers give `double`
- anything else is text by its longest value: `varchar(255)` up to 255 bytes, `text` up to 65535, then `mediumtext`
- every column allows `NULL`

```lua
local res = LibESQL.Query("SELECT id, name, duration_ms FROM abilities WHERE name LIKE '%whip%'")
local sql = LibESQL.ToMySQL(res, "whips")
```

### LibESQL.MySQLValue(value)

- **Returns:** a MySQL literal.
  - `nil`, NaN and infinity give `NULL`.
  - booleans give `1` / `0`.
  - whole numbers are written without a decimal point. This uses `%.0f`, so values past 2^31 stay exact.
  - strings are quoted, with `\`, `'`, NUL, newline, carriage return and Ctrl-Z escaped.

### LibESQL.MySQLColumnType(values, declared)

- **Returns:** the MySQL column type for an array of a column's non-NULL values, following the rules above.

### LibESQL.MySQLTableName(name)

- **Returns:** a safe MySQL table name.
  - It is lower-cased, with anything other than letters, digits and `_` turned into `_`.
  - It is at most 64 characters.
  - Names starting with a digit get a `t_` prefix, and an empty name becomes `esql_export`.

## Other add-ons' saved data

LibESQL turns other add-ons' SavedVariables into read-only tables (file `LibESQL_SavedVars.lua`). SavedVariables are global Lua tables once the game has loaded them, on PC and on console alike.

**What counts as saved data:**
- Every global table in the `ZO_SavedVars` shape: `Global[profile]["@account"]["$AccountWide" | characterId] = data`.
- Tables added with `AddSavedVariable`.
- `LibESQL_SV` and `ESQL_SV` are skipped (their data is already in your tables). The game's own `ZO_*` saved variables are skipped unless `LibESQL.SV_INCLUDE_GAME = true`.

**When the scan runs:** once on the first `EVENT_PLAYER_ACTIVATED`, again on `SCAN savedvariables` or `RescanSavedVariables()`, and on the first query of `saved_variables`, `sv_tables` or `sv_values` if none has run yet. A rescan removes tables whose data has gone, and keeps the same names for the rest.

**Which nodes become tables:** a node becomes a table when most of its children are tables that look alike, and they hold plain values. "Look alike" means their keys are array-style, or (with 3 or more of them) they share their most common field.

**Generated tables:**
- **Name:** `sv_<saved variable>_<path>`.
  - The saved variable's name is lower-cased, with suffixes like `SavedVars`, `_SV` or `_Settings` dropped.
  - Path parts with `*` (any key) are left out.
  - A name that's already taken gets `_2`, `_3`... added. That includes the built-in names, so `sv_values` and `sv_tables` can never be replaced.
- **Fixed columns:** `account`, `scope` (character name or `account-wide`), `character_id`, `key` (the record's key in its list) and `path` (where it is, for example `savedFights.3.snapshot.skillList.2`).
- **Field columns:** after the fixed columns come up to `SV_MAX_COLUMNS` field columns, most common first. Names are made safe: numeric keys become `c1`, `c2`..., and a field that clashes with a fixed column becomes `f_<name>`. Only plain values (text, number, boolean) are copied; nested tables have their own tables.
- **Kind:** live and read-only (not built in, and not writable). `INSERT`/`UPDATE`/`DELETE`/`DROP` are refused, and the add-on's data is never changed.
- **Safe to read:** every list is copied before LibESQL works through it, so an add-on changing its data while a query runs is safe.

| Function | Returns | Meaning |
|---|---|---|
| `LibESQL.RescanSavedVariables(callback)` | job | Rescans in the background. Calls `callback(count)`, or `callback(nil, errorText)` on failure. |
| `LibESQL.ScanSavedVariables()` | count | The same, run now (inside a query or job it spreads over frames). |
| `LibESQL.AddSavedVariable(globalName)` | `true` or `nil, errorText` | Includes a plain table that doesn't use `ZO_SavedVars`. It's remembered in `LibESQL_SV.extraSavedVariables`. The next scan picks it up. |
| `LibESQL.RemoveSavedVariable(globalName)` | `true` | Leaves it out again. |
| `LibESQL.GetSavedVariables()` | array | `{ { name, addon, style, tables = { { table_name, pattern, records, columns }, ... } }, ... }` |
| `LibESQL.SV_MAX_NODES` | number | Tables visited per saved variable while looking for lists. PC 250000, console 30000. Past it, `saved_variables.truncated` is true. |
| `LibESQL.SV_MAX_VALUES` | number | Rows `sv_values` builds per query. PC 200000, console 20000. |
| `LibESQL.SV_MAX_COLUMNS` | number | Field columns per generated table (60). |
| `LibESQL.SV_EXCLUDE` | set | Global names never scanned. |
| `LibESQL.SV_INCLUDE_GAME` | boolean | Also scan the game's own `ZO_*` saved variables (default `false`). |

**Callback:** `SavedVariablesScanned(count)` fires after every scan.

The `addon` column is a guess. It's the longest installed add-on name the saved variable's name starts with, so it can be empty when the names don't match (`HarvestDC_SavedVars` doesn't start with `HarvestMapDC`).

---

## Utilities

| Function | Returns | Meaning |
|---|---|---|
| `LibESQL.Print(fmt, ...)` | none | Prints `[ESQL] ...` to chat, `string.format` style. |
| `LibESQL.Try(fn, ...)` | `...` or `nil` | Calls `fn` in `pcall` and returns all its results, or `nil` on error or when `fn` isn't a function. |
| `LibESQL.CleanName(s)` | string | Removes the game's grammar suffix: `"Fire Rune^n"` becomes `"Fire Rune"`. |
| `LibESQL.StripMarkup(s)` | string | Removes `\|c` colours, `\|t` textures and `\|H` links (keeping the link text). |
| `LibESQL.EnumName(prefix, value)` | string or nil | `("BUFF_EFFECT_TYPE_", 2)` gives `"BUFF_EFFECT_TYPE_DEBUFF"`. When several names share a value, the shortest wins. `MIN_VALUE`/`MAX_VALUE` names are skipped. |
| `LibESQL.EnumShort(prefix, value)` | string or nil | The same without the prefix, lower case: `"debuff"`. |
| `LibESQL.EnumRange(prefix, lo, hi)` | lo, hi | The `prefix..MIN_VALUE` / `MAX_VALUE` (or `ITERATION_BEGIN/END`) of an enum, or the fallbacks you pass. |
| `LibESQL.GlobalPairs()` | iterator | A safe `pairs(_G)` that uses `zo_insecurePairs` and skips the game's private functions. |
| `LibESQL.NowMs()` | number | `GetGameTimeMilliseconds()`. |
| `LibESQL.IsBuiltinTable(name)` | boolean | Whether a table comes with LibESQL (and so is always read-only). |
| `LibESQL.CheckWritable(def, action)` | `"user"` or `"handler"` | The check every write goes through (`action` is `"INSERT"`, `"UPDATE"` or `"DELETE"`). It raises an engine error when the table can't be written to. |
| `LibESQL.NULL` | sentinel | Stands for SQL `NULL` where Lua can't store `nil`, for example in `Update` changes. |
| `LibESQL.AbilityName(id)` | string or nil | Clean ability name, `nil` if empty. |
| `LibESQL.ItemLink(id)` | string | A base item link for an item id. |

---

## Low-level: LibESQL.SQL

These are for tools and other UIs. Most add-ons don't need them.

| Function | Returns | Meaning |
|---|---|---|
| `SQL.Run(text, opts)` | result | Parses and runs. It raises an engine error table on failure. Call it inside `RunAsync` or `RunSync`. |
| `SQL.Parse(text, params)` | statement AST | Parses only. It raises on syntax errors. |
| `SQL.ExecuteStatement(stmt, opts)` | result | Runs a parsed statement. |
| `SQL.ErrorText(err)` | string | The text of an engine error table or a Lua error. |
| `SQL.Fail(fmt, ...)` | (raises) | Raises an engine error, for your own functions and builders. |
| `SQL.Compare(a, b)` | -1, 0, 1 or nil | SQL comparison: `nil` if either side is `NULL`, case-insensitive text, numbers parsed from text. |
| `SQL.SortCompare(a, b)` | -1, 0, 1 | The `ORDER BY` order: `NULL` first, then numbers and booleans, then text (case-insensitive). |
| `SQL.ToText(v)` | string or nil | How values print: integers without `.0`, `nil` stays `nil`. |
| `SQL.NormKey(v)` | value | The key used for `IN`, `GROUP BY`, `DISTINCT` and joins. Text is lowered, numeric text becomes a number, and booleans become 1/0. |
| `SQL.Tokenize(text)` | tokens | The lexer. |
| `SQL.FUNCS` | table | Scalar functions by upper-case name. `RegisterFunction` writes here. |
| `SQL.HELP` | array of strings | The text shown by `HELP`. |
| `SQL.Highlight(text, colors)` | string | The highlighter behind `LibESQL.Highlight`. Here `colors` replaces the whole palette instead of being merged into it. |
| `SQL.HIGHLIGHT_COLORS` | table | The default palette. Changing it changes the colours for every add-on. |

---

## Fields and limits

| Field | PC | Console | Meaning |
|---|---|---|---|
| `LibESQL.version` | `"1.0.0"` | | Version string |
| `LibESQL.versionNumber` | `10000` | | Same as `## AddOnVersion` |
| `LibESQL.isConsole` | `false` | `true` | `IsConsoleUI()` at load |
| `LibESQL.loaded` | | | `true` after SavedVariables load |
| `LibESQL.budget` | 3000 | 700 | Units of work per job per frame |
| `LibESQL.COMBAT_LOG_MAX` | 30000 | 5000 | Combat events kept |
| `LibESQL.EFFECTS_SEEN_MAX` | 20000 | 3000 | Distinct effect ids remembered |
| `LibESQL.USER_TABLE_MAX_ROWS` | 50000 | 5000 | Rows allowed in one user table (`SELECT ... INTO` or `INSERT`) |

You can change `budget` at run time. A lower value gives smoother frames and slower queries.

---

## SavedVariables

`LibESQL_SV` is account-wide (`ZO_SavedVars:NewAccountWide`, version 1):

| Key | Contents |
|---|---|
| `scans[table]` | `{ api, ranges, count, maxId }`. `ranges` is a compact base-36 string of id runs. |
| `effectsSeen[abilityId]` | `{ timesSeen, lastSeenTimestamp, flags, maxStacks, effectType, abilityType, statusEffectType }`. The `flags` bits are 1 = on you, 2 = on others, 4 = applied by you. |
| `userTables[name]` | `{ columns = {...}, types = {...}, primaryKey = {...}, rows = { {v1, v2, ...}, ... }, desc }`, from `CREATE TABLE`, `INSERT` and `SELECT ... INTO` |
| `trackEffects` | boolean |

---

## SQL language

### Statements

| Statement | Result |
|---|---|
| `SELECT ...` | Rows (see below). |
| `SELECT ... INTO name FROM ...` | Rows. The result is also saved as user table `name`, replacing any user table with that name. Column names are lower-cased, and repeated names get `_2`, `_3`... You can't overwrite a built-in table. |
| `SHOW TABLES` | `name, kind, description` for every table |
| `DESCRIBE t` / `DESC t` | `column_name, type, description` |
| `CREATE TABLE [IF NOT EXISTS] t (col [type], ...)` | Creates an empty user table. The types are `INT`/`INTEGER`/`BIGINT`/`SMALLINT`, `REAL`/`FLOAT`/`DOUBLE`/`NUMBER`/`NUMERIC`/`DECIMAL`, `TEXT`/`STRING`/`VARCHAR`/`CHAR` and `BOOL`/`BOOLEAN`. Sizes such as `VARCHAR(40)` are accepted and ignored. A missing or unknown type means `any`. |
| `INSERT INTO t [(col, ...)] VALUES (v, ...) [, (v, ...)]` | Adds rows. Values can be any constant expression, `?`, a function, or a `(SELECT ...)`. Without a column list, each row must give every column in order. |
| `INSERT INTO t [(col, ...)] SELECT ...` | Adds the rows a query returns, matched to the columns by position. |
| `CREATE TABLE t (a TEXT PRIMARY KEY, ...)` / `CREATE TABLE t (a, b, PRIMARY KEY (a, b))` | A table with a primary key. `NOT NULL` is accepted after a column (key columns are never `NULL` anyway). |
| `UPSERT INTO t [(cols)] VALUES ... \| SELECT ...` | Inserts new rows. Rows whose primary key already exists get the given columns updated, and the key keeps its spelling. |
| `INSERT OR REPLACE INTO ...` / `REPLACE INTO ...` | Inserts, or overwrites the whole existing row. Columns left out become `NULL`. |
| `INSERT OR IGNORE INTO ...` | Inserts, and leaves existing rows alone. |
| `INSERT ... ON CONFLICT [(cols)] DO NOTHING` | The same as `INSERT OR IGNORE`, matching on `cols` (default: the primary key). |
| `INSERT ... ON CONFLICT [(cols)] DO UPDATE SET c = expr [, ...] [WHERE cond]` | Updates the existing row. In `expr` and `cond`, a plain or `t.`-qualified column is the row already in the table, and `excluded.col` is the row you tried to insert. Rows that fail `cond` stay unchanged. |
| `INSERT ... ON DUPLICATE KEY UPDATE c = expr [, ...]` | MySQL style, matching on the primary key. `VALUES(col)` is the value you tried to insert. |
| `UPDATE t [[AS] alias] SET col = expr [, col = expr ...] [WHERE cond]` | Changes the rows where `cond` is true, or every row without `WHERE`. `SET` expressions and `WHERE` can use the row's columns (`SET secs = secs - 1`), `?` and subqueries. Every `SET` is computed from the row as it was before the update, and a column can be set only once per statement. `SET t.col = ...` is accepted. |
| `DELETE FROM t [[AS] alias] [WHERE cond]` | Removes the rows where `cond` is true, or every row without `WHERE`. The table itself stays; use `DROP TABLE` to remove it. `WHERE` can use the row's columns, `?` and subqueries, and is checked for every row before any row is removed. |
| `DROP TABLE t` | Removes a user table. Built-in tables and other add-ons' tables can't be dropped. |
| `REFRESH t` / `REFRESH ALL` | Clears cached rows. |
| `SCAN abilities` / `SCAN items` | Rebuilds the id index (always a fresh scan). |
| `SCAN savedvariables` | Finds other add-ons' SavedVariables again and rebuilds the tables made from them. |
| `HELP` | A short syntax summary, one line per row. |

A trailing `;` is allowed. Comments are `-- to end of line` and `/* ... */`.

### SELECT

```
SELECT [DISTINCT | ALL] item [, item ...]
       [INTO new_table]
       [FROM source [[INNER | LEFT [OUTER] | CROSS] JOIN source [ON condition] | , source] ...]
       [WHERE condition]
       [GROUP BY expr [, expr ...]]
       [HAVING condition]
       [ORDER BY expr [ASC | DESC] [, ...]]
       [LIMIT n [OFFSET m] | LIMIT m, n]

item   := *  |  alias.*  |  expr [[AS] alias]
source := table [[AS] alias]  |  (SELECT ...) [AS] alias
```

- **No `FROM`:** `SELECT 1 + 1` returns one row.
- **Aliases:** an alias can follow without `AS`.
- **`LEFT JOIN`:** needs `ON`. A comma join is a cross join that you filter with `WHERE`.
- **`GROUP BY`, `ORDER BY` and `HAVING`** can use output column numbers (`ORDER BY 2`) and output aliases.
- **Columns that aren't grouped or aggregated** take their value from the first row of each group.
- **`HAVING`** needs `GROUP BY` or an aggregate.
- **An aggregate query with no rows** and no `GROUP BY` still returns one row: `COUNT(*) = 0`, and the other aggregates are `NULL`.
- **Correlation:** subqueries are uncorrelated (they can't read columns of the outer query). Each runs once, the first time it's needed.

### Names and literals

| Form | Meaning |
|---|---|
| `name`, `t.name` | A column. An unqualified name must be unique across the joined tables. |
| `"name"`, `` `name` ``, `[name]` | A quoted name. A double-quoted name that matches no column is used as a text value, as in SQLite, so `WHERE x = "fire"` works. |
| `'text'` | Text. Write `''` for a single quote. |
| `42`, `3.5`, `1e3`, `0x1F` | Numbers |
| `TRUE`, `FALSE`, `NULL` | Literals |
| `?` | A parameter from `opts.params` |

### Operators

Highest precedence first:

| Precedence | Operators |
|---|---|
| 1 | unary `-`, `+` |
| 2 | `*` `/` `%` |
| 3 | `+` `-` |
| 4 | `\|\|` (concatenation) |
| 5 | `=` `==` `!=` `<>` `<` `<=` `>` `>=`, `[NOT] LIKE`, `[NOT] IN (...)`, `[NOT] BETWEEN a AND b`, `IS [NOT] NULL` |
| 6 | `NOT` |
| 7 | `AND` |
| 8 | `OR` |

Other expressions:
- `CASE WHEN c THEN v ... [ELSE v] END`, and `CASE x WHEN v THEN r ... END`
- `CAST(x AS INT | INTEGER | REAL | NUMBER | FLOAT | TEXT | STRING | BOOL)`
- `EXISTS (SELECT ...)`, `x IN (SELECT ...)` (the subquery returns one column), and `(SELECT ...)` as a value (first row, first column)

### Values and comparison

- **`NULL`:** any comparison or arithmetic with `NULL` gives `NULL`. `WHERE` keeps only rows whose condition is true. `AND`/`OR` use three-valued logic: `NULL AND FALSE` is `FALSE`, and `NULL OR TRUE` is `TRUE`.
- **Text is case-insensitive** for `=`, `<`, `IN`, `ORDER BY`, `GROUP BY` and `DISTINCT`. So `WHERE name = 'molten whip'` matches.
- **Number vs text:** text that parses as a number compares as that number. Other text compares as text.
- **Booleans** compare and sum as 1 and 0, so `SUM(unlocked)` counts the true values. `WHERE passive` is the same as `WHERE passive = TRUE`.
- **Arithmetic:** `/` always gives a decimal (`10 / 4 = 2.5`). Dividing by zero, or `%` by zero, gives `NULL`. `%` follows `math.fmod`. Text in arithmetic is parsed as a number, and becomes `NULL` if it isn't one.
- **`||`:** joins the text of both sides. If either side is `NULL`, the result is `NULL`.
- **`CAST(x AS INT)`** truncates toward zero.
- **`LIKE`:** `%` matches any run of characters and `_` matches one character, ignoring case. `LIKE pattern ESCAPE 'c'` makes the character after `c` match itself: `LIKE '%100!%%' ESCAPE '!'` finds text containing `100%`. The escape is any single character, given as a constant, `?` or a column, and `ESCAPE NULL` gives `NULL`. A pattern that ends with the escape character is an error. To match text a player typed, escape it with `ESCAPE()` / `LibESQL.Escape`. For Lua patterns, use `MATCH()`.

### Aggregates

| Function | Result |
|---|---|
| `COUNT(*)` | Rows |
| `COUNT(x)`, `COUNT(DISTINCT x)` | Non-NULL values, or distinct non-NULL values |
| `SUM(x)` | Sum of the values, or `NULL` when there are none |
| `TOTAL(x)` | Like `SUM`, but 0 when there are none |
| `AVG(x)` | Average, or `NULL` when there are none |
| `MIN(x)`, `MAX(x)` | Smallest or largest, in `ORDER BY` order (works on text too) |
| `GROUP_CONCAT(x [, 'sep'])` | Values joined with `sep` (default `,`). `sep` must be a constant. |

`DISTINCT` works inside any aggregate. Aggregates can't be nested and can't appear in `WHERE`.

---

## Scalar functions

Unless noted, any `NULL` argument gives `NULL`. Text matching ignores case.

### Text

| Function | Result |
|---|---|
| `LOWER(s)`, `UPPER(s)` | Case-converted text |
| `LENGTH(s)`, `LEN(s)` | Bytes |
| `SUBSTR(s, start [, len])`, `SUBSTRING` | Part of `s`. `start` is 1-based, and a negative `start` counts from the end. |
| `LEFT(s, n)`, `RIGHT(s, n)` | The first or last `n` characters |
| `TRIM(s)`, `LTRIM(s)`, `RTRIM(s)` | `s` without surrounding spaces |
| `REPLACE(s, find, with)` | Plain-text replace of every occurrence |
| `INSTR(s, find)` | 1-based position, or 0 |
| `CONTAINS(s, find)`, `STARTSWITH(s, find)` | Boolean |
| `MATCH(s, luaPattern)` | Boolean (`string.find` with a Lua pattern) |
| `CAPTURE(s, luaPattern)` | The first capture, or the whole match |
| `CONCAT(a, b, ...)` | Joined text. `NULL`s are skipped. |
| `CONCAT_WS(sep, a, b, ...)` | Joined with `sep`. `NULL`s are skipped. |
| `PRINTF(fmt, ...)`, `FORMAT` | `string.format` |
| `ESCAPE(s [, c])` | `s` with `%`, `_` and `c` (default `\`) prefixed by `c`, so it matches itself in `LIKE ... ESCAPE 'c'`: `name LIKE '%' \|\| ESCAPE(?) \|\| '%' ESCAPE '\'` |
| `QUOTE(x)` | `x` as an SQL literal: `'it''s'`, `42`, `NULL`, `TRUE` (like `LibESQL.Quote`) |
| `CHAR(n, ...)` | Characters from byte values |
| `HEX(n)` | Upper-case hex |

### Numbers

| Function | Result |
|---|---|
| `ABS(x)`, `SIGN(x)` | Absolute value; -1, 0 or 1 |
| `ROUND(x [, digits])` | Rounded, half up (default 0 digits) |
| `FLOOR(x)`, `CEIL(x)`, `CEILING(x)` | Rounded down or up |
| `SQRT(x)` | Square root, or `NULL` for a negative `x` |
| `POWER(x, y)`, `POW` | `x ^ y` |
| `MOD(x, y)` | `x % y`, or `NULL` when `y` is 0 |
| `MIN(a, b, ...)`, `MAX(a, b, ...)` | With two or more arguments: the smallest or largest. `NULL` if any argument is `NULL`. |
| `RANDOM()`, `RANDOM(a, b)` | `math.random` |
| `MS_TO_S(ms)` | `ms / 1000` |

### NULL and logic

| Function | Result |
|---|---|
| `COALESCE(a, b, ...)` | The first argument that isn't `NULL` |
| `IFNULL(a, b)`, `NVL` | `a`, or `b` when `a` is `NULL` |
| `NULLIF(a, b)` | `NULL` if `a = b`, otherwise `a` |
| `IIF(cond, a, b)`, `IF` | `a` if `cond` is true, otherwise `b` |
| `TYPEOF(x)` | `null`, `integer`, `real`, `text` or `boolean` |

### Time

| Function | Result |
|---|---|
| `NOW()`, `CURRENT_TIMESTAMP`, `LOCALTIMESTAMP` | The current local date and time as text, `'2026-11-20 14:05:33'` (like MySQL) |
| `CURRENT_DATE`, `CURDATE()` | `'2026-11-20'` |
| `CURRENT_TIME`, `CURTIME()` | `'14:05:33'` |
| `UNIX_TIMESTAMP()` | Seconds since 1970 (UTC), the same as the game's `GetTimeStamp()`. Use it for numbers you store and do maths with. |
| `UNIX_TIMESTAMP(text)` | Parses `'2026-11-20'`, `'2026-11-20 14:05'` or `'2026-11-20T14:05:33'` (local time) into seconds. Gives `NULL` for a date it can't read. |
| `FROM_UNIXTIME(ts [, fmt])` | A stored timestamp as local date-time text, by default `'2026-11-20 14:05:33'` |
| `DATE(ts [, fmt])` | Formats a timestamp, by default with the time. `DATE('2026-11-20 14:05:33')` gives the date part, `'2026-11-20'`. |

Notes:
- **Without brackets:** `CURRENT_TIMESTAMP`, `CURRENT_DATE`, `CURRENT_TIME` and `LOCALTIMESTAMP` can be written without brackets, as in standard SQL.
- **Once per statement:** these zero-argument functions are worked out once per statement, so every row of one query gets the same time, even when the query is spread over several frames.
- **Comparing:** the text forms sort correctly (`WHERE at > '2026-11-01'`).
- **Doing maths:** for date maths, use `UNIX_TIMESTAMP()` numbers (`UNIX_TIMESTAMP() - 7 * 86400`), then show them with `FROM_UNIXTIME`.
- **Format codes:** `fmt` uses `os.date` / strftime codes, such as `%Y %m %d %H %M %S`. Where the game has no `os.date` (console), the dates are worked out from `GetTimeStamp()` and the local clock (`GetDate`, `GetSecondsSinceMidnight`). That supports `%Y %y %m %d %H %M %S %%`, and uses the current UTC offset, so old timestamps from before a daylight-saving change can show one hour off.

### ESO

| Function | Result |
|---|---|
| `ABILITY_NAME(id)` | Clean ability name |
| `ABILITY_DESC(id)` | Tooltip description |
| `ABILITY_ICON(id)` | Icon path |
| `ABILITY_DURATION(id)` | Duration in ms |
| `ABILITY_LINK(id)` | Chat link |
| `SET_NAME(id)` | Item set name |
| `ZONE_NAME(id)` | Zone name |
| `ITEM_NAME(idOrLink)` | Item name |
| `ITEM_LINK(id)` | A base item link |
| `ITEM_ID(link)` | The item id in a link |
| `COLLECTIBLE_NAME(id)`, `ACHIEVEMENT_NAME(id)` | Names |
| `CLEAN(s)`, `STRIP(s)` | `s` without grammar suffixes and markup |
| `ICON(path [, size])` | `\|t` texture markup (default size 24) |
| `ENUM(prefix, value)` | Constant name: `ENUM('ACTION_RESULT_', 1)` |
| `CONST(name)` | A global's value: `CONST('STAT_POWER')` |
| `STR(id or 'SI_NAME')` | `GetString(id)` |

---

## Performance

The engine always gives correct results. These features make the common cases fast:

- **Key lookups:** on the first table, `WHERE key = c`, `key IN (c, ...)`, and on scan tables `key BETWEEN a AND b` (up to 200,000 ids) fetch rows directly instead of reading the whole table. `abilities WHERE id = 46340` never needs the id scan.
- **Join plans:** a join on `t.col = <earlier table expression>` uses one of two plans. On a scan table's key, it looks up each row directly. Otherwise it builds a hash of the joined table once.
- **WHERE pushdown:** for inner joins, each part of a `WHERE ... AND ...` is checked as soon as the tables it uses are bound, and it can drive a hash join.
- **Early stop:** without `ORDER BY`, `GROUP BY` or `DISTINCT`, a query stops reading rows once `LIMIT` (or `maxRows`) is reached.
- **Lazy columns:** expensive columns, such as an ability's description, cost or skill line, are read from the game only when a query uses them. Name only the columns you need: `SELECT *` over `abilities` reads every column of every row.
- **Name cache:** on PC, ability names are cached for the session after the first read, which makes repeated `name LIKE` searches fast. Console skips this to save memory.
- **Caching:** static tables are built once and stay cached until `REFRESH`. Live tables (inventory, effects, quests...) rebuild on every query.

---

## Tables

The tables below were generated from the library's own table definitions. Run `DESCRIBE <table>` in game for the same list.

- `scan`: rows come from the saved id index.
- `live`: read on every query.
- `static`: built once, cached until `REFRESH`.
- *(lazy)*: the column is read from the game only when a query uses it.

Text values from game enums use the constant's name, lower-cased and without its prefix. For example `BUFF_EFFECT_TYPE_DEBUFF` becomes `debuff`, and `ITEM_DISPLAY_QUALITY_LEGENDARY` becomes `legendary`.

### abilities

Every ability id in the game (scanned once per update). Columns are read on demand.  
Kind: **scan**  ·  Key: `id`

| Column | Type | Description |
|---|---|---|
| `id` | int | Ability id |
| `name` | text | Ability name *(lazy)* |
| `description` | text | Tooltip description *(lazy)* |
| `icon` | text | Icon texture path *(lazy)* |
| `duration_ms` | int | Duration in ms (0 = instant or none) *(lazy)* |
| `cast_ms` | int | Cast or channel time in ms *(lazy)* |
| `channeled` | bool | Channeled ability *(lazy)* |
| `cost` | int | Base resource cost *(lazy)* |
| `cost_mechanic` | text | Resource used: magicka, stamina, health, ultimate... *(lazy)* |
| `cost_over_time` | bool | Cost is paid over time *(lazy)* |
| `cooldown_ms` | int | Cooldown in ms *(lazy)* |
| `min_range` | int | Minimum range (cm) *(lazy)* |
| `max_range` | int | Maximum range (cm, 2800 = 28 m) *(lazy)* |
| `radius` | int | Area radius (cm) *(lazy)* |
| `angle` | int | Cone angle *(lazy)* |
| `target` | text | Target description (Self, Enemy, Area...) *(lazy)* |
| `passive` | bool | Passive ability *(lazy)* |
| `permanent` | bool | Permanent effect *(lazy)* |
| `ultimate` | bool | Ultimate ability *(lazy)* |
| `toggled` | bool | Duration is a toggle *(lazy)* |
| `buff_type` | int | BuffType enum value *(lazy)* |
| `buff_type_name` | text | BuffType name (major_*, minor_*...) *(lazy)* |
| `frequency_ms` | int | Tick interval in ms *(lazy)* |
| `role_tank` | bool | Flagged as a tank ability *(lazy)* |
| `role_healer` | bool | Flagged as a healer ability *(lazy)* |
| `role_dps` | bool | Flagged as a damage ability *(lazy)* |
| `header` | text | Description header *(lazy)* |
| `new_effect` | text | Morph's new effect lines *(lazy)* |
| `mundus` | text | Mundus stone this ability belongs to *(lazy)* |
| `crafted_ability_id` | int | Scribing grimoire id *(lazy)* |
| `is_player_skill` | bool | Part of a player skill line *(lazy)* |
| `skill_type` | text | class, weapon, armor, guild, ava, racial, world, tradeskill... *(lazy)* |
| `skill_line_id` | int | Skill line id *(lazy)* |
| `skill_line` | text | Skill line name *(lazy)* |
| `skill_index` | int | Index in the skill line *(lazy)* |
| `morph` | int | 0 = base, 1 / 2 = morphs *(lazy)* |
| `rank` | int | Skill rank *(lazy)* |
| `link` | text | Chat link *(lazy)* |

### skill_lines

Skill lines available to this character (class, weapon, armor, guild, world...)  
Kind: **live**  ·  Key: `id`

| Column | Type | Description |
|---|---|---|
| `id` | int | Skill line id |
| `name` | text | Skill line name |
| `skill_type` | text | class, weapon, armor, world, guild, ava, racial, tradeskill... |
| `skill_type_id` | int | SkillType enum value |
| `line_index` | int | Index within its skill type |
| `rank` | int | Current rank |
| `active` | bool | Line is active for this character |
| `discovered` | bool | Line is discovered |
| `class_id` | int | Class id for class lines |
| `num_skills` | int | Number of skills in the line |
| `xp` | int | Current XP in the rank |

### skills

Every skill in your skill lines: one row per morph (actives) or rank (passives)  
Kind: **live**

| Column | Type | Description |
|---|---|---|
| `ability_id` | int | Ability id of this morph / rank |
| `name` | text | Skill name |
| `line_id` | int | Skill line id |
| `line_name` | text | Skill line name |
| `skill_type` | text | class, weapon, armor, guild... |
| `skill_index` | int | Index in the line |
| `morph` | int | 0 = base, 1 / 2 = morphs (actives) |
| `rank` | int | Rank (passives) |
| `max_rank` | int | Highest passive rank |
| `passive` | bool | Passive skill |
| `ultimate` | bool | Ultimate skill |
| `purchased` | bool | You bought this skill |
| `current` | bool | This is the morph / rank you have now |
| `line_rank_needed` | int | Skill line rank needed to unlock |
| `progression_id` | int | Progression id (actives) |
| `crafted_ability_id` | int | Scribing grimoire id |
| `icon` | text | Icon texture path |
| `description` | text | Tooltip *(lazy)* |

### champion_skills

Champion point stars in every constellation  
Kind: **static**  ·  Key: `id`

| Column | Type | Description |
|---|---|---|
| `id` | int | Champion skill id |
| `name` | text | Star name |
| `discipline` | text | Constellation (Warfare, Fitness, Craft) |
| `discipline_id` | int | Discipline id |
| `discipline_type` | text | combat, conditioning, world |
| `skill_type` | text | normal, normal_slottable, stat_pool_slottable... |
| `slottable` | bool | Can be slotted |
| `max_points` | int | Max points |
| `ability_id` | int | Ability id behind the star |
| `cluster` | text | Cluster name, if in a cluster |
| `description` | text | Tooltip at 0 extra points *(lazy)* |
| `current_bonus` | text | Current bonus text *(lazy)* |
| `x` | num | Position in the constellation |
| `y` | num | Position in the constellation |

### crafted_abilities

Scribing grimoires  
Kind: **static**  ·  Key: `id`

| Column | Type | Description |
|---|---|---|
| `id` | int | Crafted ability (grimoire) id |
| `name` | text | Grimoire name |
| `description` | text | Description |
| `icon` | text | Icon |
| `ability_id` | int | Representative ability id |
| `skill_type` | text | Skill type it belongs to |
| `hint` | text | How to acquire |

### scribing_scripts

Scribing scripts (focus, signature, affix)  
Kind: **static**  ·  Key: `id`

| Column | Type | Description |
|---|---|---|
| `id` | int | Script id |
| `name` | text | Script name |
| `slot` | text | primary (focus), secondary (signature), tertiary (affix) |
| `description` | text | General description |
| `icon` | text | Icon |
| `hint` | text | How to acquire |

### effects

Buffs and debuffs active right now on you, your target, bosses, group and companion  
Kind: **live**

| Column | Type | Description |
|---|---|---|
| `unit` | text | Unit tag (player, reticleover, boss1, group3...) |
| `unit_name` | text | Unit name |
| `ability_id` | int | Effect ability id |
| `name` | text | Effect name |
| `stacks` | int | Stack count |
| `remaining_s` | num | Seconds left (NULL for permanent) |
| `duration_s` | num | Total duration in seconds (NULL for permanent) |
| `start_s` | num | Game time when it started (s) |
| `end_s` | num | Game time when it ends (s) |
| `permanent` | bool | No end time |
| `effect_type` | text | buff or debuff |
| `ability_type` | text | AbilityType name |
| `status_effect` | text | Status effect (burning, poisoned, ...) |
| `buff_type_name` | text | BuffType (major_*/minor_*) *(lazy)* |
| `cast_by_player` | bool | You applied it |
| `can_click_off` | bool | Can be cancelled |
| `slot` | int | Buff slot |
| `icon` | text | Icon |

### effects_seen

Every buff/debuff id seen while effect tracking is on (saved across sessions)  
Kind: **live**  ·  Key: `ability_id`

| Column | Type | Description |
|---|---|---|
| `ability_id` | int | Effect ability id |
| `name` | text | Name *(lazy)* |
| `times_seen` | int | How often it was gained or refreshed |
| `last_seen` | int | Unix time last seen |
| `on_player` | bool | Seen on you |
| `on_others` | bool | Seen on other units |
| `from_player` | bool | Applied by you |
| `max_stacks` | int | Highest stack count seen |
| `effect_type` | text | buff or debuff |
| `ability_type` | text | AbilityType name |
| `status_effect` | text | Status effect |
| `duration_ms` | int | Ability duration *(lazy)* |
| `icon` | text | Icon *(lazy)* |

### combat_log

Combat events recorded this session while logging is on (/esql log on)  
Kind: **live**

| Column | Type | Description |
|---|---|---|
| `seq` | int | Order received |
| `time_ms` | int | Game time in ms |
| `result` | text | damage, critical_damage, heal, dot_tick, blocked_damage, ... |
| `result_id` | int | ActionResult enum value |
| `ability_id` | int | Ability id |
| `ability` | text | Ability name |
| `source` | text | Source name |
| `source_type` | text | player, group, other, player_pet... |
| `target` | text | Target name |
| `target_type` | text | player, group, other... |
| `hit` | int | Damage / heal value |
| `overflow` | int | Overkill / overheal |
| `damage_type` | text | fire, shock, physical... |
| `power_type` | text | Resource for power events |
| `is_error` | bool | Error result |
| `source_unit_id` | int | Source unit id |
| `target_unit_id` | int | Target unit id |

### hotbar

Skills slotted on your front and back bars  
Kind: **live**

| Column | Type | Description |
|---|---|---|
| `bar` | text | primary, backup, ... |
| `slot` | int | Slot index (3-7 skills, 8 ultimate) |
| `ability_id` | int | Slotted ability id |
| `name` | text | Ability name |
| `icon` | text | Icon *(lazy)* |
| `active_bar` | bool | This bar is active now |

### sets

Every item set: type, category, pieces, bonuses  
Kind: **static**  ·  Key: `id`

| Column | Type | Description |
|---|---|---|
| `id` | int | Item set id |
| `name` | text | Set name |
| `set_type` | text | crafted, dungeon, monster, trial, overland, arena, mythic, cyrodiil... |
| `max_equipped` | int | Pieces for the full bonus |
| `num_bonuses` | int | Number of bonus lines |
| `in_collection` | bool | Listed in the set collections UI |
| `category` | text | Collection category |
| `parent_category` | text | Parent collection category |
| `category_id` | int | Collection category id |
| `perfected` | bool | Perfected version of another set |
| `unperfected_id` | int | Set id of the non-perfected version |
| `num_pieces` | int | Collectible pieces |
| `pieces_unlocked` | int | Pieces you have unlocked *(lazy)* |
| `bonuses` | text | All bonus lines in one text *(lazy)* |

### set_bonuses

One row per set bonus line  
Kind: **static**

| Column | Type | Description |
|---|---|---|
| `set_id` | int | Item set id |
| `set_name` | text | Set name |
| `bonus_index` | int | Bonus line number |
| `num_required` | int | Pieces required |
| `description` | text | Bonus text |
| `perfected` | bool | Perfected-only bonus |

### set_pieces

Every collectible piece of every set, with item details  
Kind: **static**

| Column | Type | Description |
|---|---|---|
| `set_id` | int | Item set id |
| `set_name` | text | Set name |
| `piece_id` | int | Collection piece id |
| `item_id` | int | Item id *(lazy)* |
| `link` | text | Item link |
| `unlocked` | bool | You have it in your collection *(lazy)* |
| `name` | text | Item name *(lazy)* |
| `icon` | text | Icon *(lazy)* |
| `item_type` | text | weapon, armor, potion, food, recipe, furnishing... *(lazy)* |
| `specialized_type` | text | Specialized item type *(lazy)* |
| `quality` | text | normal, magic, arcane, artifact, legendary, mythic_override *(lazy)* |
| `equip_type` | text | head, chest, ring, one_hand... *(lazy)* |
| `armor_type` | text | light, medium, heavy *(lazy)* |
| `weapon_type` | text | sword, bow, fire_staff... *(lazy)* |
| `trait` | text | Item trait *(lazy)* |
| `level` | int | Required level *(lazy)* |
| `cp` | int | Required champion points *(lazy)* |
| `value` | int | Vendor value *(lazy)* |
| `bind_type` | text | on_pickup, on_equip, ... *(lazy)* |
| `style` | text | Motif style *(lazy)* |
| `unique` | bool | Unique item *(lazy)* |
| `armor_rating` | int | Armor rating *(lazy)* |
| `weapon_power` | int | Weapon damage *(lazy)* |
| `on_use` | text | On-use effect description *(lazy)* |
| `flavor` | text | Flavor text *(lazy)* |

### items

Every item id in the game (scanned once per update; run SCAN items). Columns are read on demand.  
Kind: **scan**  ·  Key: `id`

| Column | Type | Description |
|---|---|---|
| `id` | int | Item id |
| `link` | text | Item link (base quality, level 1) |
| `name` | text | Item name *(lazy)* |
| `icon` | text | Icon *(lazy)* |
| `item_type` | text | weapon, armor, potion, food, recipe, furnishing... *(lazy)* |
| `specialized_type` | text | Specialized item type *(lazy)* |
| `quality` | text | normal, magic, arcane, artifact, legendary, mythic_override *(lazy)* |
| `equip_type` | text | head, chest, ring, one_hand... *(lazy)* |
| `armor_type` | text | light, medium, heavy *(lazy)* |
| `weapon_type` | text | sword, bow, fire_staff... *(lazy)* |
| `trait` | text | Item trait *(lazy)* |
| `set_id` | int | Item set id *(lazy)* |
| `set_name` | text | Item set name *(lazy)* |
| `level` | int | Required level *(lazy)* |
| `cp` | int | Required champion points *(lazy)* |
| `value` | int | Vendor value *(lazy)* |
| `bind_type` | text | on_pickup, on_equip, ... *(lazy)* |
| `style` | text | Motif style *(lazy)* |
| `unique` | bool | Unique item *(lazy)* |
| `armor_rating` | int | Armor rating *(lazy)* |
| `weapon_power` | int | Weapon damage *(lazy)* |
| `on_use` | text | On-use effect description *(lazy)* |
| `flavor` | text | Flavor text *(lazy)* |

### inventory

Items in your equipped slots, backpack, bank, craft bag and open house storage  
Kind: **live**

| Column | Type | Description |
|---|---|---|
| `bag` | text | worn, backpack, bank, subscriber_bank, virtual (craft bag), house_bank_* |
| `slot` | int | Slot index |
| `item_id` | int | Item id |
| `name` | text | Item name |
| `count` | int | Stack size |
| `link` | text | Item link |
| `equipped` | bool | Worn by you |
| `stolen` | bool | Stolen *(lazy)* |
| `locked` | bool | Player locked *(lazy)* |
| `bound` | bool | Bound *(lazy)* |
| `bag_id` | int | Bag id |
| `icon` | text | Icon *(lazy)* |
| `item_type` | text | weapon, armor, potion, food, recipe, furnishing... *(lazy)* |
| `specialized_type` | text | Specialized item type *(lazy)* |
| `quality` | text | normal, magic, arcane, artifact, legendary, mythic_override *(lazy)* |
| `equip_type` | text | head, chest, ring, one_hand... *(lazy)* |
| `armor_type` | text | light, medium, heavy *(lazy)* |
| `weapon_type` | text | sword, bow, fire_staff... *(lazy)* |
| `trait` | text | Item trait *(lazy)* |
| `set_id` | int | Item set id *(lazy)* |
| `set_name` | text | Item set name *(lazy)* |
| `level` | int | Required level *(lazy)* |
| `cp` | int | Required champion points *(lazy)* |
| `value` | int | Vendor value *(lazy)* |
| `bind_type` | text | on_pickup, on_equip, ... *(lazy)* |
| `style` | text | Motif style *(lazy)* |
| `unique` | bool | Unique item *(lazy)* |
| `armor_rating` | int | Armor rating *(lazy)* |
| `weapon_power` | int | Weapon damage *(lazy)* |
| `on_use` | text | On-use effect description *(lazy)* |
| `flavor` | text | Flavor text *(lazy)* |

### character

The character you are logged in on (one row)  
Kind: **live**

| Column | Type | Description |
|---|---|---|
| `name` | text | Character name |
| `account` | text | @account |
| `character_id` | text | Character id |
| `level` | int | Level |
| `cp` | int | Champion points earned (account) |
| `class` | text | Class |
| `class_id` | int | Class id |
| `race` | text | Race |
| `race_id` | int | Race id |
| `alliance` | text | Alliance |
| `zone` | text | Current zone |
| `zone_id` | int | Current zone id |
| `health_max` | int | Max health |
| `magicka_max` | int | Max magicka |
| `stamina_max` | int | Max stamina |
| `api_version` | int | Game API version |
| `console` | bool | Running the console UI |

### characters

Every character on this account and server  
Kind: **live**

| Column | Type | Description |
|---|---|---|
| `slot` | int | Character select order |
| `name` | text | Name |
| `class` | text | Class |
| `race` | text | Race |
| `level` | int | Level |
| `alliance` | text | Alliance |
| `id` | text | Character id |
| `location` | text | Last zone |

### stats

Your character sheet stats right now  
Kind: **live**

| Column | Type | Description |
|---|---|---|
| `stat` | text | Stat name (lower case, without STAT_) |
| `stat_id` | int | DerivedStats enum value |
| `value` | int | Value with bonuses |
| `base` | int | Value without bonuses |
| `label` | text | Display name *(lazy)* |

### currencies

Gold, AP, Tel Var, writ vouchers, transmute crystals... where you hold them  
Kind: **live**

| Column | Type | Description |
|---|---|---|
| `currency` | text | Currency key |
| `currency_id` | int | CurrencyType value |
| `name` | text | Display name |
| `carried` | int | On this character |
| `bank` | int | In the bank |
| `account` | int | Account-wide |
| `total` | int | Sum |

### quests

Quests in your journal  
Kind: **live**

| Column | Type | Description |
|---|---|---|
| `journal_index` | int | Journal index |
| `name` | text | Quest name |
| `type` | text | QuestType |
| `level` | int | Quest level |
| `zone` | text | Zone |
| `step` | text | Current step text |
| `background` | text | Background text |
| `tracked` | bool | Tracked |
| `completed` | bool | Ready to turn in |
| `repeat_type` | text | QuestRepeatableType *(lazy)* |

### completed_quests

Every quest this character has completed  
Kind: **live**  ·  Key: `id`

| Column | Type | Description |
|---|---|---|
| `id` | int | Quest id |
| `name` | text | Quest name |
| `type` | text | QuestType |
| `zone` | text | Zone *(lazy)* |
| `repeat_type` | text | QuestRepeatableType *(lazy)* |

### achievements

Every achievement with points, completion and rewards  
Kind: **live**  ·  Key: `id`

| Column | Type | Description |
|---|---|---|
| `id` | int | Achievement id |
| `name` | text | Name |
| `description` | text | Description |
| `points` | int | Achievement points |
| `completed` | bool | Completed |
| `date` | text | Completion date |
| `category` | text | Top category |
| `subcategory` | text | Subcategory |
| `icon` | text | Icon |
| `num_criteria` | int | Number of criteria *(lazy)* |
| `reward_title` | text | Title reward *(lazy)* |
| `reward_collectible_id` | int | Collectible reward *(lazy)* |
| `reward_dye_id` | int | Dye reward *(lazy)* |
| `reward_item` | text | Item reward *(lazy)* |
| `link` | text | Chat link *(lazy)* |

### achievement_criteria

Progress on each achievement criterion  
Kind: **live**

| Column | Type | Description |
|---|---|---|
| `achievement_id` | int | Achievement id |
| `achievement` | text | Achievement name |
| `criterion_index` | int | Criterion number |
| `description` | text | What to do |
| `completed` | int | Progress |
| `required` | int | Needed |
| `done` | bool | Criterion complete |

### collectibles

Mounts, pets, costumes, houses, mementos, emotes, skill styles... with unlock state  
Kind: **live**  ·  Key: `id`

| Column | Type | Description |
|---|---|---|
| `id` | int | Collectible id |
| `name` | text | Name |
| `category_type` | text | mount, vanity_pet, costume, house, memento, ... |
| `category` | text | Collections category *(lazy)* |
| `unlocked` | bool | Unlocked on this account |
| `active` | bool | Active now |
| `purchasable` | bool | Sold in the Crown Store |
| `description` | text | Description *(lazy)* |
| `hint` | text | Where to get it *(lazy)* |
| `icon` | text | Icon |
| `nickname` | text | Your nickname *(lazy)* |
| `reference_id` | int | Referenced id (house id, ...) *(lazy)* |
| `linked_achievement` | int | Achievement that grants it *(lazy)* |
| `link` | text | Chat link *(lazy)* |

### titles

Titles you have earned  
Kind: **live**

| Column | Type | Description |
|---|---|---|
| `title_index` | int | Index |
| `name` | text | Title |

### dyes

Every dye with colour and unlock state  
Kind: **live**  ·  Key: `id`

| Column | Type | Description |
|---|---|---|
| `id` | int | Dye id |
| `name` | text | Dye name |
| `known` | bool | Unlocked |
| `rarity` | text | common, uncommon, rare, material... |
| `hue` | text | Hue category |
| `achievement_id` | int | Achievement that unlocks it |
| `r` | num | Red 0-1 |
| `g` | num | Green 0-1 |
| `b` | num | Blue 0-1 |
| `hex` | text | RRGGBB |

### emotes

Every emote with its slash command  
Kind: **static**  ·  Key: `id`

| Column | Type | Description |
|---|---|---|
| `id` | int | Emote id |
| `emote_index` | int | Index |
| `slash` | text | Slash command |
| `name` | text | Display name |
| `category` | text | EmoteCategory |
| `collectible_id` | int | Collectible that unlocks it *(lazy)* |

### lore_books

Lore library books (Eidetic Memory, Shalidor's Library, crafting motifs...)  
Kind: **live**

| Column | Type | Description |
|---|---|---|
| `book_id` | int | Book id |
| `title` | text | Title |
| `known` | bool | You have read it |
| `category` | text | Library category |
| `collection` | text | Collection |
| `category_index` | int | Category index |
| `collection_index` | int | Collection index |
| `book_index` | int | Book index |
| `icon` | text | Icon |

### antiquities

Antiquities with quality, difficulty, zone and progress  
Kind: **live**  ·  Key: `id`

| Column | Type | Description |
|---|---|---|
| `id` | int | Antiquity id |
| `name` | text | Name |
| `quality` | text | AntiquityQuality |
| `difficulty` | text | AntiquityDifficulty |
| `zone_id` | int | Zone id |
| `zone` | text | Zone name |
| `set_name` | text | Antiquity set (mythic, furnishing set...) |
| `category` | text | Category |
| `recovered` | int | Times recovered |
| `lore_found` | int | Lore entries found |
| `lore_total` | int | Lore entries |
| `reward_id` | int | Reward id |
| `icon` | text | Icon |

### recipes

Provisioning and furnishing recipes with result items and whether you know them  
Kind: **live**

| Column | Type | Description |
|---|---|---|
| `list` | text | Recipe list |
| `list_index` | int | List index |
| `recipe_index` | int | Recipe index |
| `name` | text | Recipe name |
| `known` | bool | Known |
| `num_ingredients` | int | Ingredients |
| `skill_required` | int | Provisioner rank needed |
| `quality_required` | int | Recipe quality rank needed |
| `station` | text | Crafting station |
| `result_link` | text | Result item link *(lazy)* |
| `ingredients` | text | Ingredients *(lazy)* |

### guilds

Your guilds  
Kind: **live**

| Column | Type | Description |
|---|---|---|
| `id` | int | Guild id |
| `name` | text | Guild name |
| `members` | int | Member count |
| `guild_index` | int | Index |

### guild_members

Members of all your guilds  
Kind: **live**

| Column | Type | Description |
|---|---|---|
| `guild` | text | Guild name |
| `guild_id` | int | Guild id |
| `account` | text | @account |
| `note` | text | Member note |
| `rank_index` | int | Guild rank index |
| `status` | text | online, away, offline... |
| `offline_seconds` | int | Seconds since last online |

### friends

Your friends list  
Kind: **live**

| Column | Type | Description |
|---|---|---|
| `account` | text | @account |
| `note` | text | Note |
| `status` | text | online, away, offline... |
| `offline_seconds` | int | Seconds since last online |

### group_members

Your group members  
Kind: **live**

| Column | Type | Description |
|---|---|---|
| `unit` | text | Unit tag |
| `name` | text | Character name |
| `account` | text | @account |
| `class` | text | Class |
| `role` | text | dps, tank, heal |
| `level` | int | Level |
| `cp` | int | Champion points |
| `zone` | text | Zone |
| `online` | bool | Online |
| `leader` | bool | Group leader |
| `health` | int | Current health |
| `health_max` | int | Max health |

### zones

Every zone: name, parent zone, description, POI and skyshard counts  
Kind: **static**  ·  Key: `id`

| Column | Type | Description |
|---|---|---|
| `id` | int | Zone id |
| `zone_index` | int | Zone index |
| `name` | text | Zone name |
| `parent_zone_id` | int | Parent zone id |
| `parent_zone` | text | Parent zone name |
| `num_pois` | int | Points of interest |
| `num_skyshards` | int | Skyshards *(lazy)* |
| `collectible_id` | int | DLC collectible that unlocks it *(lazy)* |
| `story_zone_id` | int | Zone story zone id *(lazy)* |
| `description` | text | Description *(lazy)* |

### pois

Points of interest in every zone (wayshrines, dungeons, delves, skyshards...)  
Kind: **static**

| Column | Type | Description |
|---|---|---|
| `zone_id` | int | Zone id |
| `zone` | text | Zone name |
| `zone_index` | int | Zone index |
| `poi_index` | int | POI index in the zone |
| `name` | text | Name |
| `type` | text | PointOfInterestType |
| `instance_type` | text | InstanceType *(lazy)* |
| `skyshard_id` | int | Skyshard id *(lazy)* |
| `level` | int | Objective level |
| `start_text` | text | Start description |
| `finished_text` | text | Finished description |

### wayshrines

Fast-travel nodes (wayshrines, dungeons, trials, houses) and whether you know them  
Kind: **live**

| Column | Type | Description |
|---|---|---|
| `node_index` | int | Fast travel node index |
| `name` | text | Name |
| `known` | bool | Discovered |
| `type` | text | PointOfInterestType |
| `x` | num | Normalized map x |
| `y` | num | Normalized map y |
| `house_id` | int | House id for houses *(lazy)* |
| `zone_id` | int | Zone id *(lazy)* |
| `icon` | text | Map icon |

### activities

Group finder activities: dungeons, trials, battlegrounds, arenas...  
Kind: **static**  ·  Key: `id`

| Column | Type | Description |
|---|---|---|
| `id` | int | Activity id |
| `name` | text | Name |
| `type` | text | LFGActivity: dungeon, master_dungeon, trial, battle_ground_*... |
| `min_level` | int | Minimum level |
| `max_level` | int | Maximum level |
| `min_cp` | int | Minimum champion points |
| `max_cp` | int | Maximum champion points |
| `group_type` | text | LFGGroupType |
| `min_group_size` | int | Minimum group size |
| `zone_id` | int | Zone id *(lazy)* |
| `description` | text | Description |

### classes

Playable classes and their skill lines  
Kind: **static**  ·  Key: `id`

| Column | Type | Description |
|---|---|---|
| `id` | int | Class id |
| `name` | text | Class name |
| `selectable` | bool | Selectable at character creation |
| `num_skill_lines` | int | Class skill lines |
| `skill_lines` | text | Skill line names |
| `collectible_id` | int | Collectible that unlocks the class |

### class_skill_lines

Skill lines of every class, including classes you don't play  
Kind: **static**  ·  Key: `id`

| Column | Type | Description |
|---|---|---|
| `id` | int | Skill line id |
| `name` | text | Skill line name |
| `class_id` | int | Class id |
| `class` | text | Class name |
| `line_number` | int | 1-3 within the class |

### races

Playable races  
Kind: **static**  ·  Key: `id`

| Column | Type | Description |
|---|---|---|
| `id` | int | Race id |
| `name` | text | Race name |

### maps

World maps  
Kind: **static**  ·  Key: `map_index`

| Column | Type | Description |
|---|---|---|
| `map_index` | int | Map index |
| `name` | text | Map name |
| `map_type` | text | UIMapType |
| `content_type` | text | MapContentType |
| `zone_index` | int | Zone index |
| `zone_id` | int | Zone id |
| `description` | text | Description |

### tables

Every table you can query  
Kind: **live**  ·  Key: `name`

| Column | Type | Description |
|---|---|---|
| `name` | text | Table name |
| `kind` | text | static (cached), live (read every query), scan (id index), user (yours) |
| `description` | text | What is in it |
| `num_columns` | int | Column count |
| `key` | text | Primary key column |
| `rows_cached` | int | Rows in memory or ids indexed (NULL until first use) |
| `builtin` | bool | Comes with LibESQL; always read-only |
| `writable` | bool | INSERT / UPDATE / DELETE allowed (tables you created) |

### columns

Every column of every table  
Kind: **live**

| Column | Type | Description |
|---|---|---|
| `table_name` | text | Table |
| `column_name` | text | Column |
| `position` | int | Column order |
| `type` | text | int, num, text, bool |
| `description` | text | Meaning |
| `lazy` | bool | Computed when read |

### constants

Every numeric game constant (enums, flags, limits) except SI_ string ids  
Kind: **static**  ·  Key: `name`

| Column | Type | Description |
|---|---|---|
| `name` | text | Constant name |
| `value` | num | Value |
| `family` | text | Name without its last word (ACTION_RESULT_DAMAGE -> ACTION_RESULT) |

### events

Every EVENT_* id  
Kind: **static**  ·  Key: `name`

| Column | Type | Description |
|---|---|---|
| `name` | text | Event name |
| `id` | int | Event id |

### strings

Every localized string (SI_* ids) in your game language  
Kind: **static**  ·  Key: `name`

| Column | Type | Description |
|---|---|---|
| `name` | text | String id name |
| `id` | int | String id |
| `text` | text | Localized text *(lazy)* |

### functions

Every global function (game API and add-on functions)  
Kind: **static**  ·  Key: `name`

| Column | Type | Description |
|---|---|---|
| `name` | text | Function name |
| `kind` | text | api (from the game, PascalCase) or lua (other) |

### sounds

Every entry in the SOUNDS table (PlaySound names)  
Kind: **static**  ·  Key: `name`

| Column | Type | Description |
|---|---|---|
| `name` | text | SOUNDS key |
| `value` | text | Sound id |

### saved_variables

Other add-ons' SavedVariables found in memory (read-only; SCAN savedvariables to refresh)  
Kind: **live**  ·  Key: `name`

| Column | Type | Description |
|---|---|---|
| `name` | text | Global name of the saved variable |
| `addon` | text | Add-on it most likely belongs to (guessed from the name) |
| `style` | text | ZO_SavedVars, or registered (added with LibESQL.AddSavedVariable) |
| `accounts` | int | Accounts with data |
| `characters` | int | Characters with their own data |
| `account_wide` | bool | Has account-wide data |
| `tables` | int | Tables generated from it |
| `tables_list` | text | Names of those tables |
| `nodes` | int | Tables inside it that were looked at |
| `truncated` | bool | Too big to look through completely |

### sv_tables

Tables made from other add-ons' SavedVariables (each list of records becomes a table)  
Kind: **live**  ·  Key: `table_name`

| Column | Type | Description |
|---|---|---|
| `table_name` | text | Query it: SELECT * FROM <table_name> |
| `sv` | text | Saved variable it comes from |
| `addon` | text | Add-on it most likely belongs to |
| `pattern` | text | Where the list is inside the saved variable (* = any key) |
| `records` | int | Records when it was found |
| `columns` | int | Columns |

### sv_values

Every value in other add-ons' SavedVariables, one row per value (filter with WHERE sv = '...')  
Kind: **live**

| Column | Type | Description |
|---|---|---|
| `sv` | text | Saved variable |
| `addon` | text | Add-on it most likely belongs to |
| `account` | text | @account |
| `scope` | text | Character name, or account-wide |
| `path` | text | Path inside the data, e.g. settings.window.x |
| `key` | text | Last part of the path |
| `value` | any | The value |
| `type` | text | string, number or boolean |
| `depth` | int | How deep it is |

---

MIT License. See [LICENSE](LICENSE).
