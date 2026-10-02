# M23: How Pseudo will find relevant memories (evaluated)

## The concept in one paragraph

Pseudo will remember every task, but it can't send them all to the model: Groq allows about 8,000 tokens a minute, and every memory sent is data leaving the laptop. So for each question it must **retrieve** (find) the few past tasks that matter. M23 compared two **keyword searches** that run on the laptop with no model: **BM25** written in pure Python (K1), and **SQLite FTS5** (K2), the full-text search built into Python's `sqlite3`. A third option, **cloud embeddings**, was ruled out on paper. Both keyword searches were tuned on 20 questions and measured once on 40 held-out ones, against criteria fixed beforehand. **K2 won: 83% of answerable questions found their note in the top 3** (the bar was 80%), at 3.3 ms per search. Getting that speed meant learning where the time really went.

## Web-dev analogy

- **Retrieval** is the search box on a docs site. Before the AI sees anything, a search finds the 3 most relevant pages, and only those go into the prompt. This is the "R" in RAG (retrieval-augmented generation).
- **BM25** is what Elasticsearch and Postgres full-text search rank with. FTS5 is SQLite's version of Postgres' `tsvector` and `ts_rank`.
- **Embeddings** turn text into a list of numbers so "plane late" lands near "flight delayed". It's like sending every row of your database to a third-party API so it can be searched by meaning.
- **An in-memory index refreshed by modification time** is webpack's watch mode: it doesn't rebuild everything on each save, only the files whose timestamp changed.

## What was built (file by file)

