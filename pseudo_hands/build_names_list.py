"""M22: build indian_names_large.txt from Wikidata. A maintenance tool you run by hand; nothing imports it.

    python -m pseudo_hands.build_names_list [--out PATH]

What it demonstrates: turning a public dataset into a GAZETTEER (see name_recognizers.py), and
keeping its provenance. This is the only names code that touches the network; the redactor
itself still runs fully offline and only reads the text file this writes.

Source: the English labels ("Sachin Tendulkar") of every person on Wikidata whose citizenship is
India, British Raj or Dominion of India. Wikidata is CC0 (public domain), so the list may be
committed. The labels are split into single words: the file holds name WORDS, never full names.
Words that are also ordinary English are dropped (a lowercase entry in the en_GB spelling
dictionary: "mark", "joy", "grace"), so "Mark as read" stays readable. That costs real names
that are also words, the same trade-off as the hand list's "left out on purpose".
Downloads are cached in %LOCALAPPDATA%\\Pseudo\\names_sources, outside the repo.
"""

import argparse
import io
import json
import os
import re
import zipfile
from collections import Counter
from datetime import date
from pathlib import Path

import httpx2

CACHE = Path(os.environ["LOCALAPPDATA"]) / "Pseudo" / "names_sources"
OUT = Path(__file__).resolve().parent / "core" / "indian_names_large.txt"
USER_AGENT = "PseudoNamesBuilder/1.0 (personal, non-commercial; https://github.com/rishi-ventrapragada/Pseudo)"
SPARQL_URL = "https://query.wikidata.org/sparql"
QUERY = """SELECT ?label WHERE {
  VALUES ?country { wd:Q668 wd:Q129286 wd:Q1775277 }   # India, British Raj, Dominion of India
  ?person wdt:P27 ?country ; wdt:P31 wd:Q5 ; rdfs:label ?label .
  FILTER(LANG(?label) = "en")
}"""
DICTIONARY_URL = ("https://github.com/en-wl/wordlist/releases/download/rel-2026.02.25/"
                  "hunspell-en_GB-ize-2026.02.25.zip")
# Titles, not names. ("Dr" and "Mr" are already too short: words under 3 letters are dropped.)
HONORIFICS = {"Mrs", "Miss", "Shri", "Sri", "Shree", "Smt", "Sir", "Prof", "Lord", "Lady", "Saint", "Captain",
              "Colonel", "General", "Major", "Maharaja", "Maharani", "Nawab", "Begum", "Sultan", "Mahatma", "Ustad"}
# The same words indian_names.txt leaves out on purpose (see its header), so the big list can't put them back.
LEFT_OUT = {"Sunny", "Ruby", "Jasmine", "Rose", "Joy", "Hope", "Prince", "Lucky", "Ram", "Dev", "Om", "Jay",
            "Raja", "Rani", "Amar", "Sona", "Heera", "Moti", "Bose", "Tata", "Birla", "Bajaj", "Mahindra",
            "Godrej", "Kotak"}
NAME_WORD = re.compile(r"(?:[A-Z]')?[A-Z][a-z]+")  # the shape the recognizers look up: "Amit", "D'Souza"


def download(url: str, file_name: str, params: dict | None = None, accept: str = "*/*") -> bytes:
    """Fetch once into CACHE; later runs reuse the file (so the list can be rebuilt offline)."""
    cached = CACHE / file_name
    if not cached.exists():
        print(f"--- DOWNLOADING {url} ---")
        response = httpx2.get(url, params=params, headers={"User-Agent": USER_AGENT, "Accept": accept},
                               timeout=300, follow_redirects=True)
        response.raise_for_status()
        CACHE.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(response.content)
    return cached.read_bytes()


def wikidata_labels() -> list[str]:
    raw = download(SPARQL_URL, "wikidata_india_people_labels.json", params={"query": QUERY},
                   accept="application/sparql-results+json")
    return [row["label"]["value"] for row in json.loads(raw)["results"]["bindings"]]


def common_english_words() -> set[str]:
    """Lowercase entries of the en_GB hunspell dictionary (ESDB/SCOWL, (c) Kevin Atkinson): ordinary words."""
    with zipfile.ZipFile(io.BytesIO(download(DICTIONARY_URL, "hunspell-en_GB-ize.zip"))) as archive:
        dic = next(name for name in archive.namelist() if name.endswith(".dic"))
        lines = archive.read(dic).decode("utf-8").splitlines()[1:]  # first line: the entry count
    words = {line.split("/", 1)[0].strip() for line in lines}
    return {word for word in words if word and word == word.lower()}


def split_labels(labels: list[str]) -> tuple[Counter, Counter]:
    """Name words by position: the last word of a label counts as a surname, the others as first names."""
    first, last = Counter(), Counter()
    for label in labels:
        words = [word for word in label.split() if NAME_WORD.fullmatch(word.strip(",()"))]
        words = [word.strip(",()") for word in words]
        if not words:
            continue
        if len(words) == 1:
            first[words[0]] += 1  # one-word labels are mostly mononyms: "Rekha"
            continue
        first.update(words[:-1])
        last[words[-1]] += 1
    return first, last


def keep(word: str, common: set[str]) -> bool:
    return len(word) >= 3 and word not in HONORIFICS and word not in LEFT_OUT and word.lower() not in common


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=OUT)
    out = parser.parse_args().out
    labels = wikidata_labels()
    common = common_english_words()
    first, last = split_labels(labels)
    dropped = sorted({w for w in first | last if len(w) >= 3 and w.lower() in common})
    kept_first = sorted(w for w in first if keep(w, common))
    kept_last = sorted(w for w in last if keep(w, common))
    print(f"--- {len(labels)} label rows ({len(set(labels))} distinct) -> {len(first)} first-position and {len(last)} last-position words ---")
    print(f"--- KEPT {len(kept_first)} first names, {len(kept_last)} surnames; "
          f"{len(dropped)} words dropped as ordinary English ---")
    header = f"""# Indian name WORDS from Wikidata, generated by pseudo_hands/build_names_list.py (M22, D22). Don't edit by hand:
# add your own names to indian_names.txt instead, and rebuild this file with the script.
# Source: the {len(set(labels))} distinct English labels of people on Wikidata with citizenship India, British Raj or
#   Dominion of India (P27 = Q668, Q129286, Q1775277), fetched {date.today().isoformat()}.
# Licence: Wikidata data is CC0 1.0 (public domain): https://creativecommons.org/publicdomain/zero/1.0/
# Labels are split into single words; the last word of a label is filed as a surname.
# Dropped: words under 3 letters, titles (Shri, Smt, Nawab...), the words indian_names.txt leaves out on
#   purpose, and {len(dropped)} words that are ordinary English (lowercase entries of the en_GB hunspell
#   dictionary from ESDB/SCOWL, Copyright 2000-2026 by Kevin Atkinson, used only to filter).
"""
    body = "\n[first names]\n" + "\n".join(kept_first) + "\n\n[surnames]\n" + "\n".join(kept_last) + "\n"
    out.write_text(header + body, encoding="utf-8")
    print(f"--- WROTE {out} ({out.stat().st_size / 1024:.0f} KB) ---")


if __name__ == "__main__":
    main()
