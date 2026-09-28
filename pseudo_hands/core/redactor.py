"""M7: Pseudo's local redactor. redact(text) masks personal info before any model sees it.

What it demonstrates: privacy as a plain core function (D6, D11). Microsoft's
Presidio does the finding, in two halves, like a linter and its --fix:
  analyzer   -> runs "recognizers" (regexes + a small spaCy language model)
                and returns spans like (PERSON, 10..21, score 0.85)
  anonymizer -> replaces each span with a mask like "[PERSON]"
Everything runs on this laptop; no text is sent anywhere.

Fail closed (when unsure, mask), six ways:
  1. score_threshold=0: every finding is masked, even low-confidence guesses.
  2. Indian formats match by shape, never by checksum (india_recognizers.py).
  3. LONG_NUMBER catches any 8+ digit run no other recognizer understood.
  4. The output is re-checked for phone/Aadhaar/number shapes; any leftover raises.
  5. Any error (model, analyzer, anonymizer, terms file) raises RedactionError.
     redact() never returns text it could not fully process.
  6. Nothing needs the network (a test proves it with sockets blocked).
"""

from functools import lru_cache
from pathlib import Path

from presidio_analyzer import AnalyzerEngine, PatternRecognizer, RecognizerRegistry
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_analyzer.predefined_recognizers import (
    InGstinRecognizer, InPassportRecognizer, InVehicleRegistrationRecognizer, InVoterRecognizer,
)
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

from pseudo_hands.core.india_recognizers import LEAK_CHECKS, india_recognizers

SPACY_MODEL = "en_core_web_sm"  # 12.8 MB; swap for "en_core_web_lg" (400 MB) if names get missed
TERMS_FILE = Path(__file__).resolve().parent / "redaction_terms.txt"
# App and site names ("Visual Studio Code", "GitHub") are what window titles are made of,
# and they are not personal, so spaCy's ORGANIZATION guesses are deliberately left visible.
NOT_MASKED = {"ORGANIZATION"}
# "main.py" and "notes.md" look like web addresses to Presidio (.py and .md are real country
# domains). A URL finding with no "://", "/" or "www." that ends in one of these is a file name.
FILE_EXTENSIONS = {
    "py", "md", "txt", "json", "js", "ts", "tsx", "jsx", "html", "css", "csv", "pdf", "docx", "xlsx",
    "pptx", "png", "jpg", "jpeg", "gif", "svg", "yaml", "yml", "toml", "ini", "log", "sh", "ps1", "bat",
    "ipynb", "sql",
}


class RedactionError(Exception):
    """Redaction could not be completed, so the text must be withheld, never shown as-is."""


def parse_terms(text: str) -> list[str]:
    """One private term per line; '#' starts a comment. Matching ignores case."""
    return [line.split("#", 1)[0].strip() for line in text.splitlines() if line.split("#", 1)[0].strip()]


def load_terms() -> list[str]:
    """Read the owner's private terms. A missing list is an error, not "no terms" (fail closed)."""
    try:
        return parse_terms(TERMS_FILE.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as error:
        raise RedactionError(f"can't read the private terms list ({type(error).__name__})") from None


@lru_cache(maxsize=1)
def build_analyzer() -> AnalyzerEngine:
    """Load spaCy + every recognizer once (slow, seconds); later calls reuse it."""
    nlp = NlpEngineProvider(nlp_configuration={
        "nlp_engine_name": "spacy", "models": [{"lang_code": "en", "model_name": SPACY_MODEL}],
    }).create_engine()
    registry = RecognizerRegistry(supported_languages=["en"])
    registry.load_predefined_recognizers(languages=["en"], nlp_engine=nlp)  # email, phone, card, IP, URL, NER...
    # Presidio's own Indian recognizers ship switched off; turn on the ones we don't replace.
    for recognizer in [InPassportRecognizer(), InVoterRecognizer(), InVehicleRegistrationRecognizer(),
                       InGstinRecognizer(), *india_recognizers()]:
        registry.add_recognizer(recognizer)
    return AnalyzerEngine(nlp_engine=nlp, registry=registry, supported_languages=["en"])


@lru_cache(maxsize=1)
def build_anonymizer() -> AnonymizerEngine:
    return AnonymizerEngine()


def terms_recognizers(terms: list[str]) -> list[PatternRecognizer]:
    """Built per call ("ad hoc"), so edits to the terms file apply without a restart."""
    if not terms:
        return []
    return [PatternRecognizer(supported_entity="PRIVATE", name="PseudoPrivateTermsRecognizer",
                              deny_list=terms, deny_list_score=1.0)]


def is_file_name(span: str) -> bool:
    """True for "main.py"-style spans the URL recognizer mistakes for web addresses."""
    lowered = span.lower()
    if "://" in lowered or "/" in lowered or lowered.startswith("www.") or "." not in lowered:
        return False
    return lowered.rsplit(".", 1)[1] in FILE_EXTENSIONS


def find_personal_info(text: str, terms: list[str]) -> list:
    """The analyzer half: every span any recognizer flags, at any confidence."""
    analyzer = build_analyzer()
    entities = [e for e in analyzer.get_supported_entities(language="en") if e not in NOT_MASKED]
    if terms:
        entities.append("PRIVATE")
    findings = analyzer.analyze(text=text, language="en", entities=entities, score_threshold=0.0,
                                ad_hoc_recognizers=terms_recognizers(terms))
    return [f for f in findings if not (f.entity_type == "URL" and is_file_name(text[f.start:f.end]))]


def check_nothing_left(masked: str) -> None:
    """Belt and braces: if a phone, Aadhaar or long number survived, refuse the result."""
    for name, shape in LEAK_CHECKS.items():
        if shape.search(masked):
            raise RedactionError(f"a {name} shape survived masking; text withheld")


def redact(text: str) -> str:
    """Return text with personal info replaced by [ENTITY_TYPE]. Raises instead of leaking."""
    if not isinstance(text, str):
        raise TypeError("redact() takes a string")
    if not text.strip():
        return text
    terms = load_terms()
    try:
        findings = find_personal_info(text, terms)
        operators = {f.entity_type: OperatorConfig("replace", {"new_value": f"[{f.entity_type}]"})
                     for f in findings}
        masked = build_anonymizer().anonymize(text=text, analyzer_results=findings, operators=operators).text
    except Exception as error:  # noqa: BLE001 - any failure must end in "withheld", never in raw text
        raise RedactionError(f"redaction failed ({type(error).__name__}); text withheld") from None
    check_nothing_left(masked)
    return masked
