# plugins/user_states.py
# Shared conversation-state registry.
# Used to temporarily block auto_filter when another module
# is waiting for the user's next message.
#
# State values:
#   "actor_search"  — actor/director module waiting for a name
#   None            — no active state (normal auto_filter)

from typing import Optional

# user_id (int) → state string
USER_STATES: dict[int, Optional[str]] = {}


def set_state(user_id: int, state: str):
    USER_STATES[user_id] = state


def clear_state(user_id: int):
    USER_STATES.pop(user_id, None)


def get_state(user_id: int) -> Optional[str]:
    return USER_STATES.get(user_id)
