"""M31: the questions for measuring a WARM Claude Code session that is restarted every 6 requests.
Not a test file itself.

What it demonstrates: a held-out set. M30 kept one Claude Code session open for M29's 18 questions and
saw its input grow with every request; the number 6 (restart before the input passes 3 times the first
request's) was read off THOSE questions. A number chosen on a set can't be checked on the same set, so
these 18 are new, and they were committed BEFORE any measurement. Everything here is FAKE.
  F1   Pseudo's test form (tests/fixtures/m27_form.ps1): its Subject field, never in M29's held-out set
  F2   the M27 fake page (tests/fixtures/m27_page.html): its reminders box, never in M29's held-out set
  F6   the M31 fake booking page (tests/fixtures/m31_page.html), new; its text fields start filled
  HELD_OUT   18 action requests, 3 per action type, in the order they are asked. Ids say where a request
             sits: S2-4 is the 4th request of session 2.
  sessions() the three sessions of SESSION_SIZE requests. Each holds one request of every action type, and
             the type order is rotated by 2 per session, so no type always sits in the 6th place (the
             largest input). Session 3 is all F6: six requests in a row on a page that looks the same.
The same 18, in the same order, are then asked with one launch per request (cold).
An expected popup is the control's type and name as Windows reports them, the action, and the exact text.
The criteria are M30's, fixed in PRD section 14 (M31) and copied into CRITERIA below; nothing is tuned.
"""

from brain_action_cases import ACTION_TYPES, held

FIXTURES = {"F1": "tests/fixtures/m27_form.ps1", "F2": "tests/fixtures/m27_page.html",
            "F6": "tests/fixtures/m31_page.html"}
SESSION_SIZE = 6  # the candidate: a session is stopped after this many requests, and a new one started
ROTATE_BY = 2  # session k starts ROTATE_BY * (k - 1) places further along ACTION_TYPES

HELD_OUT = [
    # session 1: press, set_text, insert_text, toggle, select, choose
    held("S1-1", "F6", "Button", "Check availability", "press", "Press Check availability on the booking page."),
    held("S1-2", "F1", "Edit", "Subject", "set_text",
         "Set the subject on the form to 'Fake budget review'.", "Fake budget review"),
    held("S1-3", "F6", "Edit", "Equipment needed", "insert_text",
         "Add 'Two extra chairs.' at the end of the equipment needed box, keeping what's already there.",
         "Two extra chairs."),
    held("S1-4", "F6", "CheckBox", "Need a projector", "toggle", "Tick the box that says we need a projector."),
    held("S1-5", "F6", "RadioButton", "Afternoon slot", "select",
         "Select the afternoon slot instead of the morning one."),
    held("S1-6", "F6", "ComboBox", "Building", "choose", "In the Building dropdown, pick Science block.",
         "Science block"),
    # session 2: insert_text, toggle, select, choose, press, set_text
    held("S2-1", "F6", "Edit", "Purpose", "insert_text",
         "After what's already in the purpose field, add 'for the whole team'.", "for the whole team"),
    held("S2-2", "F2", "CheckBox", "Send me reminders", "toggle",
         "Turn on the 'Send me reminders' checkbox on this page."),
    held("S2-3", "F6", "RadioButton", "Group room", "select",
         "We need a group room, not a quiet one: select that option."),
    held("S2-4", "F6", "ComboBox", "Seats", "choose", "Change the number of seats to Six.", "Six"),
    held("S2-5", "F6", "Hyperlink", "View house rules", "press", "Click the link to view the house rules."),
    held("S2-6", "F6", "Edit", "Booking title", "set_text",
         "Rename the booking: the title should be 'Design review' and nothing else.", "Design review"),
    # session 3: select, choose, press, set_text, insert_text, toggle (all on F6)
    held("S3-1", "F6", "RadioButton", "Evening slot", "select", "Pick the evening slot."),
    held("S3-2", "F6", "ComboBox", "Building", "choose", "Choose Main hall as the building.", "Main hall"),
    held("S3-3", "F6", "Button", "Clear the form", "press", "Use the Clear the form button to wipe my entries."),
    held("S3-4", "F6", "Edit", "Purpose", "set_text", "Change the purpose to 'Exam revision'.", "Exam revision"),
    held("S3-5", "F6", "Edit", "Equipment needed", "insert_text",
         "In the equipment needed box, put 'A spare marker pen.' after the existing text.", "A spare marker pen."),
    held("S3-6", "F6", "CheckBox", "Repeat weekly", "toggle", "Make this booking repeat weekly."),
]


def sessions() -> list[list[dict]]:
    """The requests as they are asked: one list per warm session, SESSION_SIZE requests each."""
    return [HELD_OUT[start:start + SESSION_SIZE] for start in range(0, len(HELD_OUT), SESSION_SIZE)]


def type_order(session_number: int) -> list[str]:
    """The action types of session 1, 2 or 3, in asked order: ACTION_TYPES rotated."""
    shift = ROTATE_BY * (session_number - 1) % len(ACTION_TYPES)
    return list(ACTION_TYPES[shift:] + ACTION_TYPES[:shift])


CRITERIA = {  # M30's, as written in PRD section 14 (M31); fixed before measuring. Judged on the warm sessions.
    "W_S_median_seconds_to_popup_max": 15.0,  # raw, over the usable requests
    "W_U_usable_min_of_18": 17,
    "W_R_own_read_before_acting_min_of_18": 18,
    "W_T_input_times_the_sessions_first_max": 3.0,  # fresh + cache-read + cache-written, over the model calls
    "W_B_billing_and_session_clean_min_of_18": 18,
}
