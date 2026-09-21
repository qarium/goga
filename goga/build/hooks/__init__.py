"""Hooks zone of the build domain — the checkpoint surface of build runs.

The zone owns the fact vocabulary of the run events (work identity, moment,
stage facts), the read-only contexts of the five moments, the
verdict-collecting gate view, and the ``BuildHooks`` checkpoint surface
delivering the domain's hard gate ``build/validate_build`` and the four soft
notifications ``build/build_started`` / ``build/pass_started`` /
``build/pass_completed`` / ``build/build_completed`` over the platform
facade. The gate follows the staged per-tool walk of the platform with one
domain-local deviation: the walk never stops early — every subscribed tool's
validation hooks run to completion and the vetoes are collected into one
verdict.

Built incrementally: each entity task adds its module's import and
``__all__`` entry.
"""

from __future__ import annotations

__all__: list[str] = []
