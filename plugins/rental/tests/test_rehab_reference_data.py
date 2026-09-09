import json
import pathlib

REFERENCE_PATH = (pathlib.Path(__file__).parent.parent / "references"
                  / "rehab-costs-nh-seacoast.json")

REQUIRED_PROJECT_TYPES = {"bathroom_remodel", "kitchen_remodel", "roof_replacement", "electrical"}


def _load():
    with open(REFERENCE_PATH, encoding="utf-8") as f:
        return json.load(f)


def test_reference_file_is_valid_json_with_required_project_types():
    data = _load()
    keys = {k for k in data if not k.startswith("_")}
    assert REQUIRED_PROJECT_TYPES.issubset(keys)


def test_every_line_item_has_required_fields_and_matches_its_tiers_declaration():
    data = _load()
    for project_type, spec in data.items():
        if project_type.startswith("_"):
            continue
        tiers = spec.get("tiers")
        for item in spec["line_items"]:
            label = f"{project_type}/{item['name']}"
            assert item["unit"] in ("sqft", "each", "linear_ft"), label
            assert "source" in item and item["source"], label
            if tiers is None:
                assert isinstance(item["parts"], (int, float)), label
                assert isinstance(item["labor"], (int, float)), label
            else:
                assert set(item["parts"].keys()) == set(tiers), label
                assert set(item["labor"].keys()) == set(tiers), label


def test_all_rates_are_strictly_positive():
    # Strictly > 0, not >= 0: catches a leftover 0.0 placeholder that should
    # have been replaced with a real researched rate.
    data = _load()
    for project_type, spec in data.items():
        if project_type.startswith("_"):
            continue
        tiers = spec.get("tiers")
        for item in spec["line_items"]:
            label = f"{project_type}/{item['name']}"
            if tiers is None:
                assert item["parts"] > 0, label
                assert item["labor"] > 0, label
            else:
                assert all(v > 0 for v in item["parts"].values()), label
                assert all(v > 0 for v in item["labor"].values()), label


def test_knob_and_tube_line_item_has_the_expected_trigger():
    data = _load()
    kt = next(li for li in data["electrical"]["line_items"]
             if li["name"] == "Knob-and-tube removal")
    assert kt["trigger"] == "year_built < 1960"
