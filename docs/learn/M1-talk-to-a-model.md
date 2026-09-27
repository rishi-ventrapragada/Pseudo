# M1: Talk to a model

## The concept in one paragraph

A language model in the cloud is an **HTTP endpoint**: a URL that accepts requests. You **POST** (send) a piece of **JSON** (a text format for structured data) saying which model to use and a list of **messages**, each with a **role**: `system` sets the rules, `user` is you, and `assistant` is the model's earlier replies. It sends JSON back with the reply and a count of **tokens** (chunks of text, roughly ¾ of a word, which is how usage is measured and limited). The model is **stateless**: each request starts from zero and nothing is kept between calls. Every chat app that "remembers" does it by keeping the message list itself and re-sending the whole list every turn. M1 shows this three ways: by hand (01a), through an SDK (01b), and in a chat where you can switch the memory off (01c).

## Web-dev analogy

- **01a is a `fetch()` call.** `fetch(url, {method: "POST", headers: {Authorization: \`Bearer ${key}\`}, body: JSON.stringify(body)})`. The **Bearer token** in the header works like a Supabase key.
- **Status codes are ordinary REST codes:** 200 OK, 401 bad key, 429 rate limited.
- **The SDK (01b) is to this API what `supabase-js` is to PostgREST:** the same HTTP calls, wrapped in nicer functions with typed results.
- **Statelessness is like a serverless function with no session or cookies:** every request must carry everything it needs.
- **The history list is client-side state:** like a React app re-sending the whole cart on every checkout call because the server keeps no session.
- **Tokens and rate limits are metered usage,** like Vercel function invocations: here that means 30 requests/min, 1K requests/day, and 8K tokens/min on Groq's free plan.

## What was built (file by file)

- **`playground/01a_raw_http.py`**: one POST with `httpx2`. It prints the endpoint, the headers (key hidden), the full request JSON, status and timing, the rate-limit headers, the full response JSON, and the one field we wanted.
- **`playground/01b_sdk.py`**: the same question through `openai.OpenAI(base_url=..., api_key=...)`. It shows the typed object the SDK returns.
- **`playground/01c_memory.py`**: a terminal chat that keeps `history` in a list. `--no-history` sends only the latest message. It stops after 20 turns (`MAX_TURNS`).
- **`requirements.txt`**: adds `httpx2==2.13.1` and `openai==3.19.2`. pip also installed 12 packages those two depend on (pydantic, anyio, jiter...), and those aren't pinned. That's like a `package.json` with exact versions but no lockfile: your direct libraries are fixed, their sub-dependencies can drift.
- **`PRD.md`, `ARCHITECTURE.md`, `DECISIONS.md`**: one-line edits from `httpx` to `httpx2` (explained below).

