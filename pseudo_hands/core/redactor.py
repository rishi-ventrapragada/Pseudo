"""M7/M8/M19: Pseudo's local redactor. redact(text) masks personal info before any model sees it.

What it demonstrates: privacy as a plain core function (D6, D11). Microsoft's
Presidio does the finding, in two halves, like a linter and its --fix:
  analyzer   -> runs "recognizers" (regexes + a small spaCy language model)
                and returns spans like (PERSON, 10..21, score 0.85)
  anonymizer -> replaces each span with a mask like "[PERSON]"
Everything runs on this laptop; no text is sent anywhere.

The steps of redact(text):
  1. Your private terms become [PRIVATE] first, so nothing below can un-hide them.
  2. Known app/site names (allowed_names.txt) are split out and passed through untouched;
     every other piece goes through full detection (M8: stops "New Tab" looking like a name).
  3. Presidio finds and masks; "main.py"-style file names are not treated as web addresses.
     Dates and ages come from patterns, not spaCy's guesses (M19, date_recognizers.py), and
     code-shaped words like "M15" are never names, and weak plate shapes are ignored (finding_filters.py).
     Common Indian names come from a committed list as well as spaCy (M20, name_recognizers.py).
  4. The output is re-checked for phone/Aadhaar/long-number shapes; any leftover raises.
Fail closed: every finding is masked at any confidence (score_threshold=0), Indian formats
match by shape (india_recognizers.py), and ANY error raises RedactionError. redact() never
returns text it could not fully process. Nothing needs the network.
"""

import logging
import re
from functools import lru_cache
from pathlib import Path

from presidio_analyzer import AnalyzerEngine, PatternRecognizer, RecognizerRegistry
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_analyzer.predefined_recognizers import (
    InGstinRecognizer, InPassportRecognizer, InVehicleRegistrationRecognizer, InVoterRecognizer,
)
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

from pseudo_hands.core.date_recognizers import DATE_LEAK_CHECKS, date_recognizers
from pseudo_hands.core.finding_filters import is_weak_plate, trim_codes
from pseudo_hands.core.india_recognizers import LEAK_CHECKS, india_recognizers
from pseudo_hands.core.name_recognizers import name_recognizers

SPACY_MODEL = "en_core_web_sm"  # 12.8 MB; swap for "en_core_web_lg" (400 MB) if names get missed
# (M19) spaCy's DATE and TIME guesses masked "10:30", "Monday" and "order 4471". They are switched
# off where spaCy's labels become findings; date_recognizers.py masks every birthday-shaped date.
# (Filtering them out AFTER analysis would be wrong: Presidio keeps only the higher-scoring of two
# findings on the same span, so spaCy's guess had already replaced the date pattern's finding.)
SPACY_LABELS_IGNORED = ["DATE", "TIME"]
HERE = Path(__file__).resolve().parent
TERMS_FILE = HERE / "redaction_terms.txt"  # the owner's private terms (gitignored)
ALLOWED_NAMES_FILE = HERE / "allowed_names.txt"  # app/site names never masked (committed)
PLACES_FILE = HERE / "indian_places.txt"  # major Indian cities and states -> [LOCATION] (committed)
PRIVATE_MASK = "[PRIVATE]"
# (P5-tune) Presidio's load-time chatter ("Loaded recognizer", warnings about the non-English
# recognizers we never load) filled the terminal. Its errors still show.
logging.getLogger("presidio-analyzer").setLevel(logging.ERROR)
# US-only ID recognizers: nothing here is American, and they misfire on short codes ("M9" as a
# driver's license). Long ID numbers are still caught by LONG_NUMBER (any 8+ digit run).
US_ONLY = ["UsSsnRecognizer", "UsLicenseRecognizer", "UsBankRecognizer", "UsItinRecognizer", "UsPassportRecognizer"]
# Final catch-all: any "something@something" left after masking counts as a leak.
AT_TOKEN = re.compile(r"[\w.+\-]+@[\w.\-]+")
# spaCy's ORGANIZATION guesses in titles are app/site names, not personal, so they stay visible.
NOT_MASKED = {"ORGANIZATION"}
# "main.py" and "notes.md" look like web addresses to Presidio (.py and .md are real country
# domains). A URL finding with no "://", "/" or "www." that ends in one of these is a file name.
FILE_EXTENSIONS = {
    "py", "md", "txt", "json", "js", "ts", "tsx", "jsx", "html", "css", "csv", "pdf", "docx", "xlsx",
    "pptx", "png", "jpg", "jpeg", "gif", "svg", "yaml", "yml", "toml", "ini", "log", "sh", "ps1", "bat",
    "ipynb", "sql",
}
# An allowed name glued to one of these is part of a bigger token, like "notepad@okaxis" (UPI)
# or "github.com/someone" (URL), so it is NOT exempted there.
GLUE = r"\w@./\-"


class RedactionError(Exception):
    """Redaction could not be completed, so the text must be withheld, never shown as-is."""


def parse_list(text: str) -> list[str]:
    """One entry per line; '#' starts a comment. Matching ignores case."""
    return [line.split("#", 1)[0].strip() for line in text.splitlines() if line.split("#", 1)[0].strip()]


