/**
 * M18: the brain as a CHILD PROCESS of the face.
 *
 * What it demonstrates: starting, talking to and stopping another program over a pipe.
 * The face runs `.venv\Scripts\python.exe -m pseudo_brain.bridge`, with the repo as its
 * working folder. We write one JSON object per line to its stdin and read one per line
 * from its stdout (the protocol in pseudo_brain/bridge.py). No port is opened (D18).
 *
 * Stopping: first we ASK ({"type":"quit"}). The bridge stops a running question,
 * private mode's server (if Pseudo started it) and pseudo_hands, then exits. If it
 * hasn't exited after 8 s, `taskkill /T /F` ends that process TREE: the venv's
 * python.exe is a small launcher that starts the real Python as its child, so killing
 * only the launcher would leave the real brain running.
 */

const { execFile, spawn } = require('node:child_process');
const path = require('node:path');

const REPO = path.resolve(__dirname, '..');
const PYTHON = path.join(REPO, '.venv', 'Scripts', 'python.exe');
const QUIT_WAIT_MS = 8000;

class BrainProcess {
  /**
   * @param {(message: object) => void} onMessage called with every protocol message the brain writes
   * @param {(code: number | null) => void} onExit called once the brain process has exited
   */
  constructor(onMessage, onExit) {
    this.onMessage = onMessage;
    this.onExit = onExit;
    this.child = null;
  }

  get running() {
    return this.child !== null;
  }

  start() {
    if (this.child) return; // one brain at a time
    const child = spawn(PYTHON, ['-m', 'pseudo_brain.bridge'], {
      cwd: REPO,
      stdio: ['pipe', 'pipe', 'inherit'], // stdin + stdout: the protocol; stderr: the brain's log, to our terminal
      windowsHide: true, // no console window
    });
    this.child = child;
    let partial = '';
    child.stdout.setEncoding('utf8');
    child.stdout.on('data', (chunk) => {
      partial += chunk;
      const lines = partial.split('\n');
      partial = lines.pop(); // the last piece has no newline yet: it's the start of the next line
      for (const line of lines) this.receive(line);
    });
    child.stdin.on('error', () => {}); // writing to a brain that just died: its exit is reported below
    const ended = (code) => {
      if (this.child !== child) return; // already reported
      this.child = null;
      this.onExit(code);
    };
    child.on('exit', (code) => ended(code));
    child.on('error', () => ended(null)); // e.g. .venv\Scripts\python.exe is missing
  }

  receive(line) {
    if (!line.trim()) return;
    let message;
    try {
      message = JSON.parse(line);
    } catch {
      return; // not a protocol line; the bridge never writes one, so this is just ignored
    }
    if (message && typeof message.type === 'string') this.onMessage(message);
  }

  /** One message to the brain, as one JSON line. */
  send(message) {
    if (this.child) this.child.stdin.write(JSON.stringify(message) + '\n');
  }

  /** Ask the brain to quit; after QUIT_WAIT_MS, end its whole process tree. Resolves once it's gone. */
  stop() {
    const child = this.child;
    if (!child) return Promise.resolve();
    return new Promise((resolve) => {
      const timer = setTimeout(() => {
        execFile('taskkill', ['/pid', String(child.pid), '/T', '/F'], () => resolve());
      }, QUIT_WAIT_MS);
      child.once('exit', () => {
        clearTimeout(timer);
        resolve();
      });
      this.send({ type: 'quit' });
    });
  }
}

module.exports = { BrainProcess };