**Why httpx2 and not httpx:** `httpx` hasn't released since 2024-12-06 ([PyPI: httpx](https://pypi.org/project/httpx/)). `httpx2` is its maintained continuation under the Pydantic team ([github.com/pydantic/httpx2](https://github.com/pydantic/httpx2)), and **openai 3.19.2 depends on it**. PyPI's metadata for [openai 3.19.2](https://pypi.org/project/openai/3.19.2/) lists `httpx2<3,>=2.12.0` in its `requires_dist` field (raw JSON: https://pypi.org/pypi/openai/3.19.2/json), the [openai-python README](https://github.com/openai/openai-python) says its clients are "powered by HTTPX2", and `pip show openai` in our venv prints `Requires: anyio, httpx2, jiter, pydantic, sniffio, typing-extensions`. So 01b makes its request with the same library 01a used directly.

## Walkthrough of the key code

**01a: the three parts of every model call**
```python
url = f"{base_url.rstrip('/')}/chat/completions"
headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
body = {"model": model, "messages": [{"role": "system", ...}, {"role": "user", ...}]}
response = httpx2.post(url, headers=headers, json=body, timeout=60)
```
`/chat/completions` is the standard path for every OpenAI-compatible provider, so only `base_url` changes between them. The key goes **only in the header**, never in the body. `json=body` turns the Python dict into JSON text for you.

**Keeping the key out of the output**
```python
safe_headers = {**headers, "Authorization": "Bearer <hidden>"}
def hide_key(text: str, api_key: str) -> str:
    return text.replace(api_key, "<hidden>")
```
We print a *copy* of the headers with the key swapped out. On top of that, every print goes through `show()` → `hide_key()`, so even if an API echoed the key back in an error, it would be blanked. The safety check sits right next to the output, not somewhere far away.

**01a: digging out the answer**
```python
data = response.json()                          # JSON text -> Python dict
answer = data["choices"][0]["message"]["content"]
```
`choices` is a list because the API *can* return several alternative replies. We ask for one, so we take item `[0]`.

**01b: the SDK version of the same thing**
```python
client = openai.OpenAI(base_url=base_url, api_key=api_key, max_retries=0, timeout=60)
completion = client.chat.completions.create(model=model, messages=messages)
answer = completion.choices[0].message.content
```
The SDK builds the URL, the headers, and the JSON, and turns the reply into a `ChatCompletion` object, so you get attributes with autocomplete instead of dict keys. It also turns error codes into Python exceptions (`AuthenticationError`, `RateLimitError`). By default it **silently retries** failed calls twice. `max_retries=0` turns that off so each printed request is exactly one real request.

**01c: the whole secret of "memory"**
```python
history = [{"role": "system", "content": SYSTEM_PROMPT}]
...
if use_history:
    history.append(user_message)
    messages = history                      # send EVERYTHING so far
else:
    messages = [history[0], user_message]   # send only system + this message
...
history.append({"role": "assistant", "content": reply})  # remember our own reply
```
That `if/else` is the entire difference between remembering and forgetting. The model is identical in both modes; the only thing that changes is what we send it.

**The reasoning field.** `gpt-oss-120b` is a **reasoning model**: before answering, it writes some private "thinking" text. Groq returns that text in an extra `message.reasoning` field next to `content` ([Groq reasoning docs](https://console.groq.com/docs/reasoning)). It isn't part of the standard OpenAI response shape, so our code never reads it. **Its tokens are not free.** They're counted inside `completion_tokens`, so they count toward your tokens-per-minute and tokens-per-day limits. In our 01a run, `completion_tokens_details.reasoning_tokens` was 8 of the 43 output tokens. A harder question means more thinking and more tokens.

## What happens when you run it (annotated real output, trimmed with ...)

**01a**
```
--- 4. RESPONSE STATUS ---
200 OK  (1.11 s)
--- 5. RATE-LIMIT HEADERS (your free-tier budget, live) ---
x-ratelimit-remaining-requests: 999      <- of 1000 per day
x-ratelimit-remaining-tokens: 7525       <- of 8000 per minute
--- 6. RESPONSE BODY (the full JSON we got back) ---
  "choices": [ { "message": { "role": "assistant",
        "content": "An API (Application Programming Interface) is a set of rules ...",
        "reasoning": "Need concise answer, one sentence." },     <- the model's thinking
      "finish_reason": "stop" } ],                                <- finished normally
  "usage": { "prompt_tokens": 97, "completion_tokens": 43, "total_tokens": 140,
    "queue_time": 0.486..., "completion_tokens_details": { "reasoning_tokens": 8 } },
  "x_groq": { "id": "req_01m3gt..." }, ...                        <- Groq-only extras
```
`id`, `choices`, `finish_reason`, and `usage` token counts are standard fields every provider sends. `x_groq`, `queue_time`, and `reasoning` are Groq extras, so code that relies only on the standard fields keeps working when you switch providers. Notice that the token budget dropped by 475, not 140: the rate limiter does its own accounting, so treat the header as the true remaining budget.

**01a with a bad key** (`$env:LLM_API_KEY="bad-key-for-test"`: a real shell variable beats `.env`, as noted in M0)
```
401 Unauthorized  (0.34 s)
{"error":{"message":"Invalid API Key","type":"invalid_request_error","code":"invalid_api_key"}}
```
**01b**: `Python type: ChatCompletion`. It sent the same 97 prompt tokens as 01a, because it's the same request.

**01c, history ON vs OFF** (input was piped in, so your typing isn't echoed after `you>`)
```
ON,  turn 2: --- SENDING TO MODEL: 4 messages ---
               [system] ... [user] Remember this number: 42.
               [assistant] Got it—I'll keep 42 in mind.
               [user] What number did I ask you to remember?
             --- MODEL REPLY (tokens: 124 in, 44 out) ---     <- 95 in on turn 1: history costs tokens
             assistant> You asked me to remember the number 42.

OFF, turn 1: assistant> Got it—I'll keep the number 42 in mind.   <- a promise it cannot keep
OFF, turn 2: --- SENDING TO MODEL: 2 messages (history OFF) ---
             assistant> You didn't give me a number to remember.
```

## Try this

1. **Change the rules.** In `01a_raw_http.py`, set `SYSTEM_PROMPT = "Answer like a pirate."` and rerun it. Watch the request body and the reply both change. Then try asking your own question: `python playground/01a_raw_http.py "Why is the sky blue?"`
2. **Half a memory.** In `01c_memory.py`, comment out the `history.append({"role": "assistant", ...})` line. Say "Remember 42", then ask "What exactly did you reply to me last time?". The model remembers what *you* said but not what *it* said, because it only knows what's in the list.
3. **Swap the brain.** In `.env`, set `LLM_MODEL=openai/gpt-oss-20b` and rerun 01a. Compare the speed and the token counts. No code changes. Set it back afterwards.

## Check yourself

1. In `--no-history` mode the model said "Got it" and then forgot. Why?
2. On turn 5 of a history-ON chat, how many messages are sent, and which roles are they?
3. Prompt tokens went from 95 to 124 between turns. Why, and why does that matter on a free tier?
4. Name three things the SDK does for you that 01a does by hand. Where does the API key travel in the request?
5. What is the `reasoning` field, and does it cost you anything?

<details>
<summary>Answers</summary>

1. The model is stateless: it keeps nothing between requests. On turn 2 we sent only the system prompt and the new question, so from the model's side "42" never happened. The "Got it" was just text it generated; it has no way to store anything.
2. 10 messages: 1 `system`, then 4 `user` and 4 `assistant` from turns 1–4, then the new `user` message. Turn *n* sends 2*n* messages.
3. The whole history is re-sent every turn, so the prompt grows with every exchange. You pay tokens for the entire conversation on every call, which uses up the 8K tokens/min and 200K tokens/day limits faster and eventually runs into the context window (the most text a model can read at once).
4. Builds the URL, adds the headers, converts dicts to JSON and back, turns replies into typed objects, turns error codes into exceptions, and retries by default. The key travels in the `Authorization: Bearer ...` **header**, never in the JSON body.
5. It's the reasoning model's private thinking before the answer, which Groq returns as an extra field. Yes, it costs: reasoning tokens are counted in `completion_tokens` and count toward your rate limits.

</details>

## How this connects to Pseudo's final architecture

- **The `messages` list is the agent's working memory.** In M2 the model's tool requests and your tool results get appended to this same list, and M3's agent loop grows it on every step. Hermes and Claude Code manage this same kind of list (plus tricks like summarizing old turns).
- **`base_url` + `LLM_MODEL` is the swappable brain (D10/D11).** Groq today; OpenRouter, Hermes' API server, or a local Ollama tomorrow, all by editing `.env`.
- **`hide_key` next to the output** is the first small version of Pseudo's rule that privacy checks sit next to the data they protect (Phase 4's redaction layer).
- **`MAX_TURNS`** is a first taste of the max-iterations cap every Pseudo agent loop must have.
