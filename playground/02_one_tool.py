"""M2: one tool call, with every step visible.

What it demonstrates: "tool calling" is a message protocol, not magic. We
describe a Python function to the model as JSON; the model can reply with a
*request* to call it; OUR program runs it and sends the result back; then the
model writes the final answer. The model never runs code, it only writes text.

Concepts: tool definitions (JSON Schema), tool_calls, tool_call_id, the "tool"
role, finish_reason, and why the tools are re-sent on every call.

Run it:  python playground/02_one_tool.py
         python playground/02_one_tool.py "What is the capital of France?"
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import openai
from dotenv import load_dotenv
from openai.types.chat import ChatCompletion, ChatCompletionMessage

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
SYSTEM_PROMPT = "You are a concise assistant. Answer in one or two short sentences."
DEFAULT_QUESTION = "What time is it in Tokyo right now?"


def get_current_time(timezone: str | None = None) -> str:
    """THE TOOL: plain Python that knows nothing about models. Read-only (it just
    reads the clock), so no approval gate. Bad input -> an error message, not a crash."""
    if timezone:
        try:
            now = datetime.now(ZoneInfo(timezone))
        except (ZoneInfoNotFoundError, ValueError, OSError):
            return f"Error: unknown timezone {timezone!r}. Use an IANA name like 'Asia/Tokyo'."
    else:
        now = datetime.now().astimezone()
    return f"{now:%A %d %B %Y, %H:%M:%S} {now.tzname()} (UTC{now:%z})"


# THE TOOL'S DESCRIPTION (standard OpenAI tool format). This dict is ALL the model knows
# about the tool: a name, when to use it, and a JSON Schema for its arguments. Never the code.
GET_CURRENT_TIME_TOOL = {
    "type": "function",
    "function": {
        "name": "get_current_time",
        "description": "Get the current date and time. Call this whenever the user asks what time or date it is, anywhere in the world.",
        "parameters": {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": ["string", "null"],  # null = local time, matching `str | None` above
                    "description": "IANA timezone name, for example 'Asia/Tokyo', 'Europe/London' or 'UTC'. Use null or leave it out to get the user's local time.",
                }
            },
            "required": [],
            "additionalProperties": False,
        },
    },
}

# The name the model asks for -> the Python function we actually run.
TOOL_FUNCTIONS = {"get_current_time": get_current_time}


def load_config() -> tuple[str, str, str]:
    """Read the three LLM_* settings from .env, or stop with a clear message."""
    load_dotenv(ENV_PATH)
    base_url, api_key, model = (os.getenv(n) for n in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"))
    if not (base_url and api_key and model):
        sys.exit("Missing LLM_BASE_URL, LLM_API_KEY or LLM_MODEL. Run playground/00_check_setup.py")
    return base_url, api_key, model


def show(title: str, text: str, api_key: str) -> None:
    """Print one labelled step. Every print goes through here, so the key is always blanked."""
    print(f"\n--- {title} ---")
    print(text.replace(api_key, "<hidden>"))


def describe(message: dict) -> str:
    """One readable line per message, like 01c, plus the two tool shapes."""
    if message.get("tool_calls"):
        calls = [f"{c['function']['name']}({c['function']['arguments']})  (id {c['id']})"
                 for c in message["tool_calls"]]
        return "  [assistant] wants to call " + ", ".join(calls)
    if message["role"] == "tool":
        return f"  [tool] result for {message['tool_call_id']}: {message['content']}"
    return f"  [{message['role']}] {message['content']}"


def show_messages(title: str, messages: list[dict], api_key: str) -> None:
    show(title, "\n".join(describe(m) for m in messages), api_key)


def build_request(model: str, messages: list[dict]) -> dict:
    """Everything one call sends. Tools go EVERY time: the model keeps nothing between calls."""
    return {"model": model, "messages": messages, "tools": [GET_CURRENT_TIME_TOOL], "tool_choice": "auto"}


def ask_model(client: openai.OpenAI, request: dict, api_key: str) -> ChatCompletion | None:
    try:
        return client.chat.completions.create(**request)  # ** spreads the dict, like JS ...
    except openai.APIError as error:  # bad key, rate limit, network, rejected request
        show("ERROR FROM PROVIDER", str(error), api_key)
        return None


def run_tool_call(name: str, arguments: str) -> str:
    """Run the function the model asked for. Any problem becomes an error string."""
    function = TOOL_FUNCTIONS.get(name)
    if function is None:
        return f"Error: there is no tool called {name!r}."
    try:
        kwargs = json.loads(arguments or "{}")  # the model sends arguments as a JSON *string*
        return function(**kwargs)
    except (json.JSONDecodeError, TypeError) as error:
        return f"Error: bad arguments for {name}: {error}"


def assistant_to_dict(message: ChatCompletionMessage) -> dict:
    """Keep only standard fields (drops Groq's extra "reasoning") so any provider accepts it."""
    result = {"role": "assistant", "content": message.content}
    if message.tool_calls:
        result["tool_calls"] = [
            {"id": c.id, "type": "function",
             "function": {"name": c.function.name, "arguments": c.function.arguments}}
            for c in message.tool_calls
        ]
    return result


def main() -> int:
    base_url, api_key, model = load_config()
    client = openai.OpenAI(base_url=base_url, api_key=api_key, max_retries=0, timeout=60)
    question = " ".join(sys.argv[1:]) or DEFAULT_QUESTION
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": question}]

    # STEP 1: same request as 01a, plus "tools" and "tool_choice".
    request = build_request(model, messages)
    show("STEP 1: FULL REQUEST BODY (with the tool definition)", json.dumps(request, indent=2), api_key)
    show_messages(f"STEP 1: SENDING TO MODEL: {len(messages)} messages + 1 tool", messages, api_key)
    first = ask_model(client, request, api_key)
    if first is None:
        return 1

    # STEP 2: the reply is EITHER text (done) OR a request to run a tool.
    reply = first.choices[0]
    show(f'STEP 2: MODEL REPLY (finish_reason = "{reply.finish_reason}")',
         json.dumps(reply.message.model_dump(exclude_none=True), indent=2), api_key)
    if not reply.message.tool_calls:
        show("MODEL ANSWERED DIRECTLY (no tool needed)",
             f"assistant> {reply.message.content}\n\n"
             f"No tool was run. 1 model call total ({first.usage.total_tokens} tokens).", api_key)
        return 0

    messages.append(assistant_to_dict(reply.message))
    wanted = "\n".join(f"{c.function.name}({c.function.arguments})" for c in reply.message.tool_calls)
    show("MODEL WANTS TO CALL TOOL",
         f"{wanted}\n(the arguments are a JSON string the model wrote)\n"
         "The model has not run anything. It only wrote this request.", api_key)
    show_messages(f"messages now: {len(messages)}", messages, api_key)

    # STEPS 3-4: run each requested tool HERE, then add one "tool" message per
    # call. Every tool_call id needs an answer, or the next request is rejected.
    for call in reply.message.tool_calls:
        result = run_tool_call(call.function.name, call.function.arguments)
        show("STEP 3: RUNNING TOOL LOCALLY (our Python, on this laptop)",
             f"{call.function.name}(**{call.function.arguments}) -> {result!r}", api_key)
        tool_message = {"role": "tool", "tool_call_id": call.id, "content": result}
        messages.append(tool_message)
        show("STEP 4: TOOL RESULT MESSAGE WE SEND BACK", json.dumps(tool_message, indent=2), api_key)

    show_messages(f"STEP 4: SENDING TO MODEL: {len(messages)} messages + 1 tool "
                  "(tools re-sent: the model is stateless)", messages, api_key)
    second = ask_model(client, build_request(model, messages), api_key)
    if second is None:
        return 1

    final = second.choices[0]
    if final.message.tool_calls:
        again = ", ".join(f"{c.function.name}({c.function.arguments})" for c in final.message.tool_calls)
        show("MODEL WANTS ANOTHER TOOL CALL", f"{again}\nM2 stops after one round. "
             "Repeating steps 2-4 in a loop is exactly what M3 builds.", api_key)
        return 0

    messages.append(assistant_to_dict(final.message))
    show(f'STEP 5: FINAL ANSWER (finish_reason = "{final.finish_reason}")', f"assistant> {final.message.content}", api_key)
    show_messages(f"FINAL CONVERSATION: {len(messages)} messages", messages, api_key)
    print(f"\nTokens: call 1 = {first.usage.total_tokens}, call 2 = {second.usage.total_tokens}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
