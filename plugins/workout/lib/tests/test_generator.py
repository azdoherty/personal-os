import pytest

import model
import exercises as exercises_mod
import templates as templates_mod
import generator as gen_mod


SAMPLE_EXERCISES = [
    {"exercise_id": "box_squat", "name": "Box Squat", "movement_pattern": "squat",
     "equipment_required": [], "constraint_flags": [], "ladder_group": "squat_bw",
     "ladder_rank": 0, "default_reps": "10-15", "notes": ""},
    {"exercise_id": "bodyweight_squat", "name": "Bodyweight Squat", "movement_pattern": "squat",
     "equipment_required": [], "constraint_flags": [], "ladder_group": "squat_bw",
     "ladder_rank": 1, "default_reps": "12-15", "notes": ""},
    {"exercise_id": "incline_pushup", "name": "Incline Push-Up", "movement_pattern": "push",
     "equipment_required": [], "constraint_flags": ["arm-load"], "ladder_group": "push_bw",
     "ladder_rank": 0, "default_reps": "8-12", "notes": ""},
    {"exercise_id": "db_goblet_squat", "name": "DB Goblet Squat", "movement_pattern": "squat",
     "equipment_required": ["dumbbell"], "constraint_flags": ["grip"], "ladder_group": None,
     "ladder_rank": None, "default_reps": "8-12", "notes": ""},
]

SAMPLE_TEMPLATE = {
    "template_id": "sample", "level": "beginner", "goal": "general_strength",
    "days_per_week": 1, "session_minutes": 20, "required_equipment": [],
    "progression_model": "variation-ladder", "block_weeks": 4,
    "sessions": [
        {"day": 1, "label": "Full Body", "exercises": [
            {"ladder_group": "squat_bw", "sets": 3, "weeks_per_rung": 2, "tempo": "2-0-2",
             "rest": "60s", "notes": ""},
            {"ladder_group": "push_bw", "sets": 3, "weeks_per_rung": 2, "tempo": "2-0-2",
             "rest": "60s", "notes": ""},
        ]},
    ],
}


def test_build_program_from_template_produces_valid_program():
    program = gen_mod.build_program_from_template(
        SAMPLE_TEMPLATE, SAMPLE_EXERCISES, equipment_profile=[], constraints=[], created="2026-08-15"
    )
    assert model.validate_program(program) == []
    assert len(program.weeks) == 4
    assert program.weeks[0].sessions[0].exercises[0].exercise_id == "box_squat"
    assert program.weeks[2].sessions[0].exercises[0].exercise_id == "bodyweight_squat"


def test_template_rejected_when_a_session_would_be_left_empty():
    push_only = {**SAMPLE_TEMPLATE, "sessions": [
        {"day": 1, "label": "Push", "exercises": [SAMPLE_TEMPLATE["sessions"][0]["exercises"][1]]},
    ]}
    report = gen_mod.template_buildability(
        push_only, SAMPLE_EXERCISES, equipment_profile=["dumbbell"], constraints=["arm-load"])
    assert report["buildable"] is False
    assert "no exercises left" in report["reason"]


def test_template_buildable_when_no_constraint_flag_conflicts():
    report = gen_mod.template_buildability(
        SAMPLE_TEMPLATE, SAMPLE_EXERCISES, equipment_profile=[], constraints=["impact"])
    assert report["buildable"] is True


def test_unbuildable_ladder_slot_is_dropped_when_nothing_else_covers_the_pattern():
    report = gen_mod.template_buildability(
        SAMPLE_TEMPLATE, SAMPLE_EXERCISES, equipment_profile=[], constraints=["arm-load"]
    )
    assert report["buildable"] is True
    assert report["skipped_patterns"] == ["push"]

    program = gen_mod.build_program_from_template(
        SAMPLE_TEMPLATE, SAMPLE_EXERCISES, equipment_profile=[], constraints=["arm-load"],
        created="2026-08-15",
    )
    patterns = {ex.movement_pattern for w in program.weeks for s in w.sessions for ex in s.exercises}
    assert patterns == {"squat"}
    assert model.validate_program(program) == []


