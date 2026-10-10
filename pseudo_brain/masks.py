"""M42: counting what the redactor masked in a tool's result, for the Status panel ("Masked before sending").

What it demonstrates: a COUNT, not a copy. pseudo_hands masks personal info in core before anything
leaves it (D6, D11), so a result reads "Call [PERSON] on [IN_PHONE]". The brain only ever sees those
labels, and it counts them: no masked text, no positions, nothing is kept.
Only the redactor's own labels count. The list is written out here because the brain never imports
pseudo_hands' core; a test checks it against the redactor itself. So a page's own "[TODO]", or
Pseudo's "[restricted app]", isn't counted.
"""

import re

REDACTOR_LABELS = frozenset({
    "PERSON", "LOCATION", "NRP", "DATE_TIME", "AGE", "PRIVATE",  # names, places, groups, dates; your private terms
    "IN_PHONE", "IN_AADHAAR", "IN_PAN", "IN_UPI", "IN_PASSPORT", "IN_VOTER", "IN_VEHICLE_REGISTRATION",
    "IN_GSTIN", "LONG_NUMBER", "ID",  # Indian numbers and IDs, and any long number
    "PHONE_NUMBER", "EMAIL_ADDRESS", "EMAIL", "URL", "IP_ADDRESS", "MAC_ADDRESS", "CREDIT_CARD",
    "IBAN_CODE", "CRYPTO", "MEDICAL_LICENSE", "UK_NHS",  # Presidio's own recognizers
})
LABEL = re.compile(r"\[([A-Z][A-Z0-9_]*)\]")


def count_masks(text: str) -> int:
    """How many of the redactor's labels are in this text."""
    return sum(1 for match in LABEL.finditer(text) if match.group(1) in REDACTOR_LABELS)
