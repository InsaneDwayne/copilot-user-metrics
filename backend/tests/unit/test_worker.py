"""The worker's composition root: built from settings, nothing done at import time."""

import importlib

from copilot_metrics.settings import GitHubSettings, Settings, WorkerSettings
from copilot_metrics.sync.domain import SYNC_TASKS


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        github=GitHubSettings(org="acme-labs"),
        worker=WorkerSettings.model_validate({"database_url": "postgresql://worker:worker@db/metrics"}),
    )


def test_importing_the_worker_needs_no_environment() -> None:
    importlib.reload(importlib.import_module("copilot_metrics.worker"))


def test_every_task_the_sync_page_controls_is_registered() -> None:
    from copilot_metrics.worker import create_worker

    app = create_worker(_settings()).app

    expected = {task for tasks in SYNC_TASKS.values() for task in tasks}
    assert expected <= set(app.tasks)
    assert {"recover_stalled_jobs", "prune_history"} <= set(app.tasks)
    assert all(app.tasks[name].queue == "sync" for name in expected)
