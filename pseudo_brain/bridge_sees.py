"""M42: the bridge's messages for what Pseudo SEES: the look-at chip and the memory browser.

Face -> brain:  look | list_memories | open_memory {name}        IDLE READS: answered at once, only while no job runs
Brain -> face:  looking_at {app, private, note}                  the app a question would read now
                memory_list {items, note}                        your saved memories, newest first, redacted again
                memory_note {name, date, title, question, answer, note}    one memory, read-only, redacted again

Why "idle": each one calls a brain-only tool in pseudo_hands (D29). While a question runs, pseudo_hands
may be showing an approval popup, and a call then would wait behind it. So while a job runs, `look` is
skipped (each question sends a fresh one before it starts, bridge.py) and the other two are refused as
busy. None of them sends a tool_call event: they show no popup, so the face gives no foreground
permission and the compact bar keeps always-on-top (D29).
This file decides nothing: the rules for the vault and the window live in pseudo_hands' core.
"""

import anyio

IDLE_READS = ("look", "list_memories", "open_memory")
TIME_LIMIT_SECONDS = 20.0  # the first call may load the redactor (seconds); a stuck one mustn't hold the bridge
ITEM_FIELDS = ("name", "date", "title")
NOTE_FIELDS = ("name", "date", "title", "question", "answer", "note")


async def call(bridge, tool: str, arguments: dict) -> dict:
    """A brain-only tool's result; {} if it failed or took too long."""
    with anyio.move_on_after(TIME_LIMIT_SECONDS):
        return await bridge.hands.brain_call(tool, arguments) or {}
    return {}


async def look(bridge) -> None:
    """Tell the face which app a question would read now (the chip)."""
    found = await call(bridge, "looking_at", {})
    bridge.send("looking_at", app=str(found.get("app", "")), private=found.get("private") is True,
                note=str(found.get("note", "")) if found else "the look-at tool failed")


async def read(bridge, message: dict, busy: str) -> None:
    """One idle read. `busy` is the bridge's busy reason, for the two that are refused while a job runs."""
    kind = message["type"]
    if bridge.busy:
        if kind != "look":
            bridge.send("refused", reason=busy)
        return
    if kind == "look":
        await look(bridge)
    elif kind == "list_memories":
        found = await call(bridge, "list_memories", {})
        items = [{key: str(item.get(key, "")) for key in ITEM_FIELDS}
                 for item in found.get("items", []) if isinstance(item, dict)]
        bridge.send("memory_list", items=items, note=str(found.get("note", "")) if found else "the memory list failed")
    else:
        name = message.get("name") if isinstance(message.get("name"), str) else ""
        found = await call(bridge, "open_memory", {"name": name}) or {"note": "that memory can't be opened"}
        bridge.send("memory_note", **{key: str(found.get(key, "")) for key in NOTE_FIELDS})
