import pytest

import validation


CATALOG = [
    {"equipment_id": "dumbbell", "name": "Dumbbells"},
    {"equipment_id": "pull_up_bar", "name": "Pull-Up Bar"},
]


def test_split_tokens_strips_and_drops_empties():
    assert validation.split_tokens(" a, b ,, c ") == ["a", "b", "c"]
    assert validation.split_tokens("") == []
    assert validation.split_tokens(None) == []


def test_valid_constraints_pass_through():
    assert validation.validate_constraints(["grip", "arm-load"]) == ["grip", "arm-load"]


def test_near_miss_constraint_is_rejected_not_silently_ignored():
    with pytest.raises(validation.TokenError) as exc:
        validation.validate_constraints(["arm_load"])
    assert "arm_load" in str(exc.value)
    assert "arm-load" in str(exc.value)


def test_valid_equipment_passes_through():
    assert validation.validate_equipment(["dumbbell"], catalog=CATALOG) == ["dumbbell"]


def test_unknown_equipment_is_rejected():
    with pytest.raises(validation.TokenError) as exc:
        validation.validate_equipment(["kettlebell"], catalog=CATALOG)
    assert "kettlebell" in str(exc.value)
    assert "dumbbell" in str(exc.value)


def test_equipment_validates_against_the_real_shipped_catalog():
    assert validation.validate_equipment(["sturdy_table", "sled"]) == ["sturdy_table", "sled"]
    with pytest.raises(validation.TokenError):
        validation.validate_equipment(["dumbbells"])  # plural typo


def test_valid_focus_tokens_pass_through():
    assert validation.validate_focus(["core", "legs", "arms"]) == ["core", "legs", "arms"]


def test_near_miss_focus_is_rejected_not_silently_ignored():
    with pytest.raises(validation.TokenError) as exc:
        validation.validate_focus(["cardio"])
    assert "cardio" in str(exc.value)
    assert "core" in str(exc.value)
