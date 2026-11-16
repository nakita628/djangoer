// Starts Studio on a fresh workspace. Playwright runs this as its web server, so the workspace
// is rebuilt exactly once per run (the config file itself is loaded by every worker).
//
// Studio runs as `djangoer studio` does for a user: with the reloader, so a saved models.py
// restarts it and the page follows. The reloader runs the server in a child process of its own;
// both stay in this process's group, which is the group Playwright stops when the run ends.
import { spawn } from 'node:child_process'

import { PORT, prepareWorkspace, ROOT_DIR, WORKSPACE_DIR } from './workspace.ts'

const prepared = prepareWorkspace()
if (prepared !== 0) process.exit(prepared)
const child = spawn(
  'uv',
  ['run', '--project', ROOT_DIR, 'djangoer', 'studio', '--port', String(PORT)],
  { stdio: 'inherit', cwd: WORKSPACE_DIR },
)
for (const signal of ['SIGINT', 'SIGTERM'] as const) {
  process.on(signal, () => {
    child.kill(signal)
  })
}
child.on('exit', (code) => {
  process.exit(code ?? 0)
})