def test_template_rejected_when_the_user_owns_gear_the_template_cannot_use():
    # push_bw is unusable (arm-load), but the pool has an eligible push
    # option this template never mentions -- the generator serves them better.
    pool = SAMPLE_EXERCISES + [
        {"exercise_id": "vest_push", "name": "Vest Push", "movement_pattern": "push",
         "equipment_required": ["weighted_vest"], "constraint_flags": [], "ladder_group": None,
         "ladder_rank": None, "default_reps": "8-12", "notes": ""},
    ]
    report = gen_mod.template_buildability(
        SAMPLE_TEMPLATE, pool, equipment_profile=["weighted_vest"], constraints=["arm-load"]
    )
    assert report["buildable"] is False
    assert "push" in report["reason"]


def test_template_rejected_when_it_uses_none_of_the_equipment_the_user_owns():
    # SAMPLE_TEMPLATE is all-bodyweight ladders. A dumbbell owner's eligible
    # pool has a real squat option for the very slot it fills with box squats.
    report = gen_mod.template_buildability(
        SAMPLE_TEMPLATE, SAMPLE_EXERCISES, equipment_profile=["dumbbell"], constraints=[]
    )
    assert report["buildable"] is False
    assert "none of the equipment you own" in report["reason"]


def test_template_kept_when_it_uses_some_owned_gear_even_if_not_all_of_it():
    # A dumbbell template for a dumbbell+bench owner is still the right answer;
    # the rule fires on "uses nothing of yours", not "uses less than everything".
    db_template = {**SAMPLE_TEMPLATE, "sessions": [
        {"day": 1, "label": "Full Body", "exercises": [
            {"exercise_id": "db_goblet_squat", "sets": 3, "reps_low": 8, "reps_high": 12,
             "rep_step": 1, "load_value": 15.0, "load_increment": 5.0, "tempo": "2-0-2",
             "rest": "90s", "notes": ""},
        ]},
    ]}
    pool = SAMPLE_EXERCISES + [
        {"exercise_id": "db_bench_press", "name": "DB Bench Press", "movement_pattern": "squat",
         "equipment_required": ["dumbbell", "bench"], "constraint_flags": [], "ladder_group": None,
         "ladder_rank": None, "default_reps": "8-12", "notes": ""},
    ]
    report = gen_mod.template_buildability(
        db_template, pool, equipment_profile=["dumbbell", "bench"], constraints=[]
    )
    assert report["buildable"] is True


def test_zero_equipment_user_is_not_penalised_by_the_ignored_equipment_rule():
    report = gen_mod.template_buildability(
        SAMPLE_TEMPLATE, SAMPLE_EXERCISES, equipment_profile=[], constraints=[]
    )
    assert report["buildable"] is True


def test_a_minimum_length_session_still_spans_more_than_one_pattern_family():
    # Two slots is the floor. Truncating PATTERN_ORDER from the end must drop
    # the least essential work, not leave a lower-body-only session.
    exercises = exercises_mod.load_exercises()
    program = gen_mod.generate_program(
        exercises, equipment_profile=["dumbbell"], constraints=[], level="beginner",
        days_per_week=1, session_minutes=20, block_weeks=1, created="2026-08-15",
    )
    session = program.weeks[0].sessions[0]
    assert len(session.exercises) == 2
    patterns = {ex.movement_pattern for ex in session.exercises}
    assert len(patterns) == 2
    assert patterns != {"squat", "hinge"}, "a 2-slot session must not be lower-body only"


def test_pick_representative_prefers_the_option_that_uses_more_owned_equipment():
    pool = [
        {"exercise_id": "aaa_one_item", "name": "One", "movement_pattern": "push",
         "equipment_required": ["dumbbell"], "constraint_flags": [], "ladder_group": None,
         "ladder_rank": None, "default_reps": "8-12", "notes": ""},
        {"exercise_id": "zzz_two_items", "name": "Two", "movement_pattern": "push",
         "equipment_required": ["dumbbell", "bench"], "constraint_flags": [], "ladder_group": None,
         "ladder_rank": None, "default_reps": "8-12", "notes": ""},
    ]
    # Alphabetically "aaa_one_item" wins; the tie-break must override that.
    assert gen_mod._pick_representative(pool)["exercise_id"] == "zzz_two_items"


