"""M41: what renaming or deleting a saved chat means for the conversation that is open.

What it demonstrates: a change to a FILE that has consequences elsewhere. session_files.py changes
the file and decides nothing else. These two rules keep the open conversation true to it, and, like
chat.py's, they hold for every interface (D11):
  - Renaming the open chat renames its Session too. Otherwise the next save, after every question,
    would write the old title back.
  - Deleting a chat that a warm Claude Code session serves stops that session, as a provider switch
    does (M32): it still holds that chat's requests. Deleting the OPEN chat then starts a new one,
    on the same provider.
"""

from pseudo_brain.chat import Chat
from pseudo_brain.session_files import delete_session, rename_session


def rename(chat: Chat, name: object, title: object) -> str:
    """Rename a saved chat, and the open one's Session with it. Returns the new title. Raises SessionRefused."""
    clean = rename_session(name, title)
    if chat.session.started == name:
        chat.session.title = clean
    return clean


async def delete(chat: Chat, name: object) -> tuple[str, bool]:
    """Delete a saved chat. Returns its title and whether it was the open one. Raises SessionRefused."""
    title = delete_session(name)
    if chat.warm is not None and chat.warm.conversation == name:
        await chat.warm.end("its chat was deleted")
    was_open = chat.session.started == name
    if was_open:
        chat.new_session()
    return title, was_open
