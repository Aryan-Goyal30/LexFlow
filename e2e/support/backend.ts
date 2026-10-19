/**
 * Starts and stops the isolated API used by the end-to-end tests.
 *
 * The API runs through `server/scripts/e2e.py`, against its own database
 * (`lexflow_e2e`) and upload folder, on 127.0.0.1:8001. The database URL stays
 * inside that Python process; nothing here reads or prints it.
 *
 * Stopping is identity-checked. Each start passes a random run id on the API's
 * command line and records `{ pid, runId }`. A process is only ever stopped when
 * the operating system confirms that this pid is still running `e2e.py` with
 * that exact run id, so a recorded pid that has since been reused by another
 * program is never touched. The health endpoint is only a supplementary check
 * (is the port busy before a start, free after a stop), never the reason to stop
 * a process.
 */

import { spawn, spawnSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import {
  closeSync,
  existsSync,
  mkdirSync,
  openSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const API_PORT = Number(process.env.LEXFLOW_E2E_API_PORT ?? 8001);
export const APP_PORT = Number(process.env.LEXFLOW_E2E_APP_PORT ?? 5174);

const ROOT = fileURLToPath(new URL('../..', import.meta.url));
const SERVER = path.join(ROOT, 'server');
const STATE_DIR = path.join(ROOT, 'e2e', '.state');
/** Which API process this run started: `{ pid, runId }`. */
export const RECORD_FILE = path.join(STATE_DIR, 'api.json');
const LOG_FILE = path.join(STATE_DIR, 'api.log');
const HEALTH_URL = `http://127.0.0.1:${API_PORT}/api/health`;

export interface ApiRecord {
  pid: number;
  runId: string;
}

function python(): string {
  if (process.env.LEXFLOW_PYTHON) return process.env.LEXFLOW_PYTHON;
  const venv =
    process.platform === 'win32'
      ? path.join(SERVER, '.venv', 'Scripts', 'python.exe')
      : path.join(SERVER, '.venv', 'bin', 'python');
  if (existsSync(venv)) return venv;
  return process.platform === 'win32' ? 'python' : 'python3';
}

const pythonHint = 'Set LEXFLOW_PYTHON, or create server/.venv (see server/README.md).';

async function healthy(): Promise<boolean> {
  try {
    const response = await fetch(HEALTH_URL, { signal: AbortSignal.timeout(2_000) });
    return response.ok;
  } catch {
    return false;
  }
}

async function until(condition: () => Promise<boolean> | boolean, what: string, ms = 30_000) {
  const deadline = Date.now() + ms;
  while (Date.now() < deadline) {
    if (await condition()) return;
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`Timed out waiting for ${what}. See ${LOG_FILE}.`);
}

/**
 * The command line of a running process, as the operating system reports it,
 * or null when no such process is running (or it can't be read).
 */
export function commandLineOf(pid: number): string | null {
  if (!Number.isSafeInteger(pid) || pid <= 0) return null;
  try {
    if (process.platform === 'linux') {
      const raw = readFileSync(`/proc/${pid}/cmdline`, 'utf8');
      return raw.split(String.fromCharCode(0)).join(' ').trim() || null;
    }
    const result =
      process.platform === 'win32'
        ? spawnSync(
            'powershell.exe',
            [
              '-NoProfile',
              '-NonInteractive',
              '-Command',
              `(Get-CimInstance Win32_Process -Filter "ProcessId=${pid}").CommandLine`,
            ],
            { encoding: 'utf8', windowsHide: true, timeout: 20_000 },
          )
        : spawnSync('ps', ['-o', 'command=', '-p', String(pid)], {
            encoding: 'utf8',
            timeout: 10_000,
          });
    if (result.status !== 0) return null;
    return result.stdout.trim() || null;
  } catch {
    return null;
  }
}

/** Whether `record` still describes a running e2e API started by this harness. */
export function isRecordedApi(record: ApiRecord): boolean {
  const commandLine = commandLineOf(record.pid);
  return (
    commandLine !== null &&
    commandLine.includes('e2e.py') &&
    commandLine.includes(`--run-id ${record.runId}`)
  );
}

export function readRecord(file: string): ApiRecord | null {
  try {
    const value: unknown = JSON.parse(readFileSync(file, 'utf8'));
    if (
      typeof value === 'object' &&
      value !== null &&
      'pid' in value &&
      'runId' in value &&
      Number.isSafeInteger(value.pid) &&
      typeof value.runId === 'string' &&
      /^[0-9a-f]{32}$/.test(value.runId)
    ) {
      return { pid: value.pid as number, runId: value.runId };
    }
  } catch {
    // Missing or unreadable: there is nothing to stop.
  }
  return null;
}

export type StopOutcome = 'stopped' | 'not-running' | 'not-ours';

/**
 * Stop the process in `file` if, and only if, it is still the e2e API that was
 * recorded there. Always forgets the record. Never signals any other process.
 */
export async function stopRecordedApi(file: string = RECORD_FILE): Promise<StopOutcome> {
  const record = readRecord(file);
  if (record === null) {
    rmSync(file, { force: true });
    return 'not-running';
  }
  if (!isRecordedApi(record)) {
    // Gone, or the pid now belongs to something else: leave it alone.
    rmSync(file, { force: true });
    return commandLineOf(record.pid) === null ? 'not-running' : 'not-ours';
  }
  try {
    process.kill(record.pid);
  } catch {
    // It exited between the check and the signal.
  }
  await until(() => !isRecordedApi(record), 'the e2e API process to exit', 20_000);
  rmSync(file, { force: true });
  return 'stopped';
}

/** Recreate the e2e database with the sample data, and empty its upload folder. */
export function prepareDatabase(): void {
  rmSync(LOG_FILE, { force: true }); // one log per run
  const result = spawnSync(python(), ['scripts/e2e.py', 'prepare'], {
    cwd: SERVER,
    stdio: 'inherit',
  });
  if (result.error) {
    throw new Error(`Could not run ${python()}: ${result.error.message}. ${pythonHint}`);
  }
  if (result.status !== 0) {
    const how = result.signal ? `signal ${result.signal}` : `exit ${result.status}`;
    // 9009: Windows' "python" store alias, which runs even when Python is absent.
    const hint = result.status === 9009 ? ` Python was not found. ${pythonHint}` : '';
    throw new Error(`Preparing the e2e database failed (${how}).${hint}`);
  }
}

/**
 * Deal with a record left by an interrupted run, before anything else can fail
 * (teardown runs even when setup fails). An API it proves to be ours is stopped;
 * anything else is left alone and the record is forgotten.
 */
export async function clearStaleRecord(): Promise<void> {
  const outcome = await stopRecordedApi();
  if (outcome === 'stopped') console.log('Stopped an e2e API left running by an earlier run.');
}

export async function startBackend(): Promise<void> {
  if (await healthy()) {
    throw new Error(`Something is already listening on port ${API_PORT}; stop it first.`);
  }
  mkdirSync(STATE_DIR, { recursive: true });
  const runId = randomBytes(16).toString('hex');
  const log = openSync(LOG_FILE, 'a');
  const child = spawn(python(), ['scripts/e2e.py', 'serve', '--run-id', runId], {
    cwd: SERVER,
    stdio: ['ignore', log, log],
    // Not tied to the process that started it: an API restarted by a test
    // worker keeps running after the worker exits, until teardown stops it.
    detached: true,
    windowsHide: true,
  });
  closeSync(log); // the child has its own copy
  let failure: string | null = null;
  child.on('error', (error) => {
    failure = `could not run ${python()}: ${error.message}. ${pythonHint}`;
  });
  child.on('exit', (code, signal) => {
    failure ??= `it exited during start-up (${signal ? `signal ${signal}` : `exit ${code}`})`;
  });
  child.unref();

  const record: ApiRecord | null = child.pid === undefined ? null : { pid: child.pid, runId };
  if (record) writeFileSync(RECORD_FILE, JSON.stringify(record));
  try {
    await until(async () => {
      if (failure !== null) throw new Error(`The e2e API failed to start: ${failure}`);
      return healthy();
    }, 'the e2e API to become healthy');
    // The port answers; make sure it is our process that answers.
    if (failure !== null || record === null || !isRecordedApi(record)) {
      throw new Error(`The e2e API failed to start: ${failure ?? 'it is not running'}`);
    }
  } catch (error) {
    // Our own child (we hold its handle), so stopping it is safe.
    if (child.exitCode === null && child.signalCode === null) child.kill();
    rmSync(RECORD_FILE, { force: true });
    throw new Error(`${(error as Error).message} See ${LOG_FILE}.`);
  }
}

/** Stop the API this run started, then check that its port is free. */
export async function stopBackend(): Promise<void> {
  const outcome = await stopRecordedApi();
  if (outcome === 'stopped') {
    await until(async () => !(await healthy()), `port ${API_PORT} to be free`, 15_000);
  }
}

export async function restartBackend(): Promise<void> {
  await stopBackend();
  await startBackend();
}