HETEROGENEOUS_LADDER = [
    {"exercise_id": "rung_free", "name": "Rung Free", "movement_pattern": "pull",
     "equipment_required": [], "constraint_flags": [], "ladder_group": "mixed",
     "ladder_rank": 0, "default_reps": "8-12", "notes": ""},
    {"exercise_id": "rung_bar", "name": "Rung Bar", "movement_pattern": "pull",
     "equipment_required": ["pull_up_bar"], "constraint_flags": [], "ladder_group": "mixed",
     "ladder_rank": 1, "default_reps": "6-10", "notes": ""},
    {"exercise_id": "rung_grippy", "name": "Rung Grippy", "movement_pattern": "pull",
     "equipment_required": [], "constraint_flags": ["grip"], "ladder_group": "mixed",
     "ladder_rank": 2, "default_reps": "6-8", "notes": ""},
]

MIXED_LADDER_TEMPLATE = {
    "template_id": "mixed", "level": "beginner", "goal": "general_strength",
    "days_per_week": 1, "session_minutes": 20, "required_equipment": [],
    "progression_model": "variation-ladder", "block_weeks": 6,
    "sessions": [
        {"day": 1, "label": "Pull", "exercises": [
            {"ladder_group": "mixed", "sets": 3, "weeks_per_rung": 2, "tempo": "2-0-2",
             "rest": "60s", "notes": ""},
        ]},
    ],
}


def test_ladder_rungs_needing_unowned_equipment_never_reach_the_program():
    program = gen_mod.build_program_from_template(
        MIXED_LADDER_TEMPLATE, HETEROGENEOUS_LADDER, equipment_profile=[], constraints=["grip"],
        created="2026-08-15",
    )
    ids = {ex.exercise_id for w in program.weeks for s in w.sessions for ex in s.exercises}
    assert ids == {"rung_free"}


def test_ladder_rungs_conflicting_with_constraints_never_reach_the_program():
    program = gen_mod.build_program_from_template(
        MIXED_LADDER_TEMPLATE, HETEROGENEOUS_LADDER, equipment_profile=["pull_up_bar"],
        constraints=["grip"], created="2026-08-15",
    )
    ids = {ex.exercise_id for w in program.weeks for s in w.sessions for ex in s.exercises}
    assert ids == {"rung_free", "rung_bar"}
    assert "rung_grippy" not in ids


def test_fully_ineligible_ladder_fails_compatibility_and_raises_rather_than_leaking_a_bad_rung():
    grip_only = [dict(r, constraint_flags=["grip"]) for r in HETEROGENEOUS_LADDER]
    assert gen_mod.template_buildability(
        MIXED_LADDER_TEMPLATE, grip_only, equipment_profile=["pull_up_bar"], constraints=["grip"]
    )["buildable"] is False
    with pytest.raises(gen_mod.LadderUnavailable):
        gen_mod._build_ladder_exercise(
            MIXED_LADDER_TEMPLATE["sessions"][0]["exercises"][0], grip_only, 4,
            equipment_profile=["pull_up_bar"], constraints=["grip"],
        )


def test_template_path_reports_the_templates_own_session_length():
    # The template's content is fixed, so its printed length has to be its
    # own -- there is no caller override to relabel it with.
    program = gen_mod.build_program_from_template(
        SAMPLE_TEMPLATE, SAMPLE_EXERCISES, equipment_profile=[], constraints=[],
        created="2026-08-15",
    )
    assert program.meta.session_minutes == SAMPLE_TEMPLATE["session_minutes"] == 20


def test_generated_session_size_scales_with_the_requested_minutes():
    exercises = exercises_mod.load_exercises()
    short = gen_mod.generate_program(
        exercises, equipment_profile=["dumbbell"], constraints=[], level="beginner",
        days_per_week=1, session_minutes=20, block_weeks=1, created="2026-08-15",
    )
    long = gen_mod.generate_program(
        exercises, equipment_profile=["dumbbell"], constraints=[], level="beginner",
        days_per_week=1, session_minutes=60, block_weeks=1, created="2026-08-15",
    )
    assert len(short.weeks[0].sessions[0].exercises) == 2
    assert len(long.weeks[0].sessions[0].exercises) > 2
    assert short.meta.session_minutes == 20


