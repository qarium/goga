"""Hooks zone of the config domain — the amendment checkpoint surface.

The zone owns the read-and-amend view of the project-configuration load
moment (``ConfigAmendment`` with its buffered ``PathAmendment`` entries),
the deterministic in-memory amendment merge (``merge_config_amendments``
composing ``ToolAmendment`` contributions into a ``ConfigOverlay`` of
``AppliedAmendment`` records), and the ``ConfigHooks`` checkpoint surface
delivering the hard ``config/amend_config`` action over the platform
facade.

Built incrementally: this package scaffold precedes its modules; the zone
facade — the seven contract names in ``__all__`` — is assembled once every
module has landed.
"""
