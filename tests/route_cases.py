"""M30: questions for checking the routing rule (pseudo_brain/routing.py: is_action_request).
Not a test file itself.

Everything here is FAKE, and was committed BEFORE the rule was run on any of them. The bar was fixed
in the M30 plan: at least 18 of the 20 ACTION questions are routed to Claude Code, and at most 2 of the
20 OTHER questions are. The same person wrote the rule and these questions, so this is a sanity check;
real use is the real test (as R1 was in M29).
  ACTION   20 requests to act on a window: these should go to Claude Code.
  OTHER    20 questions, switch requests and read requests: these should stay on Groq.
Some are phrased the way people really talk ("needs to be ticked"), which a word rule may miss.
"""

ACTION = [
    "Click the Save draft button.",
    "Press Submit on the form.",
    "Tick the newsletter box.",
    "Untick 'Remember this device'.",
    "Type 'Fake meeting notes' into the Title field.",
    "Please select the Monthly plan option.",
    "Can you choose 'Blue' in the colour dropdown?",
    "Add 'See you at five' to the end of the message box.",
    "Replace the subject with 'Fake invoice 12'.",
    "Turn off email alerts.",
    "Set the quantity to 3.",
    "Could you hit the Refresh button for me?",
    "Pick the second delivery slot.",
    "Fill in the city field with 'Faketown'.",
    "I'd like the dark theme switched on.",
    "Clear the search box.",
    "Change the language to Hindi.",
    "Open the Settings link on this page.",
    "The agree checkbox needs to be ticked.",
    "Enter 'FAKE50' as the promo code.",
]

OTHER = [
    "What does this page say?",
    "Which windows are open?",
    "Switch to the Notepad window.",
    "Bring the browser to the front.",
    "Summarise the window I'm on.",
    "How many buttons are on this form?",
    "Is the reminders box ticked?",
    "Read me the status line.",
    "What is 12 times 12?",
    "Open the calculator window.",
    "Who is this email from?",
    "Can I see the fake order page?",
    "Tell me what options the dropdown has.",
    "Which option is selected for payment?",
    "Explain what the Apply coupon button would do.",
    "Does the form have a password field?",
    "Show me the test form window.",
    "What did I type in the notes box?",
    "Check whether the page mentions a deadline.",
    "Give me a summary of the changes on screen.",
]

BAR = {"action_routed_min_of_20": 18, "other_routed_max_of_20": 2}