def test_generated_standalone_reps_come_from_the_exercise_db_not_a_hardcoded_default():
    exercises = exercises_mod.load_exercises()
    program = gen_mod.generate_program(
        exercises, equipment_profile=["sled"], constraints=["grip", "arm-load"], level="beginner",
        days_per_week=1, session_minutes=30, block_weeks=1, created="2026-08-15",
    )
    sled = next(
        ex for w in program.weeks for s in w.sessions for ex in s.exercises
        if ex.exercise_id == "sled_push"
    )
    # sled_push's default_reps is "3-5 trips" -- not 3 sets of 8.
    assert sled.reps == "3 trips"
    assert "5 trips" in sled.load.progression_rule


def test_zero_equipment_user_gets_a_real_program_from_the_curated_template():
    exercises = exercises_mod.load_exercises()
    template = next(
        t for t in templates_mod.load_all_templates() if t["template_id"] == "bodyweight_beginner_3day"
    )
    assert templates_mod.match_template([template], "beginner", [], 3) is template
    report = gen_mod.template_buildability(template, exercises, equipment_profile=[], constraints=[])
    assert report["buildable"] is True
    assert report["skipped_patterns"] == ["pull"]  # no table -> no bodyweight pull option

    program = gen_mod.build_program_from_template(
        template, exercises, equipment_profile=[], constraints=[], created="2026-08-15",
    )
    assert model.validate_program(program) == []
    assert all(s.exercises for w in program.weeks for s in w.sessions)


def test_generate_program_excludes_constrained_patterns():
    program = gen_mod.generate_program(
        SAMPLE_EXERCISES, equipment_profile=["dumbbell"], constraints=["arm-load"], level="beginner",
        days_per_week=1, session_minutes=30, block_weeks=2, created="2026-08-15",
    )
    all_ids = {ex.exercise_id for w in program.weeks for s in w.sessions for ex in s.exercises}
    assert "incline_pushup" not in all_ids
    assert model.validate_program(program) == []


def test_generate_program_picks_ladder_rank_zero_as_starting_point():
    program = gen_mod.generate_program(
        SAMPLE_EXERCISES, equipment_profile=[], constraints=[], level="beginner",
        days_per_week=1, session_minutes=30, block_weeks=1, created="2026-08-15",
    )
    squat_exercise = next(
        ex for w in program.weeks for s in w.sessions for ex in s.exercises
        if ex.movement_pattern == "squat"
    )
    assert squat_exercise.exercise_id == "box_squat"


def test_generate_program_leaves_generated_load_unset_for_user_to_fill_in():
    program = gen_mod.generate_program(
        SAMPLE_EXERCISES, equipment_profile=["dumbbell"], constraints=["arm-load", "impact"],
        level="beginner", days_per_week=1, session_minutes=30, block_weeks=1, created="2026-08-15",
    )
    loaded = [
        ex for w in program.weeks for s in w.sessions for ex in s.exercises if ex.load.type == "external"
    ]
    assert loaded and all(ex.load.value is None for ex in loaded)


def test_ladder_exercise_notes_update_as_the_program_climbs_rungs():
    ladder = [
        {"exercise_id": "box_squat", "name": "Box Squat", "movement_pattern": "squat",
         "equipment_required": [], "constraint_flags": [], "ladder_group": "squat_bw",
         "ladder_rank": 0, "default_reps": "10-15",
         "notes": "Sit back onto a chair or box, stand back up."},
        {"exercise_id": "bodyweight_squat", "name": "Bodyweight Squat", "movement_pattern": "squat",
         "equipment_required": [], "constraint_flags": [], "ladder_group": "squat_bw",
         "ladder_rank": 1, "default_reps": "12-15",
         "notes": "Feet shoulder-width, sit the hips back and down, chest tall."},
    ]
    entry = {"ladder_group": "squat_bw", "sets": 3, "weeks_per_rung": 1, "tempo": "2-0-2", "rest": "60s"}
    weeks = gen_mod._build_ladder_exercise(entry, ladder, 3, equipment_profile=[], constraints=[])
    assert weeks[0].notes == "Sit back onto a chair or box, stand back up."
    assert weeks[1].notes == "Feet shoulder-width, sit the hips back and down, chest tall."


