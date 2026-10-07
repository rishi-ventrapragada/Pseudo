# M35: What running all day costs (evaluation)

## The concept in one paragraph

A program you leave running costs you even when you aren't using it: **CPU time** it burns while idle (battery, fan), and **memory** it holds that other programs can't have. M35 measured both for a hidden, idle Pseudo, and compared four ways of keeping it alive: everything running (A0), the brain started only when Pseudo is first shown (A1), the brain stopped again after a while (A2), and the page closed too (A3). The lesson inside the lesson is about **measuring**: "how much memory does it use?" has more than one honest answer, and the criteria, the rules and even the measuring script each needed care before the numbers meant anything.

## Web-dev analogy

- **A0 is a server that boots everything at start-up.** Simple, but a slow cold start, here paid at every sign-in.
- **A1 is lazy loading**, like `React.lazy` or a dynamic `import()`: don't load the heavy part until someone needs it, then keep it.
- **A2 is a serverless function that scales to zero**: no cost while idle, and a cold start (7 to 8 seconds here) on the next request.
- **A3 is also unmounting the page**: smallest when idle, but all the page's state is gone when you come back.
- **CPU-seconds are like billed compute time**: not "how busy is it right now" but "how much work did it do in total over ten minutes".
- **USS against committed memory is like RAM in use against RAM reserved.** A container may reserve 600 MB and touch 250; the operating system may then page most of that out while it sleeps.

## What was built (file by file)

Nothing in Pseudo changed. The repo got the measuring rules and the result (PRD), a README line, and a new paragraph in D27. Everything else lived in the scratchpad and is deleted:

- **`m35-main.js`:** a copy of `face/main.js` with the four candidates switchable, plus a tray icon and a signal folder (drop a file named `show`, `hide` or `quit` in it).
- **`m35_setup.mjs`:** makes a temporary copy of Pseudo.exe that starts from that file, and builds a second copy of the page with one extra state for A2.
- **`m35_lib.py`:** starts a candidate and samples its whole process tree every 5 seconds.
- **`m35_checks.py`:** the hands-off checks (I3, I4, I5). **`m35_measure.py`:** the idle windows (I1, I2, I6).

## Walkthrough of the key code

**1. Four candidates, four flags** (`m35-main.js`):
```js
const LAZY = MODE !== 'A0';
const SLEEPS = MODE === 'A2' || MODE === 'A3';
const CLOSES = MODE === 'A3';
```
Each candidate is the previous one plus one idea. That is why the decision rule could be "the first one that passes, in order": each step adds code and something that can break.

**2. Lazy start** (`m35-main.js`):
```js
if (!LAZY || !START_HIDDEN) {
  brain.start();
}
```
A0 always starts the brain at launch. The others start it at launch only when you opened Pseudo yourself; started hidden, they wait for the first show. This one `if` is the whole of A1.

**3. Counting CPU, including processes that are gone** (`m35_lib.py`):
```python
times = proc.cpu_times()
self.cpu[proc.pid] = (name, times.user + times.system)
```
`cpu_times()` is the total CPU a process has used since it started. The dictionary keeps the last value seen for every process id, so a brain that A2 stopped still counts for what it used. Subtracting the first sample's total from the last gives the CPU-seconds spent in the window.

**4. Two kinds of memory** (`m35_lib.py`):
```python
memory[name] += proc.memory_full_info().uss / 1048576
committed[name] += proc.memory_info().private / 1048576
```
**USS** ("unique set size") is the private memory that is in RAM right now: what would be freed at once if the process ended. **Committed** ("private bytes") is what the process has asked Windows for, in RAM or not. Both are true. They answered very differently, which is point 6 below.

**5. Refusing to measure the wrong thing** (`m35_measure.py`):
```python
if asleep is None:
    print(f"{mode}: NOT MEASURED: the steady state was never reached", flush=True)
    return
```
Twice, A2 and A3 were "measured" for ten minutes in a state they had never reached, because a signal was lost and the brain never started. The numbers looked fine. This check was added after that.

## What happens when you run it (annotated real output)

A hidden start, A0 against A1:
```
I5 hidden start: CPU s in the first minute 9.56 (limit 5) | windows shown 0 | processes {'face': 4, 'brain': 2, 'pseudo_hands': 2, 'other': 2}
I5 hidden start: CPU s in the first minute 2.78 (limit 5) | windows shown 0 | processes {'face': 4, 'brain': 0, 'pseudo_hands': 0, 'other': 0}
```
Loading Python, spaCy and the names list costs about 7 CPU-seconds. A0 pays that at every sign-in, whether or not you use Pseudo that day. This is the one criterion A0 missed.

