# M41: The sidebar

## The concept in one paragraph

M41 turns the sidebar's flat list of saved chats into the mockup's: the chats grouped by day, a search box, and a "…" menu on each chat with Rename and Delete, plus the model picker at the bottom. The interesting part is the **delete**. A button that deletes a file is a door into your disk, so it is built so it can only reach the one file it was meant for. The window sends the brain a chat's **name**, never a path. The brain (`session_files.py`) then refuses anything that isn't plainly a chat Pseudo saved in its own folder. Around that: rename and delete are refused while a question runs, deleting the open chat starts a new one, and a warm Claude Code session (M32) that served the deleted chat is stopped.

## Web-dev analogy

**Sending a name, not a path** is `DELETE /chats/:id` instead of `DELETE /files?path=...`. A server that accepts a path is open to **path traversal**: a request for `../../secret`, where the `..` parts climb out of the folder you meant. Pseudo's ids are only ever a date and time like `20261010-091500-123`, so the brain checks the id against that shape before anything else.

**The four checks** are Supabase row-level security for files: even with a valid id, the server checks that this row really is yours before touching it.

**Reads and jobs** are like a form that is disabled while it submits, except the brain enforces it, not the button. Search is a GET, allowed any time. Rename and delete are mutations, one at a time.

**The 250 ms pause before searching** is a **debounce**: wait until typing stops, then send one request, not one per key.

**`found {text, items}`** echoes the search words back, like tagging a fetch with the query it was for. A slow reply for "boo" can't overwrite the results for "booking".

## What was built (file by file)

| File | What it does |
|---|---|
| `pseudo_brain/session_files.py` | `checked_file(name)`: the four checks. `rename_session`, `delete_session`, `search_sessions`. |
| `pseudo_brain/session.py` | `Session` keeps a `title` and saves it; `SESSION_NAME` accepts ASCII digits only. |
| `pseudo_brain/chat_sessions.py` | What a rename or delete means for the open chat and the warm session. |
| `pseudo_brain/bridge_sessions.py` | The bridge's chat messages: reads answered at once, rename and delete as jobs. |
| `face/src/groups.ts` | Today, Yesterday, Previous 7 days or Older, from the date in a chat's name. |
| `face/src/components/` | `SearchChats`, `ChatRow` (title, "…" menu, rename box), `DeleteChat` (the confirm), `ProviderPicker`. |
| `face/src/components/ui/` | `Menu` and `Popover`: thin wrappers on Radix, a library of unstyled, accessible parts. |
| Tests | `test_session_files.py`, `test_session_files_refusals.py`, `test_brain_bridge_chats.py`, `groups.test.ts`, `state-m41.test.ts`, `sidebar.test.tsx`. |

## Walkthrough of the key code

**1. The name must look like one Pseudo makes.** In `session.py`:

```python
SESSION_NAME = re.compile(r"[0-9]{8}-[0-9]{6}(-[0-9]{3})?")  # 20260930-231500-123
```

It used to say `\d`. In Python, `\d` matches *any* script's digits, so `٢٠٢٦١٠١٠-٠٩١٥٠٠` (Arabic-Indic digits) passed. That name is harmless today, but it's a name Pseudo never makes, so `[0-9]` closes it.

**2. The four checks, in order.** `checked_file` in `session_files.py`:

```python
if not isinstance(name, str) or not sessions.SESSION_NAME.fullmatch(name):
    raise SessionRefused("that is not a chat name Pseudo makes")
for part in (folder.parent, folder):
    if is_link(part):
        raise SessionRefused(f"the {part.name} folder is a link; Pseudo only changes chats in a real folder")
...
if is_link(path) or not stat.S_ISREG(info.st_mode) or info.st_nlink > 1:
    raise SessionRefused("that chat's file isn't a plain file Pseudo saved: it is a link, a hard link or a folder")
...
if data["started"] != name:
    raise ValueError("another chat's name")
```

Three kinds of link, all refused:
- A **symlink** is a signpost: a file or folder that points somewhere else.
- A **junction** is Windows' older signpost for folders. Both are **reparse points**, which is what `is_link` asks Windows about. If `sessions` were a junction to your Documents, "a file inside the sessions folder" would quietly mean a file in Documents.
- A **hard link** is not a signpost. It is a second name for the *same* file, so writing to one name changes the other. `st_nlink` counts the names a file has. A chat Pseudo saved has exactly one.

`fullmatch` (not `match`) means the whole name must fit, so `20261010-091500-123/x` fails. The last check means the file must read as a Pseudo chat whose own `started` is its name.

**3. Rename changes one field.** `rename_session` sets `data["title"]` and writes the rest back untouched. The live check compared every other field before and after. `clean_title` refuses empty names, names over 60 characters, and control characters (line breaks, tabs, invisible marks).

**4. A file change has consequences.** `chat_sessions.py`:

```python
title = delete_session(name)
if chat.warm is not None and chat.warm.conversation == name:
    await chat.warm.end("its chat was deleted")
was_open = chat.session.started == name
if was_open:
    chat.new_session()
```

The order matters: the file goes first, so a refused delete changes nothing at all. Renaming the open chat also sets `chat.session.title`, because the next save, after every question, rewrites the whole file.

