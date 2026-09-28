"""M9: a thin terminal demo for read_active_window(). Run it from the repo root:

    python -m pseudo_hands.show_active_window

You get 3 seconds to click the window you want read; then it prints exactly
what a model would receive: the redacted outline, capped at 1,200 characters.
It only calls core and prints (D11).

Privacy: it prints YOUR window's (redacted) contents to YOUR terminal. Don't
paste the output into a chat with a cloud model.
"""

import time

from pseudo_hands.core.active_window import read_active_window


def main() -> None:
    print("--- CLICK THE WINDOW TO READ (3 seconds) ---")
    for second in (3, 2, 1):
        print(f"  {second}...")
        time.sleep(1)

    print("\n--- READING ITS UI AUTOMATION TREE (redacted, capped) ---")
    started = time.perf_counter()
    result = read_active_window()
    elapsed = time.perf_counter() - started
    print(f"title: {result['title']}\napp:   {result['app']}")
    print(f"controls read: {result['controls_read']} | truncated: {result['truncated']} | "
          f"note: {result['note'] or '-'} | took {elapsed:.2f} s")
    print(f"\n--- CONTENT ({len(result['content'])} characters: what the model sees) ---")
    print(result["content"] or "(nothing)")


if __name__ == "__main__":
    main()
