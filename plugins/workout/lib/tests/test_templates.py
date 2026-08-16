import templates as tpl_mod


SAMPLE_TEMPLATES = [
    {"template_id": "a", "level": "beginner", "days_per_week": 3, "required_equipment": []},
    {"template_id": "b", "level": "beginner", "days_per_week": 3, "required_equipment": ["dumbbell"]},
    {"template_id": "c", "level": "intermediate", "days_per_week": 3, "required_equipment": ["dumbbell"]},
    {"template_id": "d", "level": "beginner", "days_per_week": 4, "required_equipment": []},
]


def test_match_prefers_more_tailored_template():
    match = tpl_mod.match_template(SAMPLE_TEMPLATES, "beginner", {"dumbbell", "sled"}, 3)
    assert match["template_id"] == "b"


def test_match_falls_back_when_equipment_missing():
    match = tpl_mod.match_template(SAMPLE_TEMPLATES, "beginner", set(), 3)
    assert match["template_id"] == "a"


def test_match_respects_level_and_days():
    assert tpl_mod.match_template(SAMPLE_TEMPLATES, "advanced", {"dumbbell"}, 3) is None
    assert tpl_mod.match_template(SAMPLE_TEMPLATES, "beginner", {"dumbbell"}, 7) is None


def test_rank_candidates_returns_every_qualifying_template_best_first():
    ranked = tpl_mod.rank_candidates(SAMPLE_TEMPLATES, "beginner", {"dumbbell", "sled"}, 3)
    assert [t["template_id"] for t in ranked] == ["b", "a"]
    # A caller whose top pick turns out unbuildable has somewhere to fall.
    assert len(ranked) > 1


def test_rank_candidates_is_empty_rather_than_none_when_nothing_qualifies():
    assert tpl_mod.rank_candidates(SAMPLE_TEMPLATES, "advanced", {"dumbbell"}, 3) == []


def test_fits_time_budget_rejects_a_template_longer_than_the_users_session():
    forty = {"session_minutes": 40}
    assert tpl_mod.fits_time_budget(forty, 20) is False
    assert tpl_mod.fits_time_budget(forty, 40) is True
    assert tpl_mod.fits_time_budget(forty, 60) is True
    # Shorter than asked for is fine -- they have time to spare.
    assert tpl_mod.fits_time_budget({"session_minutes": 30}, 60) is True


def test_load_all_templates_reads_real_files():
    loaded = tpl_mod.load_all_templates()
    ids = {t["template_id"] for t in loaded}
    assert {"bodyweight_beginner_3day", "dumbbell_beginner_3day"}.issubset(ids)
    for t in loaded:
        assert t["progression_model"] in {"double-progression", "linear", "variation-ladder"}
