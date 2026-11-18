"""Tests for inventory.py (the logic), grouped by requirement R1-R6."""

from decimal import Decimal

import pytest

import inventory as inv


def pack_item(quantity, pack_size=50, minimum=0):
    return inv.Supply("nail files", pack_size, "pieces",
                      Decimal(quantity), Decimal(minimum))


def liquid(quantity, minimum=0, unit="gallons"):
    return inv.Supply("acetone", 0, unit, Decimal(quantity), Decimal(minimum))


# ---------- R1: pack size and unit ----------

def test_r1_load_reads_pack_size_and_unit(sample_copy):
    supplies = {s.name: s for s in inv.load_supplies(sample_copy)}
    assert (supplies["nail files"].pack_size, supplies["nail files"].unit) == (50, "pieces")
    assert (supplies["acetone"].pack_size, supplies["acetone"].unit) == (0, "gallons")
    assert (supplies["primer"].pack_size, supplies["primer"].unit) == (0, "bottles")


def test_r1_format_pack_size():
    assert inv.format_pack_size(pack_item(0, pack_size=200)) == "200"
    assert inv.format_pack_size(liquid(1)) == "no packs"


# ---------- R2: stock as packs + loose pieces, or amount + unit ----------

@pytest.mark.parametrize("quantity, expected", [
    (120, "2 packs + 20 pieces"),
    (50, "1 pack + 0 pieces"),
    (7, "0 packs + 7 pieces"),
    (0, "0 packs + 0 pieces"),
])
def test_r2_pack_item_shows_packs_and_loose_pieces(quantity, expected):
    assert inv.format_stock(pack_item(quantity)) == expected


@pytest.mark.parametrize("quantity, unit, expected", [
    ("1.5", "gallons", "1.5 gallons"),
    ("3", "bottles", "3 bottles"),
    ("2.50", "ounces", "2.5 ounces"),
    ("4.0", "ounces", "4 ounces"),
])
def test_r2_non_pack_item_shows_amount_and_unit(quantity, unit, expected):
    assert inv.format_stock(liquid(quantity, unit=unit)) == expected


@pytest.mark.parametrize("quantity, unit, expected", [
    ("1", "bottles", "1 bottle"),
    ("1", "gallons", "1 gallon"),
    ("1.0", "ounces", "1 ounce"),
    ("0", "bottles", "0 bottles"),
    ("0.5", "gallons", "0.5 gallons"),
    ("1.5", "gallons", "1.5 gallons"),
])
def test_r2_unit_is_singular_only_for_exactly_one(quantity, unit, expected):
    assert inv.format_stock(liquid(quantity, unit=unit)) == expected


def test_r2_one_loose_piece_is_singular():
    assert inv.format_stock(pack_item(51)) == "1 pack + 1 piece"


@pytest.mark.parametrize("unit, expected", [
    ("pieces", "piece"), ("bottles", "bottle"), ("gallons", "gallon"),
    ("boxes", "box"), ("batteries", "battery"), ("oz", "oz"), ("glass", "glass"),
])
def test_r2_singular_unit(unit, expected):
    assert inv.singular_unit(unit) == expected


def test_r2_sample_file_stock_formatting(sample_copy):
    stock = {s.name: inv.format_stock(s) for s in inv.load_supplies(sample_copy)}
    assert stock["sanding bands"] == "3 packs + 40 pieces"
    assert stock["monomer"] == "16 ounces"


# ---------- R3: restock by pack ----------

def test_r3_restock_packs_multiplies_by_pack_size():
    supply = pack_item(20, pack_size=50)
    added = inv.restock_packs(supply, 3)
    assert added == 150
    assert supply.quantity == 170


def test_r3_restock_packs_refused_for_non_pack_item():
    supply = liquid("1.5")
    with pytest.raises(inv.InventoryError, match="does not come in packs"):
        inv.restock_packs(supply, 1)
    assert supply.quantity == Decimal("1.5")


