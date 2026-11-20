# ESQL

An in-game SQL window for Elder Scrolls Online, built on [LibESQL](../LibESQL/README.md). Look up any ability id, find sets by their bonus text, list your buffs, count your collectibles, and keep notes and lists of your own in saved tables. It works on PC/Mac and console.

```sql
SELECT id, name, duration_ms, cost FROM abilities WHERE name LIKE '%whip%'
SELECT s.name, b.description FROM sets s JOIN set_bonuses b ON b.set_id = s.id WHERE b.description LIKE '%critical%'
SELECT unit, name, remaining_s FROM effects WHERE unit = 'player'
```

## Install

1. Copy the `ESQL` and `LibESQL` folders into `Documents/Elder Scrolls Online/live/AddOns/`.
2. For console, also install **LibHarvensAddonSettings**.
3. Enable both add-ons and `/reloadui`.

## Using it

**On PC**
- Type `/esql` to open the window, or bind a key in Controls > Keybindings > ESQL.
- Type a query and press Enter or **Run**. You can also run SQL directly from chat: `/esql SELECT * FROM character`.
- The arrow keys step through your last 50 queries.
- Scroll the results with the mouse wheel. Shift+wheel, or the `<` `>` buttons, moves across columns.
- Click a column header to sort by it. Hover a cell to see its full text, and click a row to print it to chat.
- **Example** cycles through ready-made queries. **Tables** lists everything you can query, and **Help** shows the syntax.
- **New table** opens the Create Table dialog:
  - **Start from** fills in a template (Notes, Wishlist, Boss times, Shopping list).
  - Name the table, then give each column a name and pick its type from the dropdown: **TEXT** for words, **INT** for whole numbers, **REAL** for decimals, **BOOL** for true/false, or **ANY**.
  - **+ Add column** adds a row and **X** removes one. The line underneath shows the exact `CREATE TABLE`, or what needs fixing.
  - **Create** makes the table and puts a ready `INSERT` for it in the query box.
- **Copy** opens the results as tab-separated text. Use **Copy to clipboard**, or Ctrl+A and Ctrl+C, then paste into a spreadsheet.
- **A-** / **A+** change the text size, which is remembered.

**On console** (Settings > Addons > ESQL)
- **Edit SQL** opens the on-screen keyboard. Confirm to run the query.
- **Example queries** and **Browse a table** fill in a query for you.
- Use **Down / Up / Right / Left** to page through the results window, and **Print** to send the visible rows to chat.
- **Create a table** makes a table without typing SQL:
  1. Pick a template under **Start from** (Notes, Wishlist, Boss times, Shopping list) or **Blank**, then change the **Table name**.
     - To add columns, type a name in **New column**, pick its **Type** from the dropdown (TEXT, INT, REAL, BOOL or ANY) and press **Add column**. **Remove last column** takes one off.
     - You can also type the **Columns** line yourself, for example `id INT, note TEXT, done BOOL`.
  2. The line below shows the exact `CREATE TABLE` that will run, or what needs fixing.
  3. Press **Create**.
  4. **Add a row** opens the keyboard with a ready `INSERT` for the new table: change the values and confirm. **View** shows what's in it.

## Your own tables

Your own tables are saved with your account and come back after a reload. Every table that comes with ESQL is read-only and can't be changed, dropped or replaced: only tables you create can be written to. Run `SELECT name, writable FROM tables` to see which ones those are.

```sql
CREATE TABLE IF NOT EXISTS notes (id INT, note TEXT, done BOOL)
INSERT INTO notes VALUES (1, 'Farm Kinras''s Wrath', FALSE), (2, 'Buy soul gems', FALSE)
UPDATE notes SET done = TRUE WHERE id = 2
DELETE FROM notes WHERE done
SELECT * FROM notes
DROP TABLE notes
```

- You can also save any query result as a table: `SELECT name, set_type INTO my_sets FROM sets WHERE name LIKE '%mother%'`.
- `UPDATE` or `DELETE` without a `WHERE` changes every row of the table. ESQL asks first: press **Run** a second time to confirm.

## Commands (PC)

| Command | Does |
|---|---|
| `/esql` | Opens or closes the window |
| `/esql <sql>` | Runs a query |
| `/esql size 1.4` | Sets the text size (0.6 to 2.5) |
| `/esql track on` or `/esql track off` | Turns on or off the recording of every buff and debuff id you see (`effects_seen`) |
| `/esql log on`, `/esql log off` or `/esql log clear` | Turns on, turns off or clears combat event recording (`combat_log`) |
| `/esql export` | Saves the last result to `SavedVariables/ESQL.lua`, written on logout or `/reloadui` |
| `/esql reset` | Puts the window back in the middle of the screen |

`/sql` works too, if no other add-on uses it.

## Good to know

- The first query on `abilities` or `items` indexes every id once per game update. That takes a few seconds and runs in the background, and the window shows its progress.
- Text matching ignores case: `WHERE name = 'molten whip'` works.
- See the [LibESQL README](../LibESQL/README.md) for every table and SQL feature, and the [API Reference](../LibESQL/API%20Reference.md) for the full details.

## License

MIT. See [LICENSE](LICENSE).
