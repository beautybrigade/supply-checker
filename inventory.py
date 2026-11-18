"""Logic for the supply checker: reading, validating, updating, and formatting
supplies stored in a CSV file.

This module never prints and never reads command-line arguments. When
something is wrong it raises InventoryError with a message meant for the user.
"""

import csv
import os
import tempfile
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

REQUIRED_COLUMNS = ["name", "pack_size", "unit", "quantity", "minimum"]


class InventoryError(Exception):
    """A problem the user should see, such as a missing file or bad number."""


@dataclass
class Supply:
    name: str
    pack_size: int  # 0 means the supply does not come in packs
    unit: str
    quantity: Decimal  # pack items: total loose pieces
    minimum: Decimal
    extra: dict = field(default_factory=dict)  # unrecognized columns, kept as-is

    @property
    def comes_in_packs(self):
        return self.pack_size > 0


# ---------- numbers ----------

def _to_decimal(text):
    """Turn text into a finite Decimal, or return None if it isn't a number."""
    try:
        value = Decimal(text.strip())
    except (InvalidOperation, AttributeError):
        return None
    if not value.is_finite():  # rejects "nan" and "inf"
        return None
    return value


def _is_whole(value):
    return value == value.to_integral_value()


def format_number(value):
    """2 -> '2', Decimal('2.0') -> '2', Decimal('1.50') -> '1.5'."""
    if _is_whole(value):
        return str(int(value))
    return format(value.normalize(), "f")


def parse_amount(text, label="amount"):
    """Parse a positive number typed by the user (for restock or use)."""
    value = _to_decimal(text)
    if value is None:
        raise InventoryError(f"{label} '{text}' is not a number.")
    if value <= 0:
        raise InventoryError(f"{label} must be greater than 0.")
    return value


# ---------- reading and writing ----------

def load_supplies(path):
    """Read and validate the CSV file. Returns a list of Supply."""
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            columns = reader.fieldnames or []
            missing = [c for c in REQUIRED_COLUMNS if c not in columns]
            if missing:
                raise InventoryError(
                    f"{path} is missing column(s): {', '.join(sorted(missing))}."
                )
            supplies = []
            seen = set()
            for row in reader:
                supply = _row_to_supply(row, path, reader.line_num)
                key = _key(supply.name)
                if key in seen:
                    raise InventoryError(
                        f"{path} line {reader.line_num}: supply "
                        f"'{supply.name}' appears more than once."
                    )
                seen.add(key)
                supplies.append(supply)
            return supplies
    except FileNotFoundError:
        raise InventoryError(f"supplies file '{path}' was not found.") from None


def _row_to_supply(row, path, line):
    name = (row["name"] or "").strip()
    where = f"{path} line {line} ({name or 'no name'})"
    if not name:
        raise InventoryError(f"{where}: name is blank.")
    unit = (row["unit"] or "").strip()
    if not unit:
        raise InventoryError(f"{where}: unit is blank.")

    numbers = {}
    for column in ("pack_size", "quantity", "minimum"):
        text = row[column] or ""
        value = _to_decimal(text)
        if value is None:
            raise InventoryError(f"{where}: {column} '{text}' is not a number.")
        if value < 0:
            raise InventoryError(f"{where}: {column} must not be negative.")
        numbers[column] = value

    if not _is_whole(numbers["pack_size"]):
        raise InventoryError(f"{where}: pack_size must be a whole number.")
    pack_size = int(numbers["pack_size"])
    if pack_size > 0:
        for column in ("quantity", "minimum"):
            if not _is_whole(numbers[column]):
                raise InventoryError(
                    f"{where}: {column} must be a whole number of {unit}."
                )

    extra = {k: v for k, v in row.items() if k not in REQUIRED_COLUMNS and k}
    return Supply(name, pack_size, unit, numbers["quantity"],
                  numbers["minimum"], extra)


