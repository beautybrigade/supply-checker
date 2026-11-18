# Supply Checker — Specification

A command-line program that reads and updates a CSV file of nail-salon supplies,
so I can see what I have, restock, record what I used, and catch low stock
before an appointment.

Python standard library only. Run with `python3 supplies.py ...`.

## Files

| File | Role |
|------|------|
| `inventory.py` | All logic: reading/writing the CSV, validation, formatting, restock, use, low-stock checks. Never reads command-line arguments and never prints. Problems are raised as `InventoryError` with a clear message. |
| `supplies.py` | Command-line layer only: `argparse`, printing, error messages, exit codes. Calls `inventory.py`. |
| `sample_supplies.csv` | Made-up example data. |
| `tests/` | pytest tests, each naming the requirement it checks (R1–R6). |

## CSV format

The first row is a header. Required columns (any order; extra columns are
kept but ignored):

| Column | Meaning | Rules |
|--------|---------|-------|
| `name` | Supply name, e.g. `nail files` | Must not be blank. Must be unique (case-insensitive). |
| `pack_size` | Pieces per pack | Whole number ≥ 0. `0` means the supply does **not** come in packs. |
| `unit` | Unit of measurement, e.g. `pieces`, `gallons`, `bottles` | Must not be blank. For pack items this is the unit of one loose piece. |
| `quantity` | Current stock | Number ≥ 0. For pack items: total loose pieces, whole number. For other items: an amount in `unit`; decimals allowed (e.g. `1.5`). |
| `minimum` | Low-stock threshold | Number ≥ 0, same rules as `quantity` (pack items: pieces). |

Example:

```csv
name,pack_size,unit,quantity,minimum
nail files,50,pieces,120,60
acetone,0,gallons,1.5,1
```

Quantities are handled with Python's `decimal.Decimal` so amounts like
`1.1 - 0.2` come out exactly `0.9`. Whole numbers are written back without a
decimal point (`2`, not `2.0`).

## Commands

Every command accepts `--file PATH` (before the command name) to choose the
CSV file. The default is `supplies.csv` in the current directory.

```
python3 supplies.py [--file PATH] list
python3 supplies.py [--file PATH] restock NAME --packs N      # pack items
python3 supplies.py [--file PATH] restock NAME --amount X     # non-pack items
python3 supplies.py [--file PATH] use NAME AMOUNT
python3 supplies.py [--file PATH] low
```

`NAME` matches regardless of upper/lower case and surrounding spaces. Names
with spaces must be quoted: `"nail files"`.

### `list`
Prints every supply: name, pack size, unit, stock, minimum, and `LOW` next to
any supply below its minimum.

```
NAME            PACK SIZE   UNIT     STOCK                   MINIMUM
nail files      50          pieces   2 packs + 20 pieces     60
acetone         no packs    gallons  1.5 gallons             1
nail wipes      200         pieces   0 packs + 150 pieces    200       LOW
```

### `restock NAME --packs N` / `restock NAME --amount X`
- Pack items: `--packs N` (whole number > 0) adds `N × pack_size` pieces, so I
  never do the multiplication myself.
- Non-pack items: `--amount X` (number > 0, decimals allowed) adds `X` in the
  item's unit.
- Using `--packs` on a non-pack item, `--amount` on a pack item, both, or
  neither is an error.
- Saves the file and prints the new stock, e.g.
  `Restocked nail files: +2 packs (100 pieces). Stock: 4 packs + 20 pieces.`

### `use NAME AMOUNT`
- Subtracts `AMOUNT` (number > 0). Pack items: pieces, whole number.
  Non-pack items: amount in the unit, decimals allowed.
- Refuses if it would go below 0; the file is not changed:
  `Error: cannot use 3 pieces of nail files; only 2 pieces in stock.`
- On success saves and prints the new stock. If the supply is now below its
  minimum, also prints a warning:
  `Warning: nail files is below its minimum (60 pieces).`

### `low`
Lists only supplies below their minimum, with stock and minimum, or prints
`All supplies are at or above their minimum.`

## How each requirement is met

| ID | Requirement | How |
|----|-------------|-----|
| R1 | Display pack size and unit for each item | `pack_size` and `unit` columns; `list` shows both (pack size `0` shown as `no packs`). |
| R2 | Stock as packs + loose pieces, or amount + unit | `inventory.format_stock`: pack items → `P packs + L <unit>` (`1 pack` singular) from total pieces; others → `<amount> <unit>`. The unit is singular when its amount is exactly 1 (`1 bottle`, `1 pack + 1 piece`). Used by `list`, `low`, `restock`, `use`. |
| R3 | Restock by pack | `restock NAME --packs N` → `inventory.restock_packs` adds `N × pack_size`. |
| R4 | Per-item minimum and low alert | `minimum` column. "Below" means `quantity < minimum`. Shown by `low`, flagged `LOW` in `list`, and warned after `use`. |
| R5 | `use` subtracts, never below 0 | `inventory.use_supply` raises `InventoryError` if amount > stock; nothing is saved. |
| R6 | Clear errors: missing file, missing column, non-numeric quantity, unknown supply | `inventory.load_supplies` / `find_supply` raise `InventoryError` with messages below; `supplies.py` prints them to stderr as `Error: ...` and exits with code 1. |

### Error messages (R6 and related)

| Situation | Message |
|-----------|---------|
| File missing | `Error: supplies file 'x.csv' was not found.` |
| Missing column(s) | `Error: x.csv is missing column(s): minimum, unit.` |
| Number not a number (in file) | `Error: x.csv line 3 (acetone): quantity 'lots' is not a number.` |
| Negative / non-whole where whole required (in file) | `Error: x.csv line 3 (nail files): quantity must be a whole number of pieces.` (similar for negatives) |
| Unknown supply | `Error: no supply named 'glitter' in x.csv.` |
| Amount on command line not a number | `Error: amount 'two' is not a number.` |
| Amount ≤ 0 | `Error: amount must be greater than 0.` |

Exit codes: `0` success, `1` an error above, `2` command-line usage error
(argparse's default, e.g. unknown command).

## Out of scope

Adding or removing supplies (edit the CSV directly), multiple locations,
history of usage.
