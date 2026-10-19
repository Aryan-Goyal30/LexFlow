/**
 * The e2e harness must never stop a process it did not start. These tests use
 * harmless decoy processes and a temporary record file (never the real one).
 */

import { spawn, type ChildProcess } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { mkdtempSync, rmSync, writeFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { expect, test } from '@playwright/test';
import { commandLineOf, stopRecordedApi } from './support/backend';

test.describe.configure({ timeout: 90_000 });

const decoys: ChildProcess[] = [];
let dir = '';

const runId = () => randomBytes(16).toString('hex');

/** A long-running process with whatever extra arguments its command line should show. */
function decoy(...args: string[]): number {
  const child = spawn(process.execPath, ['-e', 'setInterval(() => {}, 1000)', ...args], {
    stdio: 'ignore',
    windowsHide: true,
  });
  decoys.push(child);
  if (child.pid === undefined) throw new Error('decoy did not start');
  return child.pid;
}

function alive(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

function record(pid: number, id: string): string {
  const file = path.join(dir, 'api.json');
  writeFileSync(file, JSON.stringify({ pid, runId: id }));
  return file;
}

async function waitForCommandLine(pid: number) {
  await expect.poll(() => commandLineOf(pid), { timeout: 20_000 }).not.toBeNull();
}

test.beforeEach(() => {
  dir = mkdtempSync(path.join(tmpdir(), 'lexflow-harness-'));
});

test.afterEach(() => {
  for (const child of decoys.splice(0)) {
    if (child.exitCode === null && child.signalCode === null) child.kill();
  }
  rmSync(dir, { recursive: true, force: true });
});

test('leaves an unrelated process alone when its pid is in the record', async () => {
  const pid = decoy(); // stands in for a program that reused the API's old pid
  await waitForCommandLine(pid);
  const file = record(pid, runId());

  expect(await stopRecordedApi(file)).toBe('not-ours');
  expect(alive(pid)).toBe(true);
  expect(existsSync(file)).toBe(false); // the stale record is forgotten
});

test('leaves an e2e API from another run alone', async () => {
  const pid = decoy('scripts/e2e.py', 'serve', '--run-id', runId());
  await waitForCommandLine(pid);
  const file = record(pid, runId()); // same kind of process, different run id

  expect(await stopRecordedApi(file)).toBe('not-ours');
  expect(alive(pid)).toBe(true);
});

test('stops the process only when pid and run id both match', async () => {
  const id = runId();
  const pid = decoy('scripts/e2e.py', 'serve', '--run-id', id);
  await waitForCommandLine(pid);
  const file = record(pid, id);

  expect(await stopRecordedApi(file)).toBe('stopped');
  await expect.poll(() => alive(pid), { timeout: 20_000 }).toBe(false);
  expect(existsSync(file)).toBe(false);
});

test('treats a pid that is no longer running as nothing to stop', async () => {
  const child = spawn(process.execPath, ['-e', ''], { stdio: 'ignore', windowsHide: true });
  await new Promise((resolve) => child.on('exit', resolve));
  const file = record(child.pid as number, runId());

  expect(await stopRecordedApi(file)).toBe('not-running');
  expect(existsSync(file)).toBe(false);
});

test('ignores a missing or malformed record', async () => {
  const file = path.join(dir, 'api.json');
  expect(await stopRecordedApi(file)).toBe('not-running');

  writeFileSync(file, '12345'); // the old bare-pid format, or anything else
  expect(await stopRecordedApi(file)).toBe('not-running');
  expect(existsSync(file)).toBe(false);
});