**5. The brain enforces "not while busy".** In `bridge.py`, `rename_session` and `delete_session` joined `JOBS`, the messages that run one at a time. A job sent while a question runs is answered `busy: ...` and nothing happens. `list_sessions` and `search_sessions` are `READS`: answered at once. Each job ends with its own message (`renamed`, `deleted`), which tells the window it is free again.

**6. Search waits, and ignores stale replies.** `Sidebar.tsx` sends the search 250 ms after the last key. `state.ts` keeps `found` with its words, and the sidebar shows it only while the box still says them. Search reads titles and *your* messages, never the answers: it's about what you asked.

**7. A menu that opens for a screen reader too.** Radix opens its menu on a mouse *press* or a key, never on a bare click. But a screen reader's "activate", and Windows' UI Automation, send exactly that: a click with no press before it. `ui/Menu.tsx`:

```tsx
<RadixMenu.Trigger asChild onPointerDown={() => { pressed.current = true; }}
                   onClick={() => { if (!pressed.current) onOpenChange(!open); pressed.current = false; }}>
```

If a press came first, Radix has already handled it. If not, the click opens it.

## What happens when you run it (annotated real output)

The live check ran the packaged `Pseudo.exe` with a temporary folder of 8 fake chats:

```
GROUPS: {'Today': 3, 'Yesterday': 2, 'Previous 7 days': 2, 'Older': 1} (want 3, 2, 2, 1) | order newest first True
 search 'zebra': typed True | found ['What does the error say?'] | right True     <- "zebra" is only in a message
 search 'quokka': typed True | found [] | right True | 'No chats match' shown True
 rename 1: menu True | typed True | file title changed True | nothing else changed True | sidebar shows it True | top row shows it True
 delete 3: menu True | confirm shown True | Delete pressed True | file gone True | the others unchanged True | a new chat started True
PICKER: button says 'Questions go to Groq · gpt-oss-120b. Choose a model'
```

The refusals ran the brain alone, against decoy files outside its folder:

```
REFUSALS in a real folder: 17 of 17 refused | the real chat deleted True
  delete_session '..\\..\\..\\outside\\secret': refused - that is not a chat name Pseudo makes
  delete_session '20261001-080000-000': refused - that chat's file isn't a plain file Pseudo saved: it is a link, a hard link or a folder
REFUSALS, sessions folder a junction: ['refused', 'refused'] - the sessions folder is a link; Pseudo only changes chats in a real folder
DECOYS: 4 files, every one unchanged True
```

The second line is a *perfectly valid name* whose file is a hard link to a decoy. The name check alone would have let it through; the file check stopped it.

The first run crashed at the first rename. **That was the check script, not Pseudo.** It asked Windows to *Invoke* the "…" button, but a button that opens a menu (`aria-haspopup`) is offered as *Expand/Collapse* instead. Using Expand, as a real UI Automation client would, every step passed. The M15 battery scored 12/12.

## Try this (3 small experiments that break or change something)

1. In `pseudo_brain/session.py`, change `SESSION_NAME` back to `r"\d{8}-\d{6}(-\d{3})?"` and run `.venv\Scripts\python.exe -m pytest tests/test_session_files_refusals.py`. Exactly one case fails: the Arabic-Indic digits. Put it back.
2. In `pseudo_brain/session_files.py`, delete ` or info.st_nlink > 1` and run the same file. `test_a_linked_chat_file_is_refused[hard link]` fails: the rename went through and changed the decoy outside. Put it back.
3. In `face/src/groups.ts`, change `days <= 7` to `days < 7` and run `npx vitest run src/groups.test.ts` in `face\`. A chat from exactly 7 days ago drops to Older. Put it back.

## Check yourself

1. Why does the window send a chat's name and not its file path?
2. A junction and a hard link are both refused. What is different about the danger each one brings?
3. Why does the brain delete the file *before* stopping the warm session and starting a new chat?
4. Why is search allowed while a question runs, but rename is not?
5. The live check's first run said the menu couldn't be clicked. How did we know it was the script?

<details>
<summary>Answers</summary>

1. A path could point anywhere (`..\..\x`, `C:\Windows\...`). A name is checked against the one shape Pseudo makes, and the brain alone decides which folder it lives in.
2. A junction redirects a whole folder, so "inside the sessions folder" means somewhere else on the disk. A hard link is the same file under a second name, so changing the chat's file also changes the file elsewhere.
3. `delete_session` is where the refusals happen. If it refuses, nothing else has changed: the warm session and the open chat are left as they were.
4. Search only reads files. Rename writes the open chat's file, and so does a question when it saves, so they must not overlap. The brain's `JOBS` rule enforces that, whatever the window shows.
5. The error was in the script's own `invoke()`: the button exposed no Invoke action at all. Windows offered Expand/Collapse instead, because of `aria-haspopup`. With Expand, the menu opened every time.

</details>

## How this connects to Pseudo's final architecture

This is the M3 sandbox idea (one folder, resolve, refuse links) for the third time, after M3's file tools and M24's memory vault. It lives in the brain because the sessions folder is the brain's: the brain never imports `pseudo_hands` core (D11). The rules are in plain functions (`chat_sessions.py`), and the bridge only routes, so the terminal or any future interface gets the same checks. Building it showed a gap: the memory vault doesn't check `%LOCALAPPDATA%\Pseudo` itself for a link, which is now in the Backlog. M42 adds a memory browser and a status panel to this sidebar, reading notes through the M24 sandbox.
