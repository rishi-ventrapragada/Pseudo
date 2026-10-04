"""M29: the questions for measuring how often a brain turns an action request into a usable popup.
Not a test file itself.

Everything here is FAKE, and was committed BEFORE any measurement. The criteria were fixed in the M29 plan
(PRD section 14) and are copied into CRITERIA below; nothing is tuned.
  F1   Pseudo's test form (tests/fixtures/m27_form.ps1)
  F2   the M27 fake page (tests/fixtures/m27_page.html), in Brave with a temporary profile
  F5   the M29 fake order page (tests/fixtures/m29_page.html); its text fields start filled. H5, H9 and H10
       were reworded before any measurement, when F5's "Gift" labels were renamed (the redactor masked "Gift")
  LIVE_B     M28 Live B's 6 questions, word for word. SPENT: two tool descriptions were tuned on them.
             Asked LIVE_B_REPEATS times (n = 0, 1). Reported, never used to decide.
  HELD_OUT   18 new action questions, 3 per action type. These decide (U1-U3, W1).
  SWITCH     4 questions that ask to see or switch to a window: a focus popup for `focus`, no action popup.
  READ_ONLY  2 questions that ask nothing to be done: no popup at all.
  offers_focus()  candidate 1, the rule: offer focus_window only when the message asks to see or switch.
An expected popup is the control's type and name as Windows reports them, the action, and the exact text.
"""

import re

ACTION_TYPES = ("press", "set_text", "insert_text", "toggle", "select", "choose")
FIXTURES = {"F1": "tests/fixtures/m27_form.ps1", "F2": "tests/fixtures/m27_page.html",
            "F5": "tests/fixtures/m29_page.html"}

LIVE_B_REPEATS = 2
LIVE_B_ROOMS = ["Room 305", "Room 204"]  # room = LIVE_B_ROOMS[n % 2], as in M28's harness
LIVE_B = [
    {"id": "B-press", "window": "F2", "type": "Hyperlink", "name": "Go to section 2", "action": "press",
     "ask": "Click the 'Go to section 2' link on this page.", "text": ""},
    {"id": "B-set_text", "window": "F1", "type": "Edit", "name": "Subject", "action": "set_text",
     "ask": "Type 'Fake subject {n}' into the Subject field.", "text": "Fake subject {n}"},
    {"id": "B-insert_text", "window": "F1", "type": "Edit", "name": "Notes", "action": "insert_text",
     "ask": "Add the words 'fake note {n}' at the end of the Notes field, keeping what is there.",
     "text": "fake note {n}"},
    {"id": "B-toggle", "window": "F1", "type": "CheckBox", "name": "Send me reminders", "action": "toggle",
     "ask": "Tick the 'Send me reminders' box.", "text": ""},
    {"id": "B-select", "window": "F1", "type": "RadioButton", "name": "Priority high", "action": "select",
     "ask": "Select the 'Priority high' option.", "text": ""},
    {"id": "B-choose", "window": "F2", "type": "ComboBox", "name": "Room", "action": "choose",
     "ask": "Choose '{room}' in the Room dropdown.", "text": "{room}"},
]


def live_b_questions() -> list[dict]:
    """The 12 Live B questions: each of the 6 asked with n = 0 and 1, filled in as M28's harness did."""
    asked = []
    for n in range(LIVE_B_REPEATS):
        room = LIVE_B_ROOMS[n % len(LIVE_B_ROOMS)]
        for case in LIVE_B:
            filled = {key: value.format(n=n, room=room) if isinstance(value, str) else value
                      for key, value in case.items()}
            asked.append({**filled, "id": f"{case['id']}-{n}"})
    return asked


def held(id_: str, window: str, kind: str, name: str, action: str, ask: str, text: str = "") -> dict:
    return {"id": id_, "window": window, "type": kind, "name": name, "action": action, "ask": ask, "text": text}


