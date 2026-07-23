"""Persistence layer. SQLite today; isolated behind session.py so the
engine can be swapped later without touching domain models or callers
(see ARCHITECTURE.md Section 20)."""
