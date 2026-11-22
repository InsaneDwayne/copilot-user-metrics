"""Copilot usage dashboard: a modular monolith.

Modules (each laid out hexagonally: ``domain`` -> ``ports`` -> ``service`` -> ``adapters``):

- ``identity`` - GitHub sign-in, sessions and who may see what.
- ``usage``    - read side: a person's own credits, models, activity; admin views.
- ``sync``     - write side: the worker that pulls from GitHub as the org's App.
- ``shared``   - the small kernel they share (settings-free building blocks, tables).

Entry points: ``copilot_metrics.api:create_app`` (FastAPI app factory) and ``copilot_metrics.worker:create_worker``
(worker factory; ``copilot_metrics.worker.app`` for procrastinate's CLI).
"""