A1's first show:
```
 show 1: front after 21 ms | typing after 69 ms | brain had to start True | wait shown True | ready after 7.6 s | fake draft kept True
 show 2: front after 11 ms | typing after 37 ms | brain had to start False
```
The window is there at once and you can type at once. The brain is ready 7.6 seconds later, and what was typed meanwhile is still in the box. Every later show is instant.

The same candidate, the same state, two runs:
```
A1 hidden, brain running: ... private MB ... total 15 (max 204; ...) | committed MB ... total 578
A1 hidden, brain running: 3604 s, 717 samples ... total 225 (max 248; first part 246, last part 225) | committed MB ... total 594 (... first part 594, last part 594)
```
15 MB in one run, 225 MB in the other. In the first, the laptop was in use and Windows had moved most of the idle Pseudo's memory out of RAM. Committed memory barely moved (578, 594). Over the 60 minutes it did not grow at all, which is what I6 was really asking: is there a leak?

## Try this (3 small experiments that break or change something)

1. **Watch Windows trim a process.** Start Pseudo.exe, open Task Manager > Details, and add the columns "Memory (private working set)" and "Commit size". Minimize Pseudo and use the laptop for ten minutes. The first column falls for the Python processes; the second doesn't.
2. **See the cold start.** In PowerShell: `Measure-Command { .\.venv\Scripts\python.exe -c "from pseudo_hands.core import redactor; redactor.redact('Call Anil Kumar')" }`. That one import-and-redact is most of what A1 avoids paying at sign-in.
3. **Count CPU-seconds yourself.** With Pseudo.exe open and untouched, run `(Get-Process Pseudo | Measure-Object CPU -Sum).Sum` twice, ten minutes apart, and subtract. Compare with the 1.0 to 1.8 measured here.

## Check yourself

1. Why did A0 fail, although it is what Pseudo does today and it works?
2. What is the difference between USS and committed memory, and why did USS fall to 15 MB?
3. The decision rule picked A1, although A2 and A3 use less memory when idle. Why is that the right outcome of the rule?
4. I6 said "within 10%". Why was it re-read as "does not grow by more than 10%", and why does the PRD say when that was decided?
5. A2 and A3 were measured in the wrong state twice. What made those runs look valid, and what stops it now?

<details>
<summary>Answers</summary>

1. Only on I5: started hidden (as it would be at every sign-in), it used 9.6 CPU-seconds in the first minute against a limit of 5, because the brain and `pseudo_hands` load immediately. It passed everything else.
2. USS is private memory currently in RAM; committed is everything the process has asked for, in RAM or paged out. Windows takes RAM back from processes that sit idle, more so when other programs want it, so an idle Pseudo's USS shrank while its committed memory stayed the same.
3. The rule, fixed before measuring, takes the first candidate that passes all six criteria in the order A0, A1, A2, A3: the simplest thing that is good enough. A1 passed, at 248 MB against a 400 MB limit. A2 and A3 would need a new page state and a stop timer, and every wake would cost 7 to 8 seconds, to save memory that the limit doesn't require saving.
4. USS can fall by itself (trimming), so "within 10%" would report a miss when nothing is wrong, and USS can't show a leak reliably. Committed memory can. A rule changed after seeing the data could be bent to get the answer you want, so the change, its reason and its date are written down for anyone to judge.
5. The candidate was running, hidden and idle, and produced plausible numbers; only two log lines ("brain ready: False") showed that the brain had never started. Now the script waits for the idle stop and prints NOT MEASURED instead of measuring if it never comes, and a signal that isn't picked up is sent again.

</details>

## How this connects to Pseudo's final architecture

M35 decides one line of the next milestone. In M36, "Start with Windows" launches Pseudo.exe hidden with a tray icon, and from D27's new paragraph it starts only the face; `brain-process.js` starts the brain on the first show. Nothing about privacy or approval changes: the brain and `pseudo_hands` are the same processes, started a little later. The numbers also set the budget for M37 and M38, whose criteria H5 and C6 say the hotkeys and the compact bar must stay within I1 and I2. And A2 stays on the shelf, measured: if 590 MB committed ever becomes a problem, the cost of the fix (a page state, a timer, a 7-second wake) is already known.
