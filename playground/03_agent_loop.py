"""M3: a mini agent. M2's single tool round, repeated in a loop until done.

What it demonstrates: an "agent" is a while-loop around a model call. Each
iteration sends the whole history plus the tool list. If the model asks for
tools, we run them (writes need your approval) and append the results. If it
answers in plain text, we stop. A hard cap (MAX_ITERATIONS) means it ALWAYS ends.

Concepts: the agent loop, iteration caps, the approval prompt, rate limits
(429 + retry-after), and why each iteration costs more tokens than the last.

Run it:  python playground/03_agent_loop.py "create a notes.md with three study tips, then add a fourth"
         python playground/03_agent_loop.py            (it asks for the task)
"""

import os
import sys
import time
from collections.abc import Callable
from pathlib import Path

import openai
from dotenv import load_dotenv
from openai.types.chat import ChatCompletion, ChatCompletionMessage

import agent_tools
from agent_tool_schemas import TOOL_SCHEMAS

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
MAX_ITERATIONS = 10  # hard cap: one iteration = one model call (CLAUDE.md §6)
MAX_RATE_LIMIT_WAITS = 3  # per model call
LONGEST_WAIT_SECONDS = 60  # if the server wants us to wait longer than this, stop instead
PREVIEW_CHARS = 300  # how much of a long tool result we print (the model always gets all of it)
SYSTEM_PROMPT = (
    "You are a small file assistant. You can only use the tools list_files, read_file and "
    "write_file, and only inside a sandbox folder; paths are relative to it. Do the whole task "
    "yourself with the tools, step by step; never ask the user for permission in text. Calling "
    "write_file automatically shows the user a preview and asks them to approve it. If a write "
    "is denied, do not retry it, just tell the user. When the whole task is done, reply with a "
    "one or two sentence summary."
)


class StopAgent(Exception):
    """Something the loop can't recover from: bad key, oversized request, long rate limit."""


