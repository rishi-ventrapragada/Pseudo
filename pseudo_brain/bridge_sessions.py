"""M41: the bridge's messages about saved chats. bridge.py stays the router, like bridge_voice.py.

Face -> brain:  list_sessions | search_sessions {text}        READS: answered at once, even mid-question
                rename_session {name, title}                  JOBS: refused as busy while any job runs,
                | delete_session {name}                       a question included
Brain -> face:  sessions {items}                              every saved chat, newest first
                found {text, items}                           the chats that match `text`, sent back as it
                                                              came, so the face can tell old replies apart
                renamed {name, title} | deleted {name, title} each job's LAST message: the face is free again
Deleting the open chat sends `session` (the new, empty one) first, then `sessions`, then `deleted`.

This file decides nothing: chat_sessions.py holds the rules, session_files.py the checks on the files.
"""

from pseudo_brain import chat_sessions
from pseudo_brain.session import list_sessions
from pseudo_brain.session_files import SessionRefused, search_sessions

READS = ("list_sessions", "search_sessions")
JOBS = ("rename_session", "delete_session")
SESSION_REFUSALS = (SessionRefused,)  # the job's handler reports these as `refused`, like the chat's REFUSALS


def read(bridge, message: dict) -> None:
    """A read: the whole list, or a search."""
    if message["type"] == "list_sessions":
        bridge.send("sessions", items=list_sessions())
    else:
        text = message.get("text") if isinstance(message.get("text"), str) else ""
        bridge.send("found", text=text, items=search_sessions(text))


async def job(bridge, kind: str, message: dict) -> None:
    """Rename or delete one saved chat. Raises SessionRefused, and then nothing was changed."""
    name = message.get("name")
    if kind == "rename_session":
        title = chat_sessions.rename(bridge.chat, name, message.get("title"))
        bridge.send("sessions", items=list_sessions())
        bridge.send("renamed", name=name, title=title)
    else:
        title, was_open = await chat_sessions.delete(bridge.chat, name)
        if was_open:
            bridge.send("session", **bridge.session_info())
        bridge.send("sessions", items=list_sessions())
        bridge.send("deleted", name=name, title=title)
