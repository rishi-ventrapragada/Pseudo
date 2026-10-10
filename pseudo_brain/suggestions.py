"""M40: the questions an empty chat offers, one click each (from the Phase 10 mockup).

They live in the brain, not the page (D11): the brain knows which questions are safe to offer. Each one
only READS: none is an action request (it would go to Claude Code and could open an action popup), and
none asks to see or switch to a window (the switch tool would be offered). tests/test_brain_suggestions.py
runs every one through routing.py's own rules to keep it that way.
"""

SUGGESTIONS = (
    "What's on my screen?",
    "Summarise the window I was on",
    "Which buttons are on this window?",  # the mockup said "can you press": that invites the model to press one
    "What did I work on yesterday?",  # answered from memory, when there is some
)