@pytest.mark.parametrize("packs, message", [
    (0, "greater than 0"), (-2, "greater than 0"), (Decimal("1.5"), "whole number"),
])
def test_r3_restock_packs_rejects_bad_pack_counts(packs, message):
    supply = pack_item(20)
    with pytest.raises(inv.InventoryError, match=message):
        inv.restock_packs(supply, packs)
    assert supply.quantity == 20


def test_r3_restock_amount_for_non_pack_item():
    supply = liquid("1.5")
    inv.restock_amount(supply, Decimal("0.25"))
    assert supply.quantity == Decimal("1.75")


def test_r3_restock_amount_refused_for_pack_item():
    supply = pack_item(20)
    with pytest.raises(inv.InventoryError, match="comes in packs"):
        inv.restock_amount(supply, Decimal(5))
    assert supply.quantity == 20


def test_r3_restock_is_saved_and_other_columns_kept(make_csv):
    path = make_csv("name,pack_size,unit,quantity,minimum,supplier\n"
                    "nail files,50,pieces,20,60,Acme\n"
                    "acetone,0,gallons,1.5,1,Beauty Co\n")
    supplies = inv.load_supplies(path)
    inv.restock_packs(inv.find_supply(supplies, "nail files"), 2)
    inv.save_supplies(path, supplies)
    assert path.read_text() == ("name,pack_size,unit,quantity,minimum,supplier\n"
                                "nail files,50,pieces,120,60,Acme\n"
                                "acetone,0,gallons,1.5,1,Beauty Co\n")


# ---------- R4: per-item minimum and low alert ----------

def test_r4_each_item_has_its_own_minimum(sample_copy):
    minimums = {s.name: s.minimum for s in inv.load_supplies(sample_copy)}
    assert minimums["nail files"] == 60
    assert minimums["nail wipes"] == 200
    assert minimums["acetone"] == 1


@pytest.mark.parametrize("quantity, minimum, low", [
    (59, 60, True), (60, 60, False), (61, 60, False),
])
def test_r4_is_low_means_strictly_below_minimum(quantity, minimum, low):
    assert inv.is_low(pack_item(quantity, minimum=minimum)) is low


def test_r4_is_low_with_decimal_amounts():
    assert inv.is_low(liquid("0.9", minimum="1")) is True
    assert inv.is_low(liquid("1.0", minimum="1")) is False


def test_r4_low_supplies_finds_items_below_minimum(sample_copy):
    low = inv.low_supplies(inv.load_supplies(sample_copy))
    assert [s.name for s in low] == ["nail wipes", "primer"]


# ---------- R5: use, never below 0 ----------

def test_r5_use_subtracts_pieces():
    supply = pack_item(120)
    inv.use_supply(supply, 3)
    assert supply.quantity == 117


def test_r5_use_down_to_exactly_zero_is_allowed():
    supply = pack_item(2)
    inv.use_supply(supply, 2)
    assert supply.quantity == 0


def test_r5_use_more_than_stock_is_refused_and_stock_unchanged():
    supply = pack_item(2)
    with pytest.raises(inv.InventoryError) as error:
        inv.use_supply(supply, 3)
    assert str(error.value) == ("cannot use 3 pieces of nail files; "
                                "only 2 pieces in stock.")
    assert supply.quantity == 2


def test_r5_use_decimal_amount_is_exact():
    supply = liquid("1.1")
    inv.use_supply(supply, Decimal("0.2"))
    assert supply.quantity == Decimal("0.9")
    assert inv.format_stock(supply) == "0.9 gallons"


def test_r5_use_fraction_of_a_piece_is_refused():
    supply = pack_item(10)
    with pytest.raises(inv.InventoryError, match="whole"):
        inv.use_supply(supply, Decimal("1.5"))
    assert supply.quantity == 10


