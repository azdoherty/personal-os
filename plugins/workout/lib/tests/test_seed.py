import store
import seed


def test_seed_exercises_populates_table_from_real_references():
    conn = store.connect(":memory:")
    count = seed.seed_exercises(conn)
    rows = conn.execute("SELECT COUNT(*) FROM exercises").fetchone()[0]
    assert count == rows
    assert count >= 20


def test_seed_equipment_catalog_populates_table():
    conn = store.connect(":memory:")
    count = seed.seed_equipment_catalog(conn)
    rows = conn.execute("SELECT COUNT(*) FROM equipment_catalog").fetchone()[0]
    assert count == rows
    assert count >= 5


def test_parse_sources_md_extracts_fields():
    text = (
        "## example_source\n"
        "- title: Example Title\n"
        "- author_org: Example Org\n"
        "- url: https://example.com/paper\n"
        "- topic_tags: a, b\n"
        "- trust_tier: high\n"
        "- informs: some.py\n"
    )
    entries = seed.parse_sources_md(text)
    assert len(entries) == 1
    entry = entries[0]
    assert entry["source_id"] == "example_source"
    assert entry["title"] == "Example Title"
    assert entry["topic_tags"] == ["a", "b"]


def test_parse_sources_md_handles_multiple_entries():
    text = (
        "## first\n- title: First\n- author_org: Org\n- url: https://a.example\n"
        "- topic_tags: x\n- trust_tier: high\n- informs: a\n"
        "\n## second\n- title: Second\n- author_org: Org\n- url: https://b.example\n"
        "- topic_tags: y\n- trust_tier: medium\n- informs: b\n"
    )
    entries = seed.parse_sources_md(text)
    assert [e["source_id"] for e in entries] == ["first", "second"]


def test_seed_sources_populates_table_from_real_references():
    conn = store.connect(":memory:")
    count = seed.seed_sources(conn)
    rows = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
    assert count == rows
    assert count >= 5


def test_seed_all_seeds_every_table():
    conn = store.connect(":memory:")
    counts = seed.seed_all(conn)
    assert set(counts) == {"exercises", "equipment_catalog", "sources"}
    assert all(v > 0 for v in counts.values())
