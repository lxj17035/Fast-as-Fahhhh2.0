import { spawn } from 'node:child_process';
import { delimiter, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const pythonLibs = resolve(root, process.env.PIP_TARGET || '.pythonlibs');
if (!process.env.DEMO_ACCESS_USERNAME || !process.env.DEMO_ACCESS_PASSWORD) {
  throw new Error('Set DEMO_ACCESS_USERNAME and DEMO_ACCESS_PASSWORD before starting QuoteFlow.');
}

const python = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
const services = [
  {
    name: 'Python API',
    command: python,
    args: ['-m', 'backend.server'],
    env: {
      ...process.env,
      PYTHONPATH: [pythonLibs, process.env.PYTHONPATH].filter(Boolean).join(delimiter),
      PORT: '8004',
    },
  },
  {
    name: 'Authenticated web entry',
    command: process.execPath,
    args: ['frontend/server.mjs'],
    env: { ...process.env, PORT: process.env.PORT || '8080' },
  },
];

let stopping = false;
const children = services.map(({ command, args, env, name }) => {
  const child = spawn(command, args, { cwd: root, env, stdio: 'inherit' });
  child.on('error', () => {
    console.error(`${name} could not start.`);
    stop(1);
  });
  child.on('exit', (code) => {
    if (!stopping) {
      console.error(`${name} stopped unexpectedly.`);
      stop(code || 1);
    }
  });
  return child;
});

function stop(exitCode = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) {
    if (child.exitCode === null && child.signalCode === null) child.kill('SIGTERM');
  }
  const forceStop = setTimeout(() => {
    for (const child of children) {
      if (child.exitCode === null && child.signalCode === null) child.kill('SIGKILL');
    }
  }, 10_000);
  forceStop.unref();
  const finish = () => {
    if (children.every(child => child.exitCode !== null || child.signalCode !== null)) {
      clearTimeout(forceStop);
      process.exitCode = exitCode;
    }
  };
  for (const child of children) child.once('exit', finish);
  finish();
}

process.on('SIGINT', () => stop(0));
process.on('SIGTERM', () => stop(0));
