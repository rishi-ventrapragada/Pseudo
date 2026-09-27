# M2: Tool calling

## The concept in one paragraph

A model can only produce text, but it can produce text in a special shape that says "please run this function with these arguments". That's **tool calling** (also called function calling). You describe each tool in the request: a name, a description of when to use it, and a **JSON Schema** (a standard format for describing what a JSON value must look like) for its arguments. If the model decides it needs the tool, its reply contains **`tool_calls`** instead of an answer. *Your program* runs the real Python function, adds the result to the conversation as a message with role **`tool`**, and calls the model again. The model reads that result and writes the final answer. At no point does the model execute anything. It writes a request, your code decides whether and how to carry it out, and the model only ever sees the string you send back.

## Web-dev analogy

- **The model dispatches an action; your code is the reducer.** Like Redux: a component dispatches `{type: "get_current_time", payload: {timezone: "Asia/Tokyo"}}` but never touches state itself; the reducer does the work. The model is the component, and `TOOL_FUNCTIONS` plus `run_tool_call` are the reducer.
- **JSON Schema is like a TypeScript interface or Zod schema** for the function's arguments.
- **The tool's `description` is API documentation that the model reads** to decide *when* to call the tool, much like OpenAPI docs for a human developer.
- **`tool_call_id` is like a request ID:** it ties each async result back to the request that asked for it.
- **Two round trips per question,** like an OAuth redirect: the first response says "go do X", then you come back with X's result.

## What was built (file by file)

- **`playground/02_one_tool.py`** (198 lines) contains:
  - `get_current_time()`: the real function.
  - `GET_CURRENT_TIME_TOOL`: its schema, in standard OpenAI format.
  - `TOOL_FUNCTIONS`: the lookup table from tool name to function.
  - `run_tool_call()`: parses the arguments and runs the function safely.
  - `assistant_to_dict()`: keeps only standard fields.
  - `main()`: the two-call flow, printing every step and the growing `messages` list.
- **`requirements.txt`**: adds `tzdata==2026.4`. Windows has no built-in timezone database, so without it `ZoneInfo("Asia/Tokyo")` raises `ZoneInfoNotFoundError`.
- **`PRD.md`, `ARCHITECTURE.md`, `DECISIONS.md`**: the journal was removed, and `docs/journal.md` was deleted.

## Walkthrough of the key code

**1. The tool is plain Python, with no model code in it**
```python
def get_current_time(timezone: str | None = None) -> str:
    if timezone:
        try:
            now = datetime.now(ZoneInfo(timezone))
        except (ZoneInfoNotFoundError, ValueError, OSError):
            return f"Error: unknown timezone {timezone!r}. Use an IANA name like 'Asia/Tokyo'."
```
It checks its own input. `"Mars/Base"`, `"../etc"` and `"Asia"` all return an error *string* instead of crashing, so the model is told what went wrong. It only reads the clock, so there's no approval gate (CLAUDE.md §6 only requires one for tools that write, delete, or run things).

**2. The schema is all the model ever sees**
```python
"name": "get_current_time",
"description": "Get the current date and time. Call this whenever the user asks what time or date it is...",
"parameters": {"type": "object",
               "properties": {"timezone": {"type": ["string", "null"], "description": "IANA timezone name..."}},
               "required": [], "additionalProperties": False}
```
The model never sees the Python code. `"required": []` means no argument is mandatory. `"additionalProperties": False` means "don't invent other arguments".

**3. Tools go along with every request**
```python
return {"model": model, "messages": messages, "tools": [GET_CURRENT_TIME_TOOL], "tool_choice": "auto"}
...
client.chat.completions.create(**request)   # ** spreads the dict, like JS ...
```
`tool_choice: "auto"` lets the model decide whether to use a tool. The model is stateless (M1), so the tool list has to be re-sent on the second call too.

**4. Two possible replies, one `if`**
```python
if not reply.message.tool_calls:
    ...  # MODEL ANSWERED DIRECTLY: done, one call
```
**`finish_reason`** says why the model stopped writing: `"stop"` means it finished an answer, and `"tool_calls"` means it wants a tool run.

**5. Running the tool: the model's JSON string becomes a real Python call**
```python
function = TOOL_FUNCTIONS.get(name)          # name -> real function (a "dispatch table")
kwargs = json.loads(arguments or "{}")       # '{"timezone":"Asia/Tokyo"}' -> dict
return function(**kwargs)                    # get_current_time(timezone="Asia/Tokyo")
```
`arguments` arrives as a *string* of JSON that the model wrote, so it can be malformed. Bad JSON, unknown tool names, and unexpected arguments like `{"city": "Paris"}` all come back as `"Error: ..."` strings.

**6. The tool-result message**
```python
tool_message = {"role": "tool", "tool_call_id": call.id, "content": result}
```
Every tool call in the reply needs one of these, with a matching id. Groq's own example also adds a `"name"` field, but their compatibility page says `messages[].name` is unsupported. We use the standard OpenAI shape, and the real run showed Groq accepts it.

**7. Keeping the history portable**
`assistant_to_dict()` copies only `role`, `content`, and `tool_calls` into `messages`. The SDK object also carries Groq's extra `reasoning` field, which another provider might reject (D11).

## What happens when you run it (annotated real output, trimmed with ...)

