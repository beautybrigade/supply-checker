"""Tests that run supplies.py as a real command, grouped by requirement R1-R6."""

import re

import pytest

import inventory as inv


def table(stdout):
    """Turn `list` output into {name: [columns...]} (columns split on 2+ spaces)."""
    lines = stdout.strip().splitlines()
    return {cols[0]: cols for cols in (re.split(r"\s{2,}", l.strip()) for l in lines[1:])}


def quantities(path):
    return {s.name: s.quantity for s in inv.load_supplies(path)}


# ---------- R1 ----------

def test_r1_list_shows_pack_size_and_unit_for_every_item(run_cli, sample_copy):
    result = run_cli("--file", sample_copy, "list")
    assert result.returncode == 0
    rows = table(result.stdout)
    assert len(rows) == 6
    assert rows["nail files"][1:3] == ["50", "pieces"]
    assert rows["nail wipes"][1:3] == ["200", "pieces"]
    assert rows["acetone"][1:3] == ["no packs", "gallons"]
    assert rows["monomer"][1:3] == ["no packs", "ounces"]


# ---------- R2 ----------

def test_r2_list_shows_stock_as_packs_or_amount(run_cli, sample_copy):
    rows = table(run_cli("--file", sample_copy, "list").stdout)
    assert rows["nail files"][3] == "2 packs + 20 pieces"
    assert rows["nail wipes"][3] == "0 packs + 150 pieces"
    assert rows["acetone"][3] == "1.5 gallons"
    assert rows["primer"][3] == "1 bottles"


# ---------- R3 ----------

def test_r3_restock_by_packs_updates_file(run_cli, sample_copy):
    result = run_cli("--file", sample_copy, "restock", "nail files", "--packs", "2")
    assert result.returncode == 0
    assert result.stdout == ("Restocked nail files: +2 packs (100 pieces). "
                             "Stock: 4 packs + 20 pieces.\n")
    assert quantities(sample_copy)["nail files"] == 220


def test_r3_restock_one_pack_uses_singular(run_cli, sample_copy):
    result = run_cli("--file", sample_copy, "restock", "nail wipes", "--packs", "1")
    assert result.stdout.startswith("Restocked nail wipes: +1 pack (200 pieces).")
    assert quantities(sample_copy)["nail wipes"] == 350


def test_r3_restock_amount_for_non_pack_item(run_cli, sample_copy):
    result = run_cli("--file", sample_copy, "restock", "acetone", "--amount", "2")
    assert result.returncode == 0
    assert result.stdout == "Restocked acetone: +2 gallons. Stock: 3.5 gallons.\n"
    assert quantities(sample_copy)["acetone"] == 3.5


def test_r3_restock_packs_on_non_pack_item_is_error(run_cli, sample_copy):
    before = sample_copy.read_bytes()
    result = run_cli("--file", sample_copy, "restock", "acetone", "--packs", "1")
    assert result.returncode == 1
    assert result.stderr == "Error: acetone does not come in packs; use --amount instead.\n"
    assert sample_copy.read_bytes() == before


def test_r3_restock_fractional_packs_is_error(run_cli, sample_copy):
    before = sample_copy.read_bytes()
    result = run_cli("--file", sample_copy, "restock", "nail files", "--packs", "1.5")
    assert result.returncode == 1
    assert result.stderr == "Error: packs must be a whole number.\n"
    assert sample_copy.read_bytes() == before


@pytest.mark.parametrize("extra", [[], ["--packs", "1", "--amount", "1"]])
def test_r3_restock_needs_exactly_one_of_packs_or_amount(run_cli, sample_copy, extra):
    result = run_cli("--file", sample_copy, "restock", "nail files", *extra)
    assert result.returncode == 2
    assert "--packs" in result.stderr


# ---------- R4 ----------

def test_r4_low_lists_only_items_below_minimum(run_cli, sample_copy):
    result = run_cli("--file", sample_copy, "low")
    assert result.returncode == 0
    assert result.stdout == ("Below minimum:\n"
                             "  nail wipes: 0 packs + 150 pieces (minimum 200 pieces)\n"
                             "  primer: 1 bottles (minimum 2 bottles)\n")


def test_r4_low_when_nothing_is_low(run_cli, make_csv):
    path = make_csv("name,pack_size,unit,quantity,minimum\n"
                    "nail files,50,pieces,60,60\nacetone,0,gallons,2,1\n")
    result = run_cli("--file", path, "low")
    assert result.returncode == 0
    assert result.stdout == "All supplies are at or above their minimum.\n"