def load_config() -> tuple[str, str, str]:
    """Read the three LLM_* settings from .env, or stop with a clear message."""
    load_dotenv(ENV_PATH)
    base_url, api_key, model = (os.getenv(n) for n in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"))
    if not (base_url and api_key and model):
        sys.exit("Missing LLM_BASE_URL, LLM_API_KEY or LLM_MODEL. Run playground/00_check_setup.py")
    return base_url, api_key, model


def show(title: str, text: str, api_key: str) -> None:
    """Print one labelled step, with the key blanked out if it ever appears."""
    print(f"\n--- {title} ---")
    print(text.replace(api_key, "<hidden>"))


def shorten(text: str) -> str:
    """Long tool results are printed cut short. The model still receives all of it."""
    if len(text) <= PREVIEW_CHARS:
        return text
    return f"{text[:PREVIEW_CHARS]}... [{len(text) - PREVIEW_CHARS} more characters sent to the model]"


def terminal_approver(api_key: str) -> Callable[[str], bool]:
    """Build the terminal's approval prompt (a closure: a function that remembers api_key).
    agent_tools calls it from INSIDE write_file(). Only "y" or "yes" means yes."""
    def ask(preview: str) -> bool:
        show("APPROVAL NEEDED", preview, api_key)
        try:
            answer = input("Allow this write? [y/N] ").strip().lower()
        except EOFError:  # nobody at the keyboard counts as "no"
            answer = ""
        approved = answer in ("y", "yes")
        print(f"-> {'APPROVED' if approved else 'DENIED'} (you typed {answer!r})")
        return approved
    return ask


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


def call_model(client: openai.OpenAI, request: dict, api_key: str) -> tuple[ChatCompletion, dict]:
    """One model call, waiting out 429s the way the server asks.
    Returns the reply and the response headers (they carry the rate-limit budget)."""
    waits = 0
    while True:
        try:
            raw = client.chat.completions.with_raw_response.create(**request)
            return raw.parse(), dict(raw.headers)
        except openai.RateLimitError as error:  # 429: too many tokens/requests right now
            try:
                delay = float(error.response.headers.get("retry-after", 10))
            except ValueError:
                delay = 10.0
            waits += 1
            if waits > MAX_RATE_LIMIT_WAITS or delay > LONGEST_WAIT_SECONDS:
                raise StopAgent(f"still rate limited (429); the server wants {delay:.0f} s more") from None
            show(f"RATE LIMITED (429): waiting {delay:.0f} s, as the server asked "
                 f"(wait {waits} of {MAX_RATE_LIMIT_WAITS})", error.message, api_key)
            time.sleep(delay)
        except openai.APIStatusError as error:
            if error.status_code == 400 and error.code == "tool_use_failed":
                raise  # the model's own tool call broke the schema: the loop asks again
            if error.status_code == 413:
                raise StopAgent("this request is bigger than the tokens-per-minute limit; waiting won't help") from None
            raise StopAgent(f"{error.status_code}: {error.message}") from None
        except openai.APIConnectionError as error:
            raise StopAgent(f"network problem: {error}") from None


def run_agent(client: openai.OpenAI, model: str, task: str, api_key: str) -> int:
    """THE AGENT LOOP. Ends on a plain-text answer (0) or at MAX_ITERATIONS (1)."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": task}]
    total_tokens = 0
    iteration = 0
    while iteration < MAX_ITERATIONS:
        iteration += 1
        print(f"\n=== ITERATION {iteration} of {MAX_ITERATIONS} | "
              f"sending {len(messages)} messages + {len(TOOL_SCHEMAS)} tools ===")
        request = {"model": model, "messages": messages, "tools": TOOL_SCHEMAS, "tool_choice": "auto"}
        try:
            completion, headers = call_model(client, request, api_key)
        except openai.BadRequestError as error:  # 400 tool_use_failed (see call_model)
            show("MODEL WROTE AN INVALID TOOL CALL (400): asking again", error.message, api_key)
            continue

        usage = completion.usage
        total_tokens += usage.total_tokens
        print(f"tokens this call: {usage.prompt_tokens} in / {usage.completion_tokens} out | budget left "
              f"this minute: {headers.get('x-ratelimit-remaining-tokens', '?')} of "
              f"{headers.get('x-ratelimit-limit-tokens', '?')}")
        message = completion.choices[0].message
        messages.append(assistant_to_dict(message))

        if not message.tool_calls:  # plain text means the model thinks the task is done
            show(f"DONE after {iteration} iteration(s)", f"assistant> {message.content}\n\n"
                 f"{len(messages)} messages, {total_tokens} tokens in total.", api_key)
            return 0

        for call in message.tool_calls:
            show(f"MODEL WANTS TO CALL TOOL: {call.function.name}",
                 f"arguments: {shorten(call.function.arguments)}", api_key)
            # Runs locally. For write_file, the approval prompt appears from INSIDE the tool.
            result = agent_tools.run_tool(call.function.name, call.function.arguments)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
            show("TOOL RESULT (sent back to the model)", shorten(result), api_key)

    show(f"STOPPED: reached MAX_ITERATIONS = {MAX_ITERATIONS} without a final answer",
         f"{len(messages)} messages, {total_tokens} tokens used.", api_key)
    return 1


def main() -> int:
    base_url, api_key, model = load_config()
    # max_retries=0: no silent SDK retries. We handle 429s ourselves, visibly.
    client = openai.OpenAI(base_url=base_url, api_key=api_key, max_retries=0, timeout=60)
    agent_tools.approver = terminal_approver(api_key)  # plug the terminal into the approval gate
    task = " ".join(sys.argv[1:]) or input("task> ").strip()
    if not task:
        print("No task given.")
        return 1
    show("TASK", task, api_key)
    try:
        return run_agent(client, model, task, api_key)
    except StopAgent as reason:
        show("STOPPED", str(reason), api_key)
        return 1
    except KeyboardInterrupt:
        print("\nStopped by you.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