def load_list(path: Path, what: str) -> list[str]:
    """A missing list is an error, not "empty" (fail closed)."""
    try:
        return parse_list(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as error:
        raise RedactionError(f"can't read the {what} list ({type(error).__name__})") from None


def word_pattern(words: list[str], not_touching: str) -> re.Pattern | None:
    """Regex for any of the words (longest first), not directly touching those characters."""
    if not words:
        return None
    alternatives = "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))
    return re.compile(rf"(?<![{not_touching}])(?:{alternatives})(?![{not_touching}])", re.IGNORECASE)


def mask_private_terms(text: str, terms: list[str]) -> str:
    """Whole-word match with plain word boundaries: looser than the allowlist, so it masks more."""
    pattern = word_pattern(terms, r"\w")
    return pattern.sub(PRIVATE_MASK, text) if pattern else text


def split_on_allowed(text: str, names: list[str]) -> list[tuple[str, bool]]:
    """[(piece, is_allowed_name), ...]. [PRIVATE] masks are passed through like allowed names."""
    pattern = word_pattern([*names, PRIVATE_MASK], GLUE)
    pieces, position = [], 0
    for match in pattern.finditer(text):
        pieces += [(text[position:match.start()], False), (match.group(0), True)]
        position = match.end()
    return pieces + [(text[position:], False)]


@lru_cache(maxsize=1)
def build_analyzer() -> AnalyzerEngine:
    """Load spaCy + every recognizer once (slow, seconds); later calls reuse it."""
    nlp = NlpEngineProvider(nlp_configuration={
        "nlp_engine_name": "spacy", "models": [{"lang_code": "en", "model_name": SPACY_MODEL}],
        "ner_model_configuration": {"labels_to_ignore": SPACY_LABELS_IGNORED},
    }).create_engine()
    registry = RecognizerRegistry(supported_languages=["en"])
    registry.load_predefined_recognizers(languages=["en"], nlp_engine=nlp)  # email, phone, card, IP, URL, NER...
    for name in US_ONLY:
        registry.remove_recognizer(name)
    # Presidio's own Indian recognizers ship switched off; turn on the ones we don't replace.
    # The places list backs up spaCy, which misses cities like "Pune" (read once per process).
    places = PatternRecognizer(supported_entity="LOCATION", name="PseudoIndianPlacesRecognizer",
                               deny_list=load_list(PLACES_FILE, "Indian places"))
    for recognizer in [InPassportRecognizer(), InVoterRecognizer(), InVehicleRegistrationRecognizer(),
                       InGstinRecognizer(), *india_recognizers(), *date_recognizers(), *name_recognizers(), places]:
        registry.add_recognizer(recognizer)
    return AnalyzerEngine(nlp_engine=nlp, registry=registry, supported_languages=["en"])


@lru_cache(maxsize=1)
def build_anonymizer() -> AnonymizerEngine:
    return AnonymizerEngine()


def is_file_name(span: str) -> bool:
    """True for "main.py"-style spans the URL recognizer mistakes for web addresses."""
    lowered = span.lower()
    if "://" in lowered or "/" in lowered or lowered.startswith("www.") or "." not in lowered:
        return False
    return lowered.rsplit(".", 1)[1] in FILE_EXTENSIONS


def find_personal_info(text: str) -> list:
    """The analyzer half: every span any recognizer flags, at any confidence."""
    analyzer = build_analyzer()
    entities = [e for e in analyzer.get_supported_entities(language="en") if e not in NOT_MASKED]
    findings = analyzer.analyze(text=text, language="en", entities=entities, score_threshold=0.0)
    findings = [trim_codes(text, f) for f in findings if not is_weak_plate(f)]  # M19 (finding_filters.py)
    return [f for f in findings if f and not (f.entity_type == "URL" and is_file_name(text[f.start:f.end]))]


def mask_piece(piece: str) -> str:
    """Find and replace personal info in one piece of text (the anonymizer half)."""
    findings = find_personal_info(piece)
    operators = {f.entity_type: OperatorConfig("replace", {"new_value": f"[{f.entity_type}]"}) for f in findings}
    return build_anonymizer().anonymize(text=piece, analyzer_results=findings, operators=operators).text


def check_nothing_left(masked: str) -> None:
    """Belt and braces: if any Indian ID shape or a word@word token survived, refuse the result."""
    for name, shape in [*LEAK_CHECKS.items(), *DATE_LEAK_CHECKS.items(), ("word@word", AT_TOKEN)]:
        if shape.search(masked):
            raise RedactionError(f"a {name} shape survived masking; text withheld")


def redact(text: str) -> str:
    """Return text with personal info replaced by [ENTITY_TYPE]. Raises instead of leaking."""
    if not isinstance(text, str):
        raise TypeError("redact() takes a string")
    if not text.strip():
        return text
    terms = load_list(TERMS_FILE, "private terms")
    names = load_list(ALLOWED_NAMES_FILE, "allowed names")
    try:
        text = mask_private_terms(text, terms)  # first: a private term always beats the allowlist
        masked = "".join(piece if allowed or not piece.strip() else mask_piece(piece)
                         for piece, allowed in split_on_allowed(text, names))
    except Exception as error:  # noqa: BLE001 - any failure must end in "withheld", never in raw text
        raise RedactionError(f"redaction failed ({type(error).__name__}); text withheld") from None
    check_nothing_left(masked)
    return masked
