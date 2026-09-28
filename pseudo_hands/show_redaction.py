"""M7: a thin terminal demo for redact(), on FAKE titles only. Run it from the repo root:

    python -m pseudo_hands.show_redaction

What it demonstrates: the redactor end to end, and what it costs in time. It
only calls core functions and prints (D11). Every title below is invented, so
printing them is safe; this demo never reads your real windows.
"""

import statistics
import time

from pseudo_hands.core.redactor import build_analyzer, redact

FAKE_TITLES = [
    "Chat with Rahul Verma, UPI rahul.v@okaxis - WhatsApp Web - Google Chrome",
    "Invoice #4471 for a.b@example.com - Gmail - Google Chrome",
    "Call +91 98765 43210 re: KYC - Notes",
    "PAN ABCPE1234F, Aadhaar 2345 6789 0123 - scan.pdf - Adobe Acrobat",
    "Bank statement acct 123456789012345 - Google Chrome",
    "Untitled - Notepad",
    "Downloads - File Explorer",
    "notes.md - Notepad",
    "New Tab - Google Chrome",
]
RUNS = 200


def main() -> None:
    print("--- LOADING THE REDACTOR (spaCy model + recognizers, once per process) ---")
    started = time.perf_counter()
    build_analyzer()
    print(f"loaded in {time.perf_counter() - started:.2f} s")

    print("\n--- FAKE TITLES, BEFORE -> AFTER ---")
    for title in FAKE_TITLES:
        after = redact(title)
        print(f"  {'changed' if after != title else 'same   '}  {title}\n           -> {after}")

    print(f"\n--- SPEED: {RUNS} redactions of fake titles ---")
    timings = []
    for i in range(RUNS):
        title = FAKE_TITLES[i % len(FAKE_TITLES)]
        started = time.perf_counter()
        redact(title)
        timings.append((time.perf_counter() - started) * 1000)
    timings.sort()
    print(f"mean {statistics.mean(timings):.1f} ms | median {statistics.median(timings):.1f} ms | "
          f"95th percentile {timings[int(RUNS * 0.95) - 1]:.1f} ms | slowest {timings[-1]:.1f} ms")


if __name__ == "__main__":
    main()