**Tokyo** (`python playground/02_one_tool.py`)
```
--- STEP 2: MODEL REPLY (finish_reason = "tool_calls") ---
{ "role": "assistant",
  "tool_calls": [{ "id": "fc_f39e3813-...", "type": "function",
                   "function": { "name": "get_current_time", "arguments": "{\"timezone\":\"Asia/Tokyo\"}" } }],
  "reasoning": "We need to call get_current_time with timezone \"Asia/Tokyo\"." }
                                  <- no "content": it's null, and our print skips empty fields
--- messages now: 3 ---           <- the model's request is now part of the history
--- STEP 3: RUNNING TOOL LOCALLY (our Python, on this laptop) ---
get_current_time(**{"timezone":"Asia/Tokyo"}) -> 'Sunday 27 September 2026, 16:30:11 JST (UTC+0900)'
--- STEP 4: SENDING TO MODEL: 4 messages + 1 tool (tools re-sent: the model is stateless) ---
  [tool] result for fc_f39e3813-...: Sunday 27 September 2026, 16:30:11 JST (UTC+0900)
--- STEP 5: FINAL ANSWER (finish_reason = "stop") ---
assistant> It’s currently 16:30 JST (UTC+9) on Sunday, 27 September 2026.
Tokens: call 1 = 250, call 2 = 283
```
The id is just an opaque label (Groq's start with `fc_`); your code only echoes it back. Windows' own clock said 16:30:12 in Tokyo, so the tool was right, and the model repeated it faithfully.

**France** (`"What is the capital of France?"`): the same request with the tool offered. The reply was `finish_reason = "stop"`, content `"Paris is the capital of France."`, then `No tool was run. 1 model call total (244 tokens).` The model decided the tool was irrelevant.

**A real failure, and its fix** (`"What time is it?"`). The first version of the schema said `"type": "string"`, and the call failed:
```
Error code: 400 - {'error': {'message': "... parameters for tool get_current_time did not match schema:
  errors: [`/timezone`: expected string, but got null]", 'code': 'tool_use_failed',
  'failed_generation': '{"name": "get_current_time", "arguments": {"timezone": null}}'}}
```
The model tried to say "no timezone" with `null`, and Groq **checked the model's tool call against our schema on its servers** and rejected it. The Python function already accepted `str | None`, but the schema didn't match it. Changing the schema to `"type": ["string", "null"]` fixed it: `{"timezone":null}` returned `13:01:10 India Standard Time (UTC+0530)`. The lesson: **the schema is a contract, and it has to describe what your function really accepts.**

## Try this

1. **Make the tool lie.** In `get_current_time`, put `return "Monday 1 January 2001, 03:00:00 UTC"` as the first line and ask the Tokyo question. The model will very likely tell you it's 2001: it has no clock of its own, it only knows the string your code sent. This is the proof that the program runs the code, not the model.
2. **Ask for two things.** `python playground/02_one_tool.py "What time is it in Tokyo and in London?"`. Groq sends one call per reply by default, so you'll probably see `MODEL WANTS ANOTHER TOOL CALL` and M2 stopping, which is exactly why M3 needs a loop. If both calls arrive in one reply instead, the `for` loop in steps 3–4 answers both.
3. **Break the description.** Change the tool's `description` to `"Returns a random number."` and ask the Tokyo question. The model will likely stop calling it, because it chooses tools by reading their descriptions.

## Check yourself

1. Who runs `get_current_time`: the model, Groq, or your laptop?
2. What does the model literally output when it "calls" a tool?
3. Why are the tools sent again on the second call?
4. What is `tool_call_id` for?
5. How does the code know that "What is the capital of France?" didn't need the tool?

<details>
<summary>Answers</summary>

1. Your laptop. `run_tool_call` calls the Python function in our process, between the two model calls. The model only receives the result string. Try-this #1 proves it.
2. JSON text: a `tool_calls` list with an id, the function name, and `arguments` as a JSON *string*, e.g. `"{\"timezone\":\"Asia/Tokyo\"}"`. It's a request, not an action.
3. The model is stateless. Each call starts from zero, so it only knows about tools listed in *that* request.
4. It pairs each tool result with the request that asked for it, so the model knows which answer belongs to which call. Every call in a reply needs one `tool` message with its id, or the next request is rejected.
5. The reply had no `tool_calls` (and `finish_reason` was `"stop"`). The model made that decision after reading the tool's description; the code just checks whether `tool_calls` is present.

</details>

## How this connects to Pseudo's final architecture

- **M3 = steps 2–4 in a loop.** Keep calling the model while it asks for tools, with a max-iterations cap. The **approval gate** goes exactly between "MODEL WANTS TO CALL TOOL" and "RUNNING TOOL LOCALLY", because that's where your code decides what actually happens.
- **The schema format carries over.** An MCP tool (Phase 2) is published as the same trio: name, description, and a JSON Schema for its input. Pseudo Hands tools like `list_open_windows` will be plain functions plus schemas, just like this one (D11).
- **Checks live in the tool.** `get_current_time` validates its own input, so it's safe no matter which brain calls it.
- **Tool results leave your laptop.** Whatever `run_tool_call` returns is sent to the cloud model. Here it's only the time, but in Phase 4 the privacy layer sits on exactly this path, redacting screen text before it becomes a `tool` message.
