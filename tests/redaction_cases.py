"""M19: the redactor's fixed test sets, written BEFORE the fix was measured. Not a test file itself.

Every line here is FAKE. test_redactor_m19.py turns these into tests, and the M19 lesson's
measurement script uses the same lists.
  ORDINARY     ordinary text that must NOT be masked: (line, token that must survive, or None)
  SENSITIVE    every sensitive fake case from M7-M18: (text, pieces that must not survive)
  GUARDS       what M19 touches: birth dates, ages, names next to codes and times, full plates
  RESIDUALS    ordinary lines still over-masked after M19, named in advance (strict xfail)
  KNOWN_LEAKS  names spaCy's small model missed: the live privacy leak found in M19, fixed by M20's names list
"""

ORDINARY = {
    "codes": [("Pseudo M15 notes", "M15"), ("Pseudo M15 target", "M15"), ("M18 lesson - Notepad", "M18"),
              ("Phase 5 plan.md - Notepad", None), ("Release v2.1 notes", "v2.1"), ("Python 3.11 setup guide", "3.11"),
              ("Electron 44.4.5 changelog", "44.4.5"), ("Node 24 LTS download", None), ("Q3 OKR review", "Q3"),
              ("Sprint 14 board", None)],
    "departments": [("CSE-DS timetable", "CSE-DS"), ("CSE-AIML lab schedule", "CSE-AIML"),
                    ("ECE-2 section list", "ECE-2"), ("Room B-204 booking", "B-204")],
    "tickets and orders": [("Ticket #8812 - login bug", "#8812"), ("PSD-142 fix login redirect", "PSD-142"),
                           ("Notes: order 4471 shipped", "4471"), ("Invoice #4471", "#4471"), ("PR #318 review", "#318"),
                           ("Build 2041 failed", "2041"), ("Order #A-20931 tracking", "#A-20931")],
    "courses": [("CS101 lecture notes", "CS101"), ("MA2201 assignment 3", "MA2201"), ("21CS42 lab record", "21CS42"),
                ("DBMS unit 4 notes", None), ("OS lab - week 6", None), ("Chapter 3.2 exercises", None),
                ("Lecture 12 slides.pdf", None), ("Sem 5 results", None)],
    "times": [("Standup at 10:30", "10:30"), ("Class 14:00-15:30", "14:00-15:30"), ("Meet at 5 pm", "5 pm"),
              ("Reminder 9:15 AM", "9:15 AM")],
    "weekdays and relative dates": [("Notes: order 4471 ships on Monday", "Monday"), ("Quiz next week", "next week"),
                                    ("Lab on Friday", "Friday"), ("Due tomorrow", "tomorrow")],
    "other": [("Project status: BLUE (fake)", None), ("Progress 45%", None), ("Top 10 tips", None),
              ("Fake target window for focus_window", None)],
}
ORDINARY_LINES = [(line, token) for lines in ORDINARY.values() for line, token in lines]

# Aadhaar-shaped: the first has a valid Verhoeff checksum, the second is one digit off (test_redactor.py).
_AADHAAR = ["234567890124", "234567890125"]
PLACES = ["Pune", "Maharashtra", "navi mumbai", "Tamil Nadu"]

SENSITIVE = [
    ("Mail a.b@example.com, card 4111 1111 1111 1111, host 192.168.10.20, see https://example.org/x",
     ["a.b@example.com", "4111", "192.168.10.20", "example.org"]),
    ("Chat with Rahul Verma about the invoice", ["Rahul", "Verma"]),
    *[(f"Call me on {phone} tomorrow", ["98765", "43210"])
      for phone in ["+91 98765 43210", "+91-9876543210", "09876543210", "98765-43210"]],
    *[(f"Aadhaar {n[:4]} {n[4:8]} {n[8:]}", [n[:4], n[4:8], n[8:]]) for n in _AADHAAR],
    ("PAN ABCPE1234F", ["ABCPE1234F"]), ("PAN abcpe1234f", ["abcpe1234f"]),
    ("Pay rahul.v@okaxis or 9876543210@ybl, receipt to a.b@example.com",
     ["okaxis", "ybl", "rahul.v", "example.com", "9876543210"]),
    ("Ref 123456789012345", ["123456789012345", "1234"]), ("Ref 12-3456-7890", ["3456", "7890"]),
    ("Chat with Claude Martin", ["Claude", "Martin"]),
    ("Chat with Rahul Verma, +91 98765 43210 - WhatsApp Web - Google Chrome", ["Rahul", "98765"]),
    *[(f"Open {glued} - Google Chrome", [glued]) for glued in ["notepad@okaxis", "github.com/someone", "spotify.example.org"]],
    ("see example.org, www.example.net and github.com/someone", ["example.org", "example.net", "someone"]),
    ("Notes: PAN on file. UPI rahul.v@okaxis. Aadhaar pending.", ["okaxis"]),
    ("Ref 123-45-6789 on file", ["123", "6789"]),
    *[(f"Office in {place}", [place]) for place in PLACES],
    *[(f"Meeting in {place} next week", [place]) for place in PLACES],
    ("Chat with Rahul Verma, UPI rahul.v@okaxis - WhatsApp Web - Google Chrome", ["Rahul", "okaxis"]),
    ("Invoice #4471 for a.b@example.com - Gmail - Google Chrome", ["a.b@example.com"]),
    ("Call +91 98765 43210 re: KYC - Notes", ["98765"]),
    ("PAN ABCPE1234F, Aadhaar 2345 6789 0123 - scan.pdf - Adobe Acrobat", ["ABCPE1234F", "6789"]),
    ("Bank statement acct 123456789012345 - Google Chrome", ["123456789012345"]),
    ("Rahul Verma +91 98765 43210.txt - Notepad", ["Rahul", "98765"]),  # the M8 marker file
    ("Meeting with Rahul Verma in Pune on Friday", ["Rahul", "Verma", "Pune"]),  # the M15/M18 notes window
    ("Call +91 98765 43210 before 5 pm", ["98765", "43210"]),
]

GUARDS = {
    "birth dates": [("DOB 12/03/1998", ["12/03/1998", "1998"]), ("DOB: 12-03-1998", ["12-03-1998", "1998"]),
                    ("born 12.03.1998", ["12.03.1998"]), ("Date of birth: 1998-03-12", ["1998"]),
                    ("Born on 3 March 1998", ["3 March", "1998"]), ("March 3, 1998", ["March 3", "1998"]),
                    ("the third of March 1998", ["third of March", "1998"]), ("Birthday 3rd March", ["3rd March"]),
                    ("Holiday on 15 August", ["15 August"]), ("Born in 1998", ["1998"])],
    "ages": [("Rahul, 34 years old", ["34"]), ("a 34-year-old", ["34"]), ("age 34", ["34"]), ("aged 34", ["34"])],
    "names next to codes and times": [("Meeting with Priya Sharma at 10:30", ["Priya", "Sharma"]),
                                      ("M15 notes from Rahul Verma", ["Rahul", "Verma"]),
                                      ("Ticket from Arjun Mehta: login bug", ["Arjun", "Mehta"])],
    "full vehicle plates": [("Vehicle MH12AB1234 parked", ["MH12AB1234"])],
}

RESIDUALS = ["Node 24 LTS download", "Q3 OKR review", "ECE-2 section list", "Quiz next week"]

KNOWN_LEAKS = [("Call Anil Kumar re CS101", ["Anil", "Kumar"]), ("Sneha Reddy - CSE-DS - MA2201", ["Sneha", "Reddy"]),
               ("Venkatesh Iyer review", ["Venkatesh", "Iyer"])]
