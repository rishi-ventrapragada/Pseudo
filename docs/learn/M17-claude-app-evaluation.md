# M17: Can the Claude desktop app be Pseudo's face and brain? (evaluation)

## The concept in one paragraph

M17 asked whether the **Claude desktop app** could replace our planned React face (M18): chat in the app, and let it use `pseudo_hands` as a **local MCP server** (a tool server the app starts on this laptop). As in M13, we audited before trusting. We used the app's own code (Electron apps ship their JavaScript in an `app.asar` archive), its settings files, its logs, and fake-data windows, and printed only names, counts and yes/no answers. The app can run `pseudo_hands` on the subscription. But it also keeps a **device link** to Anthropic's servers that passes local MCP tools on to remote sessions (phone, claude.ai, cloud). Nothing in the app's settings switched it off. The pass rules, written before measuring, therefore recommend the own face, M18.

## Web-dev analogy

- **Local MCP server in the app:** like adding a local API route to a desktop app's config. The app starts it and calls it.
- **The device link:** like a tunnel service (ngrok) that the app opens by itself. It publishes your local routes to the internet, and a server-side feature flag decides whether it runs, not a setting in your app.
- **`+3 local-mcp`:** like a tunnel dashboard that says "3 routes now public".
- **The self-read problem:** like `document.activeElement` returning the search box you just clicked, instead of the thing you were looking at before.

## What was built (file by file)

- **In the repo:** no code. The PRD, ARCHITECTURE, DECISIONS and README now describe M17 as this evaluation and M18 as the face; the code comments were renumbered; and this lesson.
- **Outside the repo, tried and then put back:**
  - `pseudo_hands` was added to the app's `claude_desktop_config.json` twice.
  - Computer use and the sessions-bridge flag were switched off once.
  - After each test, everything went back from backups in `%LOCALAPPDATA%\Pseudo\backups\`.
- **Kept, as you approved:** `C:\dev\Pseudo` is in the app's `remoteControlExcludedFolders`. Claude Code's own trust for this repo is unchanged.
- **Scratchpad, not committed:**
  - `m17_asar.py`: searches the app's code and interface strings;
  - `m17_pick.py` and `m17_windows.ps1`: the self-read test, with a notes window that is *not* always on top.

## Walkthrough of the key code (the app's own code)

**1. The config the app really reads.** The app is an MSIX package, and Windows redirects its `%APPDATA%` into `...\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\`. Editing `%APPDATA%\Claude\claude_desktop_config.json` does nothing.

**2. Computer use is `chicagoEnabled`.** Its default is `chicagoEnabled:!1` (false). On this laptop it was `true`. Changing it triggers `reloadRemoteToolsDevice("cu_preference_change")`: computer use is offered over the device link.

**3. What turns the device link on** (`Zia()`):
```js
if(!Uia.isBlocked()&&zj("dramatic_shrimp"))return"cowork_remote"; ... zj("marble_heron") ... return"chatwork"
```
`zj(...)` reads **server-side feature flags**, and `isBlocked()` checks policy blocks (for example HIPAA). No preference from the Settings page appears here, which is why switching off computer use and the sessions-bridge flag didn't stop the link.

**4. What the link offers remote sessions.** From one log line:
```
connecting DO bridge with: get_device_info, device_list_dir, device_stage_files, ..., computer_screenshot,
  ..., computer_read_clipboard, ..., <browser>__get_page_text, <browser>__javascript_tool, ...
  (+0 grand-prix, +0 local-mcp, +0 direct-mcp)
