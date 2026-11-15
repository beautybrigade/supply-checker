# Supply Checker

A small command-line program for tracking nail-technician supplies kept in a
CSV file, so you don't run out in the middle of a service.

It can:

- show every supply with its pack size, unit, stock, and minimum (R1, R2)
- show stock as **packs + loose pieces** for items sold in packs (nail files,
  wipes, sanding bands), or as an **amount + unit** for others (acetone,
  primer, monomer) (R2)
- restock by whole packs, without doing the math yourself (R3)
- flag supplies that have fallen below their own minimum (R4)
- subtract what you used, refusing to go below 0 (R5)
- give a clear error for a missing file, a missing column, a non-numeric
  quantity, or an unknown supply name (R6)

It uses only the Python standard library. See [spec.md](spec.md) for the full
design.

## The CSV file

```csv
name,pack_size,unit,quantity,minimum
nail files,50,pieces,120,60
acetone,0,gallons,1.5,1
```

- `pack_size` is pieces per pack; `0` means the supply doesn't come in packs.
- For pack items, `quantity` and `minimum` are counted in loose pieces.
- For other items they are amounts in `unit`, and decimals are allowed.

`sample_supplies.csv` is a made-up example. To start your own file, copy it:

```bash
cp sample_supplies.csv supplies.csv
```

## Commands

`--file` chooses the CSV file (default `supplies.csv`) and goes **before** the
command name. Quote names that contain spaces. Names match regardless of case.

List everything (`LOW` marks items below their minimum):

```bash
python3 supplies.py --file supplies.csv list
```

```
NAME           PACK SIZE  UNIT     STOCK                 MINIMUM
nail files     50         pieces   2 packs + 20 pieces   60
nail wipes     200        pieces   0 packs + 150 pieces  200      LOW
...
```

Restock a pack item by packs:

```bash
python3 supplies.py --file supplies.csv restock "nail files" --packs 2
# Restocked nail files: +2 packs (100 pieces). Stock: 4 packs + 20 pieces.
```

Restock a non-pack item by amount:

```bash
python3 supplies.py --file supplies.csv restock acetone --amount 2
# Restocked acetone: +2 gallons. Stock: 3.5 gallons.
```

Record what you used (pieces for pack items, unit amount otherwise):

```bash
python3 supplies.py --file supplies.csv use "nail files" 3
python3 supplies.py --file supplies.csv use acetone 0.25
```

Show only supplies below their minimum:

```bash
python3 supplies.py --file supplies.csv low
```

Errors go to standard error with exit code 1, for example:

```
Error: cannot use 3 pieces of nail files; only 2 pieces in stock.
Error: no supply named 'glitter' in supplies.csv.
```

## Running the tests

```bash
python3 -m pytest
```

Tests are in `tests/`, each named after the requirement (R1–R6) it checks.
They only use temporary copies, so `sample_supplies.csv` is never changed.

## Known limitations

- Units are printed exactly as written in the CSV, so a quantity of 1 reads
  as `1 bottles`.
- Adding or removing supplies is done by editing the CSV directly.
