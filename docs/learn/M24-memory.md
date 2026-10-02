# M24: Pseudo remembers

## The concept in one paragraph

An LLM is stateless (M1): it forgets everything between calls. Sessions (M14) remember *one conversation*. M24 adds **long-term memory**: after each answered question, Pseudo offers the task to a local markdown vault, and before each new question it searches that vault and adds up to 3 relevant past tasks to the request. Two ideas carry it. **Memory is data with a privacy cost**: a note is redacted when saved, redacted again when sent, and only saved if you click OK. **Memory is context, not instructions**: the past tasks ride along as notes for one question, and the model can neither search nor write memory itself. Building it also exposed a statistics trap that M23's measurement couldn't show: a search tuned on 150 notes doesn't behave the same with 1.

## Web-dev analogy

- **The vault** is a folder of markdown files, like a static site's `content/` folder. Obsidian is just one editor for it, the way VS Code is for your MDX.
- **The in-memory FTS5 index refreshed by modification time** is a dev server's file watcher: it rebuilds only the files that changed since the last request.
- **Brain-only tools** are server-only API routes: the browser (the model) never gets the endpoint, so no script on the page can call it.
- **Memories as an extra system message** are like injecting search results into a prompt in a RAG app: per request, never stored in the chat history.
- **Background notes** are the reference corpus a search engine uses to know that "the" is common and "Vercel" is rare.

## What was built (file by file)

- **`pseudo_hands/core/memory.py`:** `save_memory()`: redact, ask in the popup, write a NEW note named after the time. It also holds the vault's location and its link checks.
- **`pseudo_hands/core/memory_search.py`:** `search_memories()`: the M23 winner (FTS5, Porter, cut-off 5.5) with the safety rules: skip bad notes, re-redact, cap, never raise.
- **`pseudo_hands/core/memory_background.txt`:** 150 fake notes for word statistics only.
- **`pseudo_hands/mcp_server.py`:** two thin tools. **`pseudo_brain/hands.py`** hides them from the model. **`chat.py`** searches before and saves after. **`session.py`** adds memories to a request inside the budget. **`loop.py`** records the tools used. **`terminal.py`** and the face's **`events.ts` / `state.ts`** word the new events.
- **Tests:** `test_memory.py` (16), `test_memory_sandbox.py` (10), `test_brain_memory.py` (9), 2 face tests; `conftest.py` gives every test a temporary vault.

## Walkthrough of the key code

**1. Redact, then ask, then write** (`memory.py`):
```python
question = redact(question[:MAX_QUESTION_CHARS])
answer = redact(answer)  # the whole answer first, THEN cut (never half a secret)
...
if not approval.ask(popup_question(question, answer)):  # THE GATE: you decide
    return {"status": NOT_APPROVED, ...}
name = new_note(tasks_folder(create=True), note_text(...))
```
The popup shows the *redacted* text, so you approve exactly what will be stored. `new_note` opens the file with mode `"x"`, which fails if the name already exists, so a note is never overwritten.

**2. The model never sees the memory tools** (`hands.py`):
```python
self.names = [tool.name for tool in tools if tool.name not in MEMORY_TOOLS]  # what the model may call
```
Text on the screen can try to talk the model into things (prompt injection). If the model doesn't have the tool, there's nothing to talk it into.

**3. Search before, save after** (`chat.py`):
```python
intro, memories = await self.recall(text, hands)
result = await run_turn(self.session, text, self.model, hands, self.on_event, memories, intro)
self.session.save()
if result.ok:
    await self.remember(text, result, hands)
```
Only answered turns are offered. The save is announced as a `tool_call` event with `"by": "pseudo"`, so the face's existing popup permission, taskbar flash and approval banner (M18) work unchanged.

**4. Memories ride along, then vanish** (`session.py`):
```python
if used:
    system.append({"role": "system", "content": "\n".join([intro, *used])})
...
if len(kept) > 1:
    kept.pop(0)  # the oldest whole turn first
elif used:
    used.pop()  # then the weakest memory
```
They're built into each request, never appended to `self.turns`, so they're never saved and never pile up.