def save_supplies(path, supplies):
    """Write supplies back to the CSV file.

    Writes to a temporary file first and then swaps it in, so a crash halfway
    through cannot leave a half-written supplies file.
    """
    extra_columns = []
    for supply in supplies:
        for column in supply.extra:
            if column not in extra_columns:
                extra_columns.append(column)
    columns = REQUIRED_COLUMNS + extra_columns

    folder = os.path.dirname(os.path.abspath(path))
    fd, tmp_path = tempfile.mkstemp(dir=folder, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            for s in supplies:
                writer.writerow({
                    **s.extra,
                    "name": s.name,
                    "pack_size": s.pack_size,
                    "unit": s.unit,
                    "quantity": format_number(s.quantity),
                    "minimum": format_number(s.minimum),
                })
        os.replace(tmp_path, path)
    except BaseException:
        os.unlink(tmp_path)
        raise


# ---------- finding ----------

def _key(name):
    return name.strip().lower()


def find_supply(supplies, name, path="the file"):
    """Find a supply by name, ignoring case and surrounding spaces."""
    for supply in supplies:
        if _key(supply.name) == _key(name):
            return supply
    raise InventoryError(f"no supply named '{name.strip()}' in {path}.")


# ---------- formatting ----------

def format_pack_size(supply):
    return str(supply.pack_size) if supply.comes_in_packs else "no packs"


def singular_unit(unit):
    """Best-effort singular of a plural unit: 'pieces' -> 'piece',
    'bottles' -> 'bottle', 'boxes' -> 'box', 'oz' stays 'oz'."""
    lower = unit.lower()
    if lower.endswith("ies") and len(unit) > 3:
        return unit[:-3] + ("Y" if unit[-1].isupper() else "y")
    if lower.endswith(("ches", "shes", "sses", "xes", "zes")):
        return unit[:-2]
    if lower.endswith("s") and not lower.endswith("ss") and len(unit) > 1:
        return unit[:-1]
    return unit


def unit_for(amount, unit):
    """The unit as written for any amount except exactly 1, which gets the
    singular ('1 bottle', but '0 bottles', '1.5 gallons')."""
    return singular_unit(unit) if amount == 1 else unit


def format_amount(supply, amount):
    """An amount in the supply's unit, e.g. '3 pieces', '1 piece', '1.5 gallons'."""
    return f"{format_number(amount)} {unit_for(amount, supply.unit)}"


def format_stock(supply):
    """Pack items: '2 packs + 20 pieces'. Others: '1.5 gallons'."""
    if not supply.comes_in_packs:
        return format_amount(supply, supply.quantity)
    packs, loose = divmod(int(supply.quantity), supply.pack_size)
    pack_word = "pack" if packs == 1 else "packs"
    return f"{packs} {pack_word} + {loose} {unit_for(loose, supply.unit)}"


# ---------- changing stock ----------

def restock_packs(supply, packs):
    """Add whole packs to a pack item. Returns the number of pieces added."""
    if not supply.comes_in_packs:
        raise InventoryError(
            f"{supply.name} does not come in packs; use --amount instead."
        )
    packs = Decimal(packs)
    if packs <= 0:
        raise InventoryError("packs must be greater than 0.")
    if not _is_whole(packs):
        raise InventoryError("packs must be a whole number.")
    added = packs * supply.pack_size
    supply.quantity += added
    return added


def restock_amount(supply, amount):
    """Add an amount (in the supply's unit) to a non-pack item."""
    if supply.comes_in_packs:
        raise InventoryError(
            f"{supply.name} comes in packs; use --packs instead."
        )
    amount = Decimal(amount)
    if amount <= 0:
        raise InventoryError("amount must be greater than 0.")
    supply.quantity += amount
    return amount


def use_supply(supply, amount):
    """Subtract what was used. Refuses to go below 0 (nothing changes then)."""
    amount = Decimal(amount)
    if amount <= 0:
        raise InventoryError("amount must be greater than 0.")
    if supply.comes_in_packs and not _is_whole(amount):
        raise InventoryError(
            f"{supply.name} is counted in whole {supply.unit}; "
            f"{format_number(amount)} is not a whole number."
        )
    if amount > supply.quantity:
        raise InventoryError(
            f"cannot use {format_amount(supply, amount)} of {supply.name}; "
            f"only {format_amount(supply, supply.quantity)} in stock."
        )
    supply.quantity -= amount


# ---------- low stock ----------

def is_low(supply):
    return supply.quantity < supply.minimum


def low_supplies(supplies):
    return [s for s in supplies if is_low(s)]
