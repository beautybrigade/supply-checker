"""Command-line interface for the supply checker.

Examples:
    python3 supplies.py --file sample_supplies.csv list
    python3 supplies.py --file sample_supplies.csv restock "nail files" --packs 2
    python3 supplies.py --file sample_supplies.csv use acetone 0.25
    python3 supplies.py --file sample_supplies.csv low
"""

import argparse
import sys

import inventory as inv


def build_parser():
    parser = argparse.ArgumentParser(
        description="Track nail supplies stored in a CSV file."
    )
    parser.add_argument(
        "--file", default="supplies.csv",
        help="CSV file of supplies (default: supplies.csv)",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("list", help="show every supply")

    restock = commands.add_parser("restock", help="add stock to a supply")
    restock.add_argument("name", help="supply name (quote names with spaces)")
    how = restock.add_mutually_exclusive_group(required=True)
    how.add_argument("--packs", help="whole packs to add (pack items)")
    how.add_argument("--amount", help="amount to add in the unit (non-pack items)")

    use = commands.add_parser("use", help="subtract what was used")
    use.add_argument("name", help="supply name (quote names with spaces)")
    use.add_argument("amount", help="pieces for pack items, else amount in the unit")

    commands.add_parser("low", help="show supplies below their minimum")
    return parser


def cmd_list(supplies, path):
    headers = ["NAME", "PACK SIZE", "UNIT", "STOCK", "MINIMUM", ""]
    rows = [
        [s.name, inv.format_pack_size(s), s.unit, inv.format_stock(s),
         inv.format_number(s.minimum), "LOW" if inv.is_low(s) else ""]
        for s in supplies
    ]
    widths = [max(len(r[i]) for r in [headers] + rows) for i in range(len(headers))]
    for row in [headers] + rows:
        print("  ".join(cell.ljust(w) for cell, w in zip(row, widths)).rstrip())


def cmd_restock(supplies, path, args):
    supply = inv.find_supply(supplies, args.name, path)
    if args.packs is not None:
        packs = inv.parse_amount(args.packs, "packs")
        added = inv.restock_packs(supply, packs)
        pack_word = "pack" if packs == 1 else "packs"
        detail = (f"+{inv.format_number(packs)} {pack_word} "
                  f"({inv.format_amount(supply, added)})")
    else:
        amount = inv.parse_amount(args.amount)
        inv.restock_amount(supply, amount)
        detail = f"+{inv.format_amount(supply, amount)}"
    inv.save_supplies(path, supplies)
    print(f"Restocked {supply.name}: {detail}. Stock: {inv.format_stock(supply)}.")


def cmd_use(supplies, path, args):
    supply = inv.find_supply(supplies, args.name, path)
    amount = inv.parse_amount(args.amount)
    inv.use_supply(supply, amount)
    inv.save_supplies(path, supplies)
    print(f"Used {inv.format_amount(supply, amount)} of {supply.name}. "
          f"Stock: {inv.format_stock(supply)}.")
    if inv.is_low(supply):
        print(f"Warning: {supply.name} is below its minimum "
              f"({inv.format_amount(supply, supply.minimum)}).")


def cmd_low(supplies, path):
    low = inv.low_supplies(supplies)
    if not low:
        print("All supplies are at or above their minimum.")
        return
    print("Below minimum:")
    for s in low:
        print(f"  {s.name}: {inv.format_stock(s)} "
              f"(minimum {inv.format_amount(s, s.minimum)})")


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        supplies = inv.load_supplies(args.file)
        if args.command == "list":
            cmd_list(supplies, args.file)
        elif args.command == "restock":
            cmd_restock(supplies, args.file, args)
        elif args.command == "use":
            cmd_use(supplies, args.file, args)
        elif args.command == "low":
            cmd_low(supplies, args.file)
    except inv.InventoryError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