HELD_OUT = [
    held("H1", "F5", "Button", "Apply coupon", "press", "Hit the Apply coupon button."),
    held("H2", "F5", "Hyperlink", "Show delivery options", "press",
         "Can you open the 'Show delivery options' link for me?"),
    held("H3", "F5", "Button", "Reset choices", "press", "Undo my choices with the Reset choices button."),
    held("H4", "F5", "Edit", "Coupon code", "set_text",
         "Put 'SAVE10' in the coupon code box instead of what's there.", "SAVE10"),
    held("H5", "F5", "Edit", "Card message", "set_text",
         "Change the card message to 'Congratulations on the new job'.", "Congratulations on the new job"),
    held("H6", "F5", "Edit", "Coupon code", "set_text", "Replace the coupon code with 'WELCOME5'.", "WELCOME5"),
    held("H7", "F5", "Edit", "Delivery instructions", "insert_text",
         "Add 'Ring the bell twice.' to the end of the delivery instructions.", "Ring the bell twice."),
    held("H8", "F5", "Edit", "Delivery instructions", "insert_text",
         "Append 'Call before coming' to the delivery instructions, keeping what's there.", "Call before coming"),
    held("H9", "F5", "Edit", "Card message", "insert_text",
         "In the card message, add 'From all of us' after the current text.", "From all of us"),
    held("H10", "F5", "CheckBox", "Present wrapping", "toggle", "Turn on present wrapping."),
    held("H11", "F1", "CheckBox", "Send me reminders", "toggle", "Check the reminders box on the form."),
    held("H12", "F5", "CheckBox", "Text me updates", "toggle", "In the order page window, tick 'Text me updates'."),
    held("H13", "F5", "RadioButton", "Pay now", "select", "Switch the payment to Pay now."),
    held("H14", "F1", "RadioButton", "Priority high", "select", "Make the priority high."),
    held("H15", "F5", "RadioButton", "Pay by card", "select", "Pick 'Pay by card' as the payment option."),
    held("H16", "F5", "ComboBox", "Shipping speed", "choose", "Set the shipping speed to Express.", "Express"),
    held("H17", "F2", "ComboBox", "Room", "choose", "Change the room on the page to Room 204.", "Room 204"),
    held("H18", "F5", "ComboBox", "Shipping speed", "choose",
         "I need it faster: pick Overnight in the shipping dropdown.", "Overnight"),
]

SWITCH = [  # window = right behind Pseudo; behind = the next one back; focus = the window that should come forward
    {"id": "H19", "window": "F1", "behind": "F5", "focus": "F5", "ask": "Switch to the fake order page."},
    {"id": "H20", "window": "F5", "behind": "F1", "focus": "F1", "ask": "Bring the test form window to the front."},
    {"id": "H21", "window": "F1", "behind": "F2", "focus": "F2", "ask": "Show me the M27 fake page window."},
    {"id": "H22", "window": "F5", "behind": "F1", "focus": "F1", "ask": "Can I see the test form?"},
]
READ_ONLY = [
    {"id": "H23", "window": "F5", "ask": "What does the status line on this page say?"},
    {"id": "H24", "window": "F5", "ask": "Which shipping speeds can I pick from?"},
]

M15_QUESTIONS = {  # the M15 battery, word for word: only T4 asks to switch (R1)
    "T1": "What does my active window say?",
    "T2": "What does my active window say?",
    "T3": "Which windows are open right now?",
    "T4": "Bring the window called Pseudo M15 target to the front.",
    "T5": "Who is the meeting in my active window with?",
    "T6": "What is 17 times 3?",
}

# Candidate 1, the rule. Fixed in the M29 plan before measuring. Core never sees the user's message,
# so a brain would apply this to each question before choosing which tools to offer.
SWITCH_PHRASES = ("switch to", "switch back", "switch over", "bring up", "to the front", "in front",
                  "on top", "focus", "jump to", "take me to", "go back to", "alt tab", "alt-tab")
SEE_A_WINDOW = re.compile(r"\b(show|see|open|go to)\b.*\bwindow\b")


def offers_focus(message: str) -> bool:
    """True if this message asks to see or switch to a window, so focus_window should be offered."""
    text = message.lower()
    return any(phrase in text for phrase in SWITCH_PHRASES) or bool(SEE_A_WINDOW.search(text))


CRITERIA = {  # copied from the M29 plan; fixed before measuring. Judged on the held-out set.
    "R1_switch_offered_min_of_5": 4, "R1_action_withheld_min_of_24": 23, "R1_others_withheld_min_of_7": 7,
    "U1_usable_min_of_18": 16, "U2_per_type_min_of_3": 2, "U3_focus_popups_max_of_18": 1,
    "W1_wrong_popups_max_of_30": 1, "N1_action_popups_on_others_max": 0, "F1_switch_right_min_of_4": 3,
    "S1_median_seconds_to_popup_max": 15.0, "T1_groq_tokens_per_question_max": 8000,
    "B1_claude_billing_clean_min": 1.0, "groq_tokens_per_model_per_day_stop": 190_000,
}