**5. The trap: scores depend on how many notes exist.** BM25's rarity weight is `log((N - n + 0.5) / (n + 0.5))` for `N` notes, `n` of them containing the word. With `N = 1` it's below zero, and FTS5 then treats it as almost nothing. Measured on the same note:
```
1 notes: [('devops-1', 0.0)]        10 notes: [('devops-1', 3.84)]        30 notes: [('devops-1', 6.23)]
```
The cut-off of 5.5 came from M23's 150 notes, so a young vault would never get a memory. The fix: index M23's 150 **fake** notes too, but never return them (`AND name != ''` in the SQL), so rarity is judged against a stable crowd from day one.

## What happens when you run it (real output, annotated)

End to end: real Groq, the real popup (answered by a script), a temporary vault, fake tasks only.
```
1 approve : popup seen: True, outcome: ['memory_saved'] | notes: 1
   note: "...the Vercel build broke and [PERSON] [PHONE_NUMBER]) says NEXT_PUBLIC_API_URL is missing..."
2 deny    : popup seen: True, outcome: ['memory_not_saved'] | notes: 1           <- Cancel: nothing written
3 timeout : popup seen: True, outcome: ['memory_not_saved'] | notes: 1           <- 20 s, no answer: nothing
4 recall  : memories: {'count': 1, 'chars': 368} | groq prompt tokens: [635] | memory in request: True (445 chars, cap 1400)
5 edited  : memories: {'count': 1, 'chars': 407} | edit masked: True             <- a phone typed into the note went out masked
```
Two honest notes. The fake project name "Zephyr" was masked as `[LOCATION]` by spaCy, yet step 4 still found the note through "Vercel" and "build". And in steps 2-3 the fake secrets from question 1 *did* reach Groq: they were still in that session's history, because typed text goes as typed (L8). That's sessions, not memory: in the new sessions (4-5) nothing secret was sent. The M15 battery scored 12/12.

## Try this

1. Run `python -m pseudo_brain`, ask a fake question, and click OK in the popup. Then open `%LOCALAPPDATA%\Pseudo\memory` as a vault in Obsidian and find the note. Is anything in it unredacted?
2. In Obsidian, add a sentence with a fake phone number to that note. Ask a related question and watch for `MEMORY: 1 past task(s) added`. Think about why the number can't reach Groq.
3. In a Python shell, call `search_memories("price of gym plans")` with an empty vault, then with your one note. Why is the result empty both times, even though "gym plans" is a background note?

## Check yourself

1. Why are notes redacted when saved *and* again when found?
2. Why are `search_memories` and `save_memory` hidden from the model?
3. Why are memories added per request instead of being stored in the session?
4. What went wrong with a 1-note vault, and how do the background notes fix it?
5. Why is the vault in `%LOCALAPPDATA%` and not in `Documents`?

<details>
<summary>Answers</summary>

1. Saving redacts what Pseudo wrote. Searching redacts again because you can edit a note in Obsidian, and your edits never passed the first redaction.
2. So nothing the model reads (including text on a web page) can make Pseudo write to or search its memory. Pseudo calls them itself, at fixed points, and a save still needs your click.
3. They're relevant to one question. Stored in the session they would be resent with every later question, eating Groq's 8,000 tokens a minute, and would end up in the saved session file.
4. BM25 rewards rare words, and with 1 note every word is "in all the notes", so scores sat near 0 and never passed the 5.5 cut-off tuned on 150 notes. Indexing 150 fake notes for statistics only makes rarity behave as it did in M23, without ever returning them.
5. `Documents` is often synced to OneDrive, which would copy every memory to the cloud. `%LOCALAPPDATA%` stays on this laptop.
</details>

## How this connects to Pseudo's final architecture

- **Memory is Pseudo's first write path for your data.** It follows the same rules as actions: consent in a popup (D13), privacy in core (D6, D11), a sandbox (the M3 idea).
- **Any brain gets it:** Claude Code or Hermes connected to `pseudo_hands` would see the same two tools, with the same popup and redaction.
- **Next, from the Backlog:** paraphrases with no shared word ("plane running late" vs "flight delayed") still miss; saving a few model-written keywords with each note is the planned fix. Approving every save may get tiring; changing that is a separate decision (D23).