def test_r4_list_flags_low_items(run_cli, sample_copy):
    rows = table(run_cli("--file", sample_copy, "list").stdout)
    flagged = {name for name, cols in rows.items() if cols[-1] == "LOW"}
    assert flagged == {"nail wipes", "primer"}


def test_r4_use_warns_when_item_falls_below_minimum(run_cli, sample_copy):
    result = run_cli("--file", sample_copy, "use", "nail files", "61")
    assert result.returncode == 0
    assert result.stdout == ("Used 61 pieces of nail files. Stock: 1 pack + 9 pieces.\n"
                             "Warning: nail files is below its minimum (60 pieces).\n")


def test_r4_use_does_not_warn_when_at_minimum(run_cli, sample_copy):
    result = run_cli("--file", sample_copy, "use", "nail files", "60")
    assert result.stdout == "Used 60 pieces of nail files. Stock: 1 pack + 10 pieces.\n"


# ---------- R5 ----------

def test_r5_use_subtracts_and_saves(run_cli, sample_copy):
    result = run_cli("--file", sample_copy, "use", "acetone", "0.25")
    assert result.returncode == 0
    assert result.stdout == "Used 0.25 gallons of acetone. Stock: 1.25 gallons.\n"
    assert "acetone,0,gallons,1.25,1" in sample_copy.read_text()


def test_r5_use_cannot_go_below_zero(run_cli, make_csv):
    path = make_csv("name,pack_size,unit,quantity,minimum\nnail files,50,pieces,2,60\n")
    before = path.read_bytes()
    result = run_cli("--file", path, "use", "nail files", "3")
    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == "Error: cannot use 3 pieces of nail files; only 2 pieces in stock.\n"
    assert path.read_bytes() == before


def test_r5_use_everything_leaves_zero(run_cli, make_csv):
    path = make_csv("name,pack_size,unit,quantity,minimum\nnail files,50,pieces,2,0\n")
    result = run_cli("--file", path, "use", "nail files", "2")
    assert result.returncode == 0
    assert quantities(path)["nail files"] == 0


# ---------- R6 ----------

def test_r6_cli_missing_file(run_cli):
    result = run_cli("--file", "nope.csv", "list")
    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == "Error: supplies file 'nope.csv' was not found.\n"


def test_r6_cli_default_file_is_supplies_csv(run_cli):
    result = run_cli("list")  # runs in an empty temp folder
    assert result.stderr == "Error: supplies file 'supplies.csv' was not found.\n"


def test_r6_cli_missing_column(run_cli, make_csv):
    path = make_csv("name,pack_size,quantity,minimum\nacetone,0,1,1\n", name="bad.csv")
    result = run_cli("--file", path, "list")
    assert result.returncode == 1
    assert result.stderr == f"Error: {path} is missing column(s): unit.\n"


def test_r6_cli_quantity_not_a_number(run_cli, make_csv):
    path = make_csv("name,pack_size,unit,quantity,minimum\nacetone,0,gallons,lots,1\n")
    result = run_cli("--file", path, "low")
    assert result.returncode == 1
    assert result.stderr == f"Error: {path} line 2 (acetone): quantity 'lots' is not a number.\n"


@pytest.mark.parametrize("args", [
    ["use", "glitter", "1"],
    ["restock", "glitter", "--packs", "1"],
])
def test_r6_cli_unknown_supply(run_cli, sample_copy, args):
    before = sample_copy.read_bytes()
    result = run_cli("--file", sample_copy, *args)
    assert result.returncode == 1
    assert result.stderr == f"Error: no supply named 'glitter' in {sample_copy}.\n"
    assert sample_copy.read_bytes() == before


def test_r6_cli_amount_not_a_number(run_cli, sample_copy):
    before = sample_copy.read_bytes()
    result = run_cli("--file", sample_copy, "use", "acetone", "two")
    assert result.returncode == 1
    assert result.stderr == "Error: amount 'two' is not a number.\n"
    assert sample_copy.read_bytes() == before


def test_r6_cli_name_matching_ignores_case(run_cli, sample_copy):
    result = run_cli("--file", sample_copy, "use", "ACETONE", "1")
    assert result.returncode == 0
    assert quantities(sample_copy)["acetone"] == 0.5
