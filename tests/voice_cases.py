"""M25: the fake sentences for measuring speech to text and text to speech. Not a test file itself.

Everything here is FAKE: invented name combinations, India's well-known dummy phone number, made-up
orders and rooms. This file was committed BEFORE any audio was generated or any service measured, and
nothing is tuned on it (model settings and thresholds were fixed in the M25 plan), so there's no
DEV/TEST split.
  V1       8 Pseudo commands
  V2       10 sentences with fake Indian names; `names` = the name words scored by A2
  V3       8 lines of Indian English, numbers and codes; `numbers` = the numbers and codes scored by A3
  V4       4 non-speech clips, generated in the scratchpad (A4: none may produce a message)
  ANSWERS  6 fake answers, 100-600 characters, for text to speech (L2, Q1)
Word error rate (A1) is scored on each sentence's other words; a lone initial ("S.") is never scored,
because it identifies nobody (as in M20).
Each V1-V3 sentence is spoken by two English (India) voices and one US voice, clean and with noise.
"""

V1 = [
    {"text": "What am I working on right now?", "names": [], "numbers": []},
    {"text": "Focus the Notepad window.", "names": [], "numbers": []},
    {"text": "Read the active window and give me a short summary.", "names": [], "numbers": []},
    {"text": "Which windows are open at the moment?", "names": [], "numbers": []},
    {"text": "Switch to the Groq fallback model.", "names": [], "numbers": []},
    {"text": "Start a new session and close the old one.", "names": [], "numbers": []},
    {"text": "Remember that the lab report is due on Friday.", "names": [], "numbers": []},
    {"text": "Did I finish the slides for the design review?", "names": [], "numbers": []},
]

V2 = [
    {"text": "Remind me to call Keerthana Boddu at four.", "names": ["Keerthana", "Boddu"], "numbers": []},
    {"text": "Did Sneha Reddy reply about the hackathon?", "names": ["Sneha", "Reddy"], "numbers": []},
    {"text": "Send S. Ramesh the notes from today's class.", "names": ["Ramesh"], "numbers": []},
    {"text": "Ask Venkatesh Iyer whether the lab is open tomorrow.", "names": ["Venkatesh", "Iyer"], "numbers": []},
    {"text": "Schedule a meeting with Harpreet Kaur and Anil Kumar.",
     "names": ["Harpreet", "Kaur", "Anil", "Kumar"], "numbers": []},
    {"text": "What did Mohammed Irfan say about the budget?", "names": ["Mohammed", "Irfan"], "numbers": []},
    {"text": "Open the chat with Lakshmi Narayanan.", "names": ["Lakshmi", "Narayanan"], "numbers": []},
    {"text": "Tell Sourav Chatterjee the train is running late.", "names": ["Sourav", "Chatterjee"], "numbers": []},
    {"text": "Remind me to wish Pallavi Deshpande a happy birthday.", "names": ["Pallavi", "Deshpande"], "numbers": []},
    {"text": "Forward the invoice to Srinivas Rao and Bhavana Nair.",
     "names": ["Srinivas", "Rao", "Bhavana", "Nair"], "numbers": []},
]

V3 = [
    {"text": "Kindly prepone the project review to Monday.", "names": [], "numbers": []},
    {"text": "Please do the needful and revert by evening itself.", "names": [], "numbers": []},
    {"text": "My order 4471 ships on Monday.", "names": [], "numbers": ["4471"]},
    {"text": "Call me back on 98765 43210.", "names": [], "numbers": ["98765 43210"]},
    {"text": "Pay 2500 rupees through UPI for the hostel fees.", "names": [], "numbers": ["2500"]},
    {"text": "Upload the M15 notes before the CS101 quiz.", "names": [], "numbers": ["M15", "CS101"]},
    {"text": "The meeting is at 10:30 in room 204.", "names": [], "numbers": ["10:30", "204"]},
    {"text": "Set a reminder for 7:45 tomorrow morning.", "names": [], "numbers": ["7:45"]},
]

# Generated in the scratchpad as 16 kHz mono WAV. Levels are RMS in dBFS (0 = the loudest a file can be).
# The M25 silence rule never sends a clip whose loudest 100 ms is below -45 dBFS, so the silence stays
# on the laptop, while the noise, hum and clicks are loud enough to reach Whisper's own silence check.
V4 = [
    {"name": "silence", "seconds": 3.0, "level_dbfs": None},  # digital silence: all zeros
    {"name": "noise", "seconds": 3.0, "level_dbfs": -35.0},  # soft white noise, like a fan
    {"name": "hum", "seconds": 3.0, "level_dbfs": -30.0},  # 50 Hz mains hum (India's grid frequency)
    {"name": "clicks", "seconds": 3.0, "level_dbfs": -30.0},  # short clicks, six a second, like typing
]

ANSWERS = [
    "You're working in Visual Studio Code on the Pseudo project, with a terminal and Notepad open beside it.",
    "The active window is Notepad. It holds a short to-do list: finish the lab report, email the CS101 notes "
    "to your study group, and book train tickets for the weekend trip.",
    "You have three windows open. Visual Studio Code shows the M25 plan, Chrome has the Groq documentation, "
    "and Notepad holds your shopping list. The plan is the one in front, so that's probably what you're "
    "working on. Should I focus one of the others, or read the plan's open file?",
    "From your memory notes: on Monday you asked [PERSON] to send the hackathon slides, and order 4471 was "
    "due to ship the same day. I can't see whether either happened, because the mail app is on your blocked "
    "list. Would you like me to read another window instead?",
    "The document in front is a project report. It has four sections. The introduction explains why the "
    "team built a study planner. The method section describes a survey of forty students. The results say "
    "most students plan their week on Sunday evening and miss deadlines in exam weeks. The last section "
    "suggests reminders two days before each deadline.",
    "Here's what I found in the window. Your timetable shows three classes tomorrow: data structures at "
    "nine, a CS101 lab at eleven thirty, and a seminar at three. The lab sheet asks for a linked list "
    "program and a short write-up. There's also a note at the bottom saying the seminar room changed to "
    "room 204. Nothing else on the page looks urgent. If you want, I can remember the room change, or "
    "focus your notes so you can start the lab sheet now. Last week's seminar notes are in the same "
    "folder, and the lab sheet is due on Friday evening.",
]
