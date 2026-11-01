from types import SimpleNamespace

import pytest

from app.infra import error_reporting


class _Calls:
    def __init__(self) -> None:
        self.init: list = []
        self.reported: list = []


@pytest.fixture
def calls(monkeypatch):
    recorder = _Calls()
    monkeypatch.setattr(
        error_reporting.rollbar,
        "init",
        lambda token, environment: recorder.init.append((token, environment)),
    )
    monkeypatch.setattr(
        error_reporting.rollbar,
        "report_exc_info",
        lambda exc_info, extra_data: recorder.reported.append((exc_info, extra_data)),
    )
    return recorder


def _settings(monkeypatch, environment: str) -> None:
    settings = SimpleNamespace(
        environment=environment,
        is_production=environment == "production",
        rollbar_access_token="token",
    )
    monkeypatch.setattr(error_reporting, "get_settings", lambda: settings)


def test_task_failure_is_reported_in_production(monkeypatch, calls):
    _settings(monkeypatch, "production")
    error = RuntimeError("boom")
    traceback = object()

    error_reporting.report_task_failure(
        sender=SimpleNamespace(name="app.tasks.example"),
        exception=error,
        traceback=traceback,
    )

    assert calls.reported == [
        (
            (RuntimeError, error, traceback),
            {"task": "app.tasks.example"},
        )
    ]


@pytest.mark.parametrize("environment", ["development", "test"])
def test_task_failure_is_not_reported_outside_production(
    monkeypatch, calls, environment
):
    _settings(monkeypatch, environment)

    error_reporting.report_task_failure(
        sender=SimpleNamespace(name="app.tasks.example"),
        exception=RuntimeError("boom"),
        traceback=None,
    )

    assert calls.reported == []


def test_task_failure_without_exception_is_skipped(monkeypatch, calls):
    _settings(monkeypatch, "production")

    error_reporting.report_task_failure(sender=None, exception=None, traceback=None)

    assert calls.reported == []


def test_worker_process_initializes_rollbar_in_production(monkeypatch, calls):
    _settings(monkeypatch, "production")

    error_reporting.init_rollbar_for_worker()

    assert calls.init == [("token", "production")]


def test_worker_process_skips_rollbar_outside_production(monkeypatch, calls):
    _settings(monkeypatch, "development")

    error_reporting.init_rollbar_for_worker()

    assert calls.init == []
