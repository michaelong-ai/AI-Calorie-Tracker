"""Who is making this request? (The authentication "empty slot".)

v1 is single-user by design, but every table and every query is written
multi-user (ARCHITECTURE.md). This module is the one place that decides the
current user. Today it returns the seeded user's id unconditionally; when
real accounts arrive (v2), THIS function starts reading a session token
instead — and no other file needs to change. That's the whole trick.
"""

# The id of the user seeded by migration 001. SQLite assigns the first
# inserted row id=1.
SEEDED_USER_ID = 1


def get_current_user_id() -> int:
    """Return the id of the user making the current request.

    Takes no input today; later this will accept/inspect request
    credentials. Every endpoint that touches user data calls this instead
    of hard-coding an id.
    """
    return SEEDED_USER_ID