- **`PRD.md`:** Phase 6 (Memory) with M23 and M24, and M23's result.
- **`tests/memory_cases.py`** (committed before any search existed): 150 fake task notes in their stored, redacted form; 20 DEV questions for tuning; 40 TEST questions (15 reuse a note's words, 15 paraphrase, 10 match nothing).
- **Scratchpad only** (not committed): the measurement scripts. M24 will build the winner properly, with tests.

## Walkthrough of the key code

**1. BM25 in one line of maths.** For each question word found in a note:
```python
idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))                         # rarer words count more
score += idf * tf[t] * 2.5 / (tf[t] + 1.5 * (0.25 + 0.75 * len(words) / avg))  # repeats help, with diminishing returns; long notes don't win by size
```
`tf` is how often the word appears in the note, `df` how many notes contain it, and `n` the number of notes. A word in every note ("pay") scores almost nothing; a rare one ("SIP") scores a lot.

**2. FTS5 does the same inside SQLite:**
```python
db.execute("CREATE VIRTUAL TABLE notes USING fts5(id UNINDEXED, body, tokenize='porter unicode61')")
rows = db.execute("SELECT id, -bm25(notes) FROM notes WHERE notes MATCH ? ORDER BY bm25(notes) LIMIT 3", (match,))
```
`porter` is a **stemmer**: it cuts words to a common root, so "revising" and "revision" both become "revis". That's why K2 found 10 of 15 paraphrases and K1 (a simple 4-rule stemmer) only 7. Two details matter: `match` joins the words with `OR`, because FTS5's default (AND) would demand every word of a chatty question; and `bm25()` is *negative*, lower is better.

**3. The "nothing relevant" cut-off.** A search always finds *something*, even for "how tall is Mount Everest". So a memory is used only if its score passes a cut-off, tuned on DEV: the lowest score that kept DEV's 4 unrelated questions empty (5.5 for K2).

**4. Where the time went.** The first speed test failed badly: 220 ms per search at 1,000 notes, and once 9.8 s. A profile split it up:
```
scandir + stat only: median 2 ms        <- listing the folder with modification times
read every file    : first 6591 ms, median 204 ms   <- opening 1,000 files; the first time, Windows scanned them all
FTS5 build in RAM  : median 9 ms
FTS5 query only    : median 0 ms
```
Opening a file on Windows costs about 0.2 ms, so reading every note on every question was the whole cost. The fix keeps the index in memory: each search lists the folder (2 ms) and re-reads only notes whose modification time changed. An edit in Obsidian still counts at the very next question.

## What happens when you run it (real output, annotated)

```
K1 tuned on DEV: variant=True cut=6.0 | DEV hits@3 16/16, no-match empty 4/4
K2 tuned on DEV: variant=True cut=5.5 | DEV hits@3 15/16, no-match empty 4/4
===== K1 TEST =====
Q1 Recall@3 22/30 (73%) | Q2 no-match with no memory 8/10 | Q3 MRR 0.72      <- misses Q1 (>= 80%)
   same words: 15/15 | paraphrase: 7/15
===== K2 TEST =====
Q1 Recall@3 25/30 (83%) | Q2 no-match with no memory 8/10 | Q3 MRR 0.82      <- passes
   same words: 15/15 | paraphrase: 10/15
   missed: 'is my plane running late', 'why did my credit rating go down', 'what did Sneha ask me to get'...
   no-match questions that still got memories: 'set an alarm for 6 am' -> the 6:10 am flight note
K2 incremental, 1000 notes: search median 3.3 ms | one note edited before each search: 5.6 ms | RAM +2.0 MB
K2 incremental, 10000 notes: search median 27.9 ms | first index build 2472 ms
3 full memories (1579 chars): Groq counted 956 prompt tokens (a question alone: ~510)
```
Notice DEV was perfect for K1 (16/16) but TEST wasn't (73%). That gap is exactly why held-out questions exist: tuning always flatters the set you tuned on.

## Try this

1. In a Python shell, create an FTS5 table as above, insert "flight delayed by 45 minutes", and search `"plane" OR "late"`. Why is it empty, and what kind of search would find it?
2. Insert the same note into a table **without** `tokenize='porter unicode61'`, and search `"delays"`. Then add Porter back.
3. Search `"set" OR "alarm" OR "6" OR "am"` over a note that says "6:10 am flight". Which single word causes the false match, and would dropping numbers from questions help or hurt?

## Check yourself

1. Why does Pseudo need retrieval at all, instead of sending every memory?
2. In BM25, why does a rare word count more than a common one?
3. Why were cloud embeddings ruled out, even though they understand paraphrases better?
4. K1 scored 16/16 on DEV but 73% on TEST. What does that tell you?
5. What made the first speed test slow, and why does the fix still notice your Obsidian edits?

<details>
<summary>Answers</summary>

1. Tokens and privacy: Groq allows about 8,000 tokens a minute, and every memory sent leaves the laptop. Sending only the 3 most relevant ones keeps both small.
2. A rare word says much more about which note you mean. "SIP" appears in 2 of the 150 notes; words starting with "pay" appear in 6.
3. Every note and every question would go to a second company (D6), Voyage trains on data unless you opt out, and it needs a manual account. Keyword search sends only the 3 chosen memories, to the provider already in use. Embeddings stay as the fallback if keyword search ever fails Q1.
4. Tuning fits the settings to the questions you tune on. Only questions kept apart (TEST) show how it does on questions it hasn't seen.
5. Opening 1,000 files took about 200 ms (Windows charges ~0.2 ms per file, and it scans freshly written files). The fix lists the folder with modification times (2 ms) and re-reads only changed notes, so an edit is picked up at the next question.
</details>

## How this connects to Pseudo's final architecture

- **M24 builds it:** FTS5 in `pseudo_hands` core, beside the redactor and the approval popup. Notes are redacted before saving and again when found, every save asks you first, and at most 3 memories (1,400 characters, ≤ 400 tokens) join a question.
- **D23 records the design** (approved 2026-10-02), with these numbers; L6 moved to LOCKED as part of it.
- **Known limits to watch in real use:** paraphrases with no shared word, and questions that name a person the note stores as [PERSON]. If they hurt, the plan's fallbacks are saving short keywords with each note, or revisiting embeddings.
