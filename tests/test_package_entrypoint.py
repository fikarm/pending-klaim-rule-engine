import pending_klaim_rule_engine


def test_main_starts_structured_review_cli(monkeypatch):
    called = False

    def run_cli():
        nonlocal called
        called = True

    monkeypatch.setattr(pending_klaim_rule_engine, "run_review_cli", run_cli)

    pending_klaim_rule_engine.main()

    assert called