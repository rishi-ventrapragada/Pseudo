"""M30: which brain gets a message, and whether the window-switching tool is offered. No model is involved.

What it demonstrates: ROUTING by rule. pseudo_hands' core never sees your message, only tool
calls, so anything decided from your words has to be decided here, in the brain. Two rules:

  offers_focus(message)       M29's rule, word for word (it was measured there, so it must not
                              change): the window-switching tool is offered only when you ask to see
                              or switch to a window. Without the rule, gpt-oss-120b asked for a
                              pointless switch popup on 20 of 30 action requests. This file doesn't
                              name the tool (the brain names no tools); providers.toml does.
  is_action_request(message)  M30's rule, fixed in the M30 plan: a request to act on a window
                              (click, type, tick, choose...) goes to Claude Code (D26); everything
                              else stays on Groq.

Both are plain word lists on purpose: you can read exactly why a message went where it did.
A miss is safe: the message stays on Groq, which is how Pseudo behaved before M30. A false hit
costs subscription quota, but nothing can act without your approval popup (D13).
"""

import re

# --- M29's rule (moved here from tests/brain_action_cases.py; tests pin it unchanged) ---
SWITCH_PHRASES = ("switch to", "switch back", "switch over", "bring up", "to the front", "in front",
                  "on top", "focus", "jump to", "take me to", "go back to", "alt tab", "alt-tab")
SEE_A_WINDOW = re.compile(r"\b(show|see|open|go to)\b.*\bwindow\b")


def offers_focus(message: str) -> bool:
    """True if this message asks to see or switch to a window, so the switching tool should be offered."""
    text = message.lower()
    return any(phrase in text for phrase in SWITCH_PHRASES) or bool(SEE_A_WINDOW.search(text))


# --- M30's rule ---
ACTION_WORDS = ("click", "press", "hit", "tap", "tick", "untick", "check", "uncheck", "toggle", "turn on",
                "turn off", "select", "choose", "pick", "set", "type", "enter", "put", "fill", "add", "append",
                "replace", "change", "switch the", "make", "open the", "undo", "clear")
ACTION_WORD = re.compile(r"\b(" + "|".join(re.escape(word) for word in ACTION_WORDS) + r")\b")  # whole words only
# A plain question asks about the screen; it doesn't ask for anything to be done.
# "Can you ...", "Could you ..." and "Please ..." aren't in this list: they are requests.
QUESTION_START = re.compile(r"(what|which|who|whom|when|where|why|how|is|are|was|does|do|did)\b")


def is_action_request(message: str) -> bool:
    """True if this message asks Pseudo to act on a window (so it goes to Claude Code, D26)."""
    text = message.lower().strip()
    if QUESTION_START.match(text):
        return False
    found = set(ACTION_WORD.findall(text))
    if SEE_A_WINDOW.search(text):  # "open the calculator window" is a switch, not an action
        found.discard("open the")
    return bool(found)