def test_real_templates_load_and_build_valid_programs():
    exercises = exercises_mod.load_exercises()
    for template in templates_mod.load_all_templates():
        program = gen_mod.build_program_from_template(
            template, exercises, equipment_profile=template.get("required_equipment", []),
            constraints=[], created="2026-08-15",
        )
        errors = model.validate_program(program)
        assert errors == [], f"{template['template_id']}: {errors}"


FOCUS_EXERCISES = [
    {"exercise_id": "dead_bug", "name": "Dead Bug", "movement_pattern": "core",
     "sub_category": "anti_extension", "equipment_required": [], "constraint_flags": [],
     "ladder_group": "core_antiext_bw", "ladder_rank": 0, "default_reps": "10-12 / side", "notes": ""},
    {"exercise_id": "plank", "name": "Plank", "movement_pattern": "core",
     "sub_category": "anti_extension", "equipment_required": [], "constraint_flags": [],
     "ladder_group": "core_antiext_bw", "ladder_rank": 1, "default_reps": "30-45s", "notes": ""},
    {"exercise_id": "bird_dog", "name": "Bird Dog", "movement_pattern": "core",
     "sub_category": "anti_rotation", "equipment_required": [], "constraint_flags": [],
     "ladder_group": "core_antirot_bw", "ladder_rank": 0, "default_reps": "8-10 / side", "notes": ""},
    {"exercise_id": "curl_up", "name": "Curl-Up", "movement_pattern": "core",
     "sub_category": "flexion", "equipment_required": [], "constraint_flags": [],
     "ladder_group": "core_flexion_bw", "ladder_rank": 0, "default_reps": "10-12", "notes": ""},
    {"exercise_id": "knee_tuck_hold", "name": "Knee Tuck Hold", "movement_pattern": "core",
     "sub_category": "hip_flexor_endurance", "equipment_required": [], "constraint_flags": [],
     "ladder_group": "core_hipflexor_bw", "ladder_rank": 0, "default_reps": "15-20s", "notes": ""},
    {"exercise_id": "box_squat", "name": "Box Squat", "movement_pattern": "squat",
     "equipment_required": [], "constraint_flags": [], "ladder_group": "squat_bw",
     "ladder_rank": 0, "default_reps": "10-15", "notes": ""},
    {"exercise_id": "glute_bridge", "name": "Glute Bridge", "movement_pattern": "hinge",
     "equipment_required": [], "constraint_flags": [], "ladder_group": "hinge_bw",
     "ladder_rank": 0, "default_reps": "12-15", "notes": ""},
    {"exercise_id": "diamond_pushup", "name": "Diamond Push-Up", "movement_pattern": "push",
     "sub_category": "triceps", "equipment_required": [], "constraint_flags": ["arm-load"],
     "ladder_group": None, "ladder_rank": None, "default_reps": "6-10", "notes": ""},
    {"exercise_id": "table_inverted_row", "name": "Table Inverted Row", "movement_pattern": "pull",
     "sub_category": "biceps", "equipment_required": ["sturdy_table"], "constraint_flags": ["arm-load", "grip"],
     "ladder_group": None, "ladder_rank": None, "default_reps": "8-10", "notes": ""},
    {"exercise_id": "db_bent_over_row", "name": "DB Bent-Over Row", "movement_pattern": "pull",
     "equipment_required": ["dumbbell"], "constraint_flags": ["grip", "arm-load"],
     "ladder_group": None, "ladder_rank": None, "default_reps": "8-12", "notes": ""},
]


def test_focus_program_core_session_has_more_than_one_exercise():
    program = gen_mod.generate_focus_program(
        FOCUS_EXERCISES, focus_list=["core"], equipment_profile=[], constraints=[],
        level="beginner", days_per_week=3, session_minutes=30, block_weeks=4, created="2026-08-25",
    )
    session = program.weeks[0].sessions[0]
    ids = {ex.exercise_id for ex in session.exercises}
    # 30 min -> 4 slots, and core has exactly 4 sub-category buckets here, so
    # the fully-specified answer is all four. A subset check would let a
    # regression that caps focus sessions at 2 exercises pass unnoticed.
    assert ids == {"dead_bug", "bird_dog", "curl_up", "knee_tuck_hold"}
    assert model.validate_program(program) == []


