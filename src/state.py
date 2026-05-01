"""
In-memory state shared across handlers and scheduler.
Reset on bot restart — anything that must survive restarts goes in the DB.
"""

allowed_users: set[int] = set()

active_draft_sessions: dict[int, dict] = {}
