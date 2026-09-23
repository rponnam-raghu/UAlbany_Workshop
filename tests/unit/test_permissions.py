from academic_advisor.tools.handlers import build_registry


def test_active_registry_contains_only_read_only_date_tool():
    registry = build_registry()
    assert [tool["name"] for tool in registry.schemas()] == ["days_until"]
    assert all(not tool.writes for tool in registry.tools.values())


def test_unknown_or_write_like_request_is_rejected():
    registry = build_registry()
    assert registry.dispatch("mark_complete", {"course": "CSI 201"})["status"] == "error"
    assert registry.dispatch("days_until", {"date_str": "2026-12-01"})["status"] == "ok"