def test_focus_slot_count_is_capped_by_the_buckets_actually_available():
    # Asserted on `_focus_slot_count` itself, NOT through
    # generate_focus_program: its caller slices `ordered_keys[:slot_count]`,
    # and slicing silently caps at the list's length, so a pipeline-level
    # test passes whether this cap exists, is broken, or is deleted.
    # 60 min alone wants 8 slots; with one bucket available the answer is 1.
    assert gen_mod._focus_slot_count(1, 60) == 1
    assert gen_mod._focus_slot_count(2, 60) == 2
    # The floor of 2 still applies when buckets are plentiful.
    assert gen_mod._focus_slot_count(6, 1) == 2
    # And the minutes-derived count wins when it is the smaller of the two.
    assert gen_mod._focus_slot_count(6, 30) == 4


def test_focus_program_short_session_still_caps_at_available_sub_categories():
    # 1 minute -> max(2, 0) = 2 wanted, but "legs" here only has squat+hinge
    # eligible (2 buckets) -- this must not somehow invent a 3rd exercise.
    assert gen_mod._focus_slot_count(2, 1) == 2
    program = gen_mod.generate_focus_program(
        FOCUS_EXERCISES, focus_list=["legs"], equipment_profile=[], constraints=[],
        level="beginner", days_per_week=1, session_minutes=1, block_weeks=1, created="2026-08-25",
    )
    assert len(program.weeks[0].sessions[0].exercises) == 2


def test_focus_program_leg_day_never_drops_the_squat_before_the_carry():
    # All three "legs" buckets are pattern-fallbacks (no leg exercise carries
    # a sub_category), so their internal order is PATTERN_ORDER's, not
    # alphabetical: alphabetical made a short leg day open with a loaded
    # carry and drop the squat entirely.
    exercises = exercises_mod.load_exercises()
    two_slots = gen_mod._pick_focus_exercises(
        exercises, "legs", ["dumbbell"], [], session_minutes=20)
    assert [e["exercise_id"] for e in two_slots] == ["db_goblet_squat", "db_romanian_deadlift"]

    one_slot = gen_mod._pick_focus_exercises(
        exercises, "legs", ["dumbbell"], [], session_minutes=20)[:1]
    assert one_slot[0]["movement_pattern"] == "squat"

    # And the carry is still reachable once the session is long enough.
    full = gen_mod._pick_focus_exercises(
        exercises, "legs", ["dumbbell"], [], session_minutes=60)
    assert [e["movement_pattern"] for e in full] == ["squat", "hinge", "carry"]


def test_focus_vocabulary_has_a_single_effective_source_of_truth():
    # validate_focus checks against model.FOCUS_AREAS while the generator
    # indexes generator.FOCUS_PATTERNS -- a token in one but not the other
    # is a KeyError instead of a clean "unknown focus area" error.
    assert set(model.FOCUS_AREAS) == set(gen_mod.FOCUS_PATTERNS)


def test_focus_program_prefers_named_sub_categories_before_generic_pattern_fallback():
    # arms: "triceps" and "biceps" are named sub-categories; the generic
    # "pull" bucket (db_bent_over_row) is a pattern-fallback and must lose
    # the slot when only 2 fit.
    program = gen_mod.generate_focus_program(
        FOCUS_EXERCISES, focus_list=["arms"], equipment_profile=["sturdy_table", "dumbbell"],
        constraints=[], level="beginner", days_per_week=1, session_minutes=14, block_weeks=1,
        created="2026-08-25",
    )
    ids = {ex.exercise_id for ex in program.weeks[0].sessions[0].exercises}
    assert ids == {"diamond_pushup", "table_inverted_row"}


def test_focus_program_cycles_multiple_focuses_across_days():
    program = gen_mod.generate_focus_program(
        FOCUS_EXERCISES, focus_list=["core", "legs"], equipment_profile=[], constraints=[],
        level="beginner", days_per_week=4, session_minutes=30, block_weeks=1, created="2026-08-25",
    )
    labels = [s.label for s in program.weeks[0].sessions]
    assert labels == ["Core", "Legs", "Core", "Legs"]