@pytest.mark.parametrize("amount", [0, -1])
def test_r5_use_rejects_zero_or_negative(amount):
    supply = pack_item(10)
    with pytest.raises(inv.InventoryError, match="greater than 0"):
        inv.use_supply(supply, amount)
    assert supply.quantity == 10


# ---------- R6: clear errors ----------

def test_r6_missing_file(tmp_path):
    path = tmp_path / "nope.csv"
    with pytest.raises(inv.InventoryError) as error:
        inv.load_supplies(path)
    assert str(error.value) == f"supplies file '{path}' was not found."


def test_r6_missing_column_is_named(make_csv):
    path = make_csv("name,pack_size,unit,quantity\nacetone,0,gallons,1\n")
    with pytest.raises(inv.InventoryError) as error:
        inv.load_supplies(path)
    assert str(error.value) == f"{path} is missing column(s): minimum."


def test_r6_several_missing_columns_are_all_named(make_csv):
    path = make_csv("name,quantity\nacetone,1\n")
    with pytest.raises(inv.InventoryError) as error:
        inv.load_supplies(path)
    assert str(error.value) == f"{path} is missing column(s): minimum, pack_size, unit."


def test_r6_empty_file_reports_all_columns_missing(make_csv):
    path = make_csv("")
    with pytest.raises(inv.InventoryError, match="missing column"):
        inv.load_supplies(path)


@pytest.mark.parametrize("column, row", [
    ("quantity", "acetone,0,gallons,lots,1"),
    ("minimum", "acetone,0,gallons,1,some"),
    ("pack_size", "acetone,none,gallons,1,1"),
])
def test_r6_non_numeric_value_is_reported_with_line_and_column(make_csv, column, row):
    path = make_csv("name,pack_size,unit,quantity,minimum\n"
                    "nail files,50,pieces,20,60\n" + row + "\n")
    bad = row.split(",")[inv.REQUIRED_COLUMNS.index(column)]
    with pytest.raises(inv.InventoryError) as error:
        inv.load_supplies(path)
    assert str(error.value) == f"{path} line 3 (acetone): {column} '{bad}' is not a number."


def test_r6_blank_quantity_is_not_a_number(make_csv):
    path = make_csv("name,pack_size,unit,quantity,minimum\nacetone,0,gallons,,1\n")
    with pytest.raises(inv.InventoryError, match="quantity '' is not a number"):
        inv.load_supplies(path)


def test_r6_negative_quantity_is_rejected(make_csv):
    path = make_csv("name,pack_size,unit,quantity,minimum\nacetone,0,gallons,-1,1\n")
    with pytest.raises(inv.InventoryError, match="quantity must not be negative"):
        inv.load_supplies(path)


def test_r6_fractional_pieces_in_file_are_rejected(make_csv):
    path = make_csv("name,pack_size,unit,quantity,minimum\nnail files,50,pieces,2.5,60\n")
    with pytest.raises(inv.InventoryError, match="quantity must be a whole number of pieces"):
        inv.load_supplies(path)


def test_r6_unknown_supply_name(sample_copy):
    supplies = inv.load_supplies(sample_copy)
    with pytest.raises(inv.InventoryError) as error:
        inv.find_supply(supplies, "glitter", "supplies.csv")
    assert str(error.value) == "no supply named 'glitter' in supplies.csv."


def test_r6_supply_names_match_ignoring_case_and_spaces(sample_copy):
    supplies = inv.load_supplies(sample_copy)
    assert inv.find_supply(supplies, "  Nail FILES ").name == "nail files"


@pytest.mark.parametrize("text, message", [
    ("two", "amount 'two' is not a number."),
    ("nan", "amount 'nan' is not a number."),
    ("0", "amount must be greater than 0."),
    ("-3", "amount must be greater than 0."),
])
def test_r6_parse_amount_errors(text, message):
    with pytest.raises(inv.InventoryError) as error:
        inv.parse_amount(text)
    assert str(error.value) == message


def test_r6_parse_amount_accepts_decimals():
    assert inv.parse_amount("0.25") == Decimal("0.25")