```
`local-mcp` counts the local MCP tools it passes on. That count is how Pseudo's exposure was measured.

**5. Remote Control's folder list** (`rc-serve`): served folders = registered folders minus `remoteControlExcludedFolders`. Claude Code's `hasTrustDialogAccepted` is only read, so excluding a folder doesn't change Claude Code.

## What happens when you run it (real output, annotated)

**`pseudo_hands` in the app:**
```
billing check: CLEAN | outranking credentials set: none | login: claude.ai / firstParty / plan pro
[pseudo_hands] Server started and connected successfully      <- the handshake took ~8 s (Presidio)
23:31:40 (+0 grand-prix, +0 local-mcp, +0 direct-mcp)
23:31:41 (+0 grand-prix, +3 local-mcp, +0 direct-mcp)         <- Pseudo's 3 tools now reachable remotely
```

**With computer use and the sessions-bridge flag off, after a restart:**
```
chicagoEnabled = False | bridge enabled = [False]              <- the app did NOT switch them back
23:43:20 (+0 grand-prix, +3 local-mcp, +0 direct-mcp) | computer_screenshot offered: True
```
Both times the app was closed within about 1-2 minutes. Its MCP log shows only `initialize` and `tools/list`, and **no `tools/call`**: nothing used Pseudo's tools. Because the tools were reachable, the six-question chat tests were **not run**, as you'd instructed.

**Self-read.** The notes window was *not* always on top, and the Claude app was brought to the front last:
```
target -> notes -> Claude app | today's pick_window reads: claude.exe | skipping claude.exe reads: our NOTES window
notes -> target -> Claude app | today's pick_window reads: claude.exe | skipping claude.exe reads: our TARGET window
```
The same result in 2 rounds: 4 out of 4. Windows keeps windows in the order they were last active, so skipping the face's program leads to the window you were on.

## The criteria (fixed before measuring) and the recommendation

| Criterion | Result |
|---|---|
| F1: a route around the redactor that you can't switch off, or whose off state doesn't hold | **Not cleared.** The device link runs regardless of settings (server-side flags). With computer use off, it still listed `computer_screenshot`; whether the tool would actually work wasn't tested. |
| F2: `pseudo_hands` loads on the subscription | **Pass** (claude.ai Pro, no API key) |
| F3: the native popup works with the app | **Not measured** (tests stopped because of the exposure) |
| F4: a core fix makes `pick_window` read the window you were on | **Pass**: skipping `claude.exe` works, 4/4 |
| F5: the app sends screen content on its own | **Pass on the records**: window-context dictation is off (its default) |
| M1 (the six questions) and M2 (read question speed) | **Not measured** |
| Soft signal (you asked for it to be scored this way, like M13's Bot Chat) | The app as face is only safe while its device link is off, and **no local setting keeps it off**. Pseudo's tools would be reachable from phone, claude.ai and cloud sessions whenever the app runs with `pseudo_hands`. |

**Recommendation: build the own React face (M18).** The rule needed no hard failure *and* M1 and M2 passing. M1 and M2 couldn't be measured safely, F1 isn't cleared, and the soft signal can't be switched off. `pseudo_hands` stays out of the Claude app. Claude Code (D16), launched with `--strict-mcp-config` and `--tools ""`, remains the way to use Claude with Pseudo.

## Try this

1. In the app's log (`%LOCALAPPDATA%\Claude\logs\main.log`), search for `connecting DO bridge with:` and read the `(+N local-mcp)` at the end of the line.
2. In the app, open Settings > General and look for "Computer use". Compare its state with `chicagoEnabled` in the config file under the package folder.
3. Put any window in front, then click into VS Code. In the venv, run `python -c "from pseudo_hands.core.active_window import pick_window; print(pick_window().app)"`. That prints only the app name, and it shows today's self-read.

## Check yourself

1. Why did editing `%APPDATA%\Claude\claude_desktop_config.json` look right but change nothing?
2. Why wasn't switching off computer use enough to stop Pseudo's tools being reachable remotely?
3. Why were the chat tests not run, even though the fake windows were ready?
4. Why does skipping `claude.exe` read the window you were on, and not just any window?
5. Why is the self-read fix a `pseudo_hands` core change rather than a face change?

<details>
<summary>Answers</summary>

1. The app is an MSIX package: Windows quietly redirects its `%APPDATA%` into a folder inside `LocalAppData\Packages\`. The app never reads the other copy.
2. The device link that passes on local MCP tools is turned on by server-side feature flags (`Zia()`), not by computer use or the sessions-bridge flag. The measured line said `+3 local-mcp` with both off.
3. The agreed condition was `+0 local-mcp` before any test. Asking questions while Pseudo's tools were reachable from remote sessions would have meant testing with a door open.
4. Windows keeps windows in the order they were last active. Your switch put Claude on top, so the next one down is the window you just left. Tested in both window orders.
5. D11: every face (the terminal, M18's window, any other client) calls the same `read_active_window`. Fixing it once in core, with an owner-editable list of assistant apps, fixes it for all of them.
</details>

## How this connects to Pseudo's final architecture

- **M18 builds the own face.** Its first step is the self-read fix in `pseudo_hands` core: an owner-editable `assistant_apps.txt` (`hermes.exe`, `claude.exe`, and the face's own program), tested with a window that is not always on top.
- **Outside Pseudo:** on this laptop, the Claude app's device link offers remote sessions screenshots, clipboard and file tools while computer use is on. That's worth knowing whether or not Pseudo uses the app.