def test_focus_program_zero_equipment_arms_is_triceps_only():
    # 30 min asks for 4 slots; this fixture leaves exactly 1 eligible bucket
    # for a zero-equipment arm day, and the slot count must say 1, not 4 --
    # asserted on the function, since the caller's slice hides the difference.
    assert gen_mod._focus_slot_count(1, 30) == 1
    program = gen_mod.generate_focus_program(
        FOCUS_EXERCISES, focus_list=["arms"], equipment_profile=[], constraints=[],
        level="beginner", days_per_week=1, session_minutes=30, block_weeks=1, created="2026-08-25",
    )
    ids = {ex.exercise_id for ex in program.weeks[0].sessions[0].exercises}
    assert ids == {"diamond_pushup"}  # table_inverted_row needs sturdy_table, unowned


def test_real_db_zero_equipment_arm_day_is_one_triceps_pick_plus_a_push_fallback():
    # What SKILL.md promises the user. Against the real DB (not the trimmed
    # fixture above) a zero-equipment arm day is exactly two exercises: the
    # triceps bucket's pick, plus the generic "push" pattern-fallback bucket
    # -- there is no bodyweight biceps bucket without a table. `--minutes`
    # stops mattering once past 2 slots' worth.
    exercises = exercises_mod.load_exercises()
    for minutes in (7, 14, 20, 30, 60):
        ids = [e["exercise_id"] for e in gen_mod._pick_focus_exercises(
            exercises, "arms", [], [], session_minutes=minutes)]
        assert ids == ["diamond_pushup", "incline_pushup"], minutes


def test_focus_program_meta_reflects_the_split():
    program = gen_mod.generate_focus_program(
        FOCUS_EXERCISES, focus_list=["core", "arms"], equipment_profile=[], constraints=[],
        level="beginner", days_per_week=2, session_minutes=30, block_weeks=1, created="2026-08-25",
    )
    assert program.meta.source == "generated-focus"
    assert program.meta.goal == "split: core, arms"


def test_focus_program_ladder_exercise_still_progresses_across_the_block():
    program = gen_mod.generate_focus_program(
        FOCUS_EXERCISES, focus_list=["core"], equipment_profile=[], constraints=[],
        level="beginner", days_per_week=1, session_minutes=8, block_weeks=3, created="2026-08-25",
    )
    # session_minutes=8 -> max(2, 8//7=1) = 2 slots, only anti_extension's
    # ladder is guaranteed to be selected first (alphabetically named).
    week1_ex = next(
        ex for ex in program.weeks[0].sessions[0].exercises
        if ex.movement_pattern == "core" and ex.exercise_id in {"dead_bug", "plank"}
    )
    week3_ex = next(
        ex for ex in program.weeks[2].sessions[0].exercises
        if ex.movement_pattern == "core" and ex.exercise_id in {"dead_bug", "plank"}
    )
    assert week1_ex.exercise_id == "dead_bug"
    assert week3_ex.exercise_id == "plank"


def test_real_exercise_db_builds_a_valid_focus_program_for_every_area():
    exercises = exercises_mod.load_exercises()
    for focus in model.FOCUS_AREAS:
        program = gen_mod.generate_focus_program(
            exercises, focus_list=[focus], equipment_profile=[], constraints=[], level="beginner",
            days_per_week=1, session_minutes=30, block_weeks=2, created="2026-08-25",
        )
        assert model.validate_program(program) == [], focus
        assert program.weeks[0].sessions[0].exercises, focus


def test_full_body_generator_still_produces_a_valid_core_pick_after_the_ladder_split():
    # Regression guard for the core_bw -> 4-group split (see the design
    # spec's "regression risk" section): full-body generation must still
    # deterministically pick exactly one valid core exercise, even though
    # the specific winner changes now that there are 4 rank-0 candidates.
    exercises = exercises_mod.load_exercises()
    program = gen_mod.generate_program(
        exercises, equipment_profile=[], constraints=[], level="beginner",
        days_per_week=1, session_minutes=60, block_weeks=1, created="2026-08-25",
    )
    core_exercises = [
        ex for w in program.weeks for s in w.sessions for ex in s.exercises
        if ex.movement_pattern == "core"
    ]
    assert len(core_exercises) == 1
    assert model.validate_program(program) == []
