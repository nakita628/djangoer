// The project the E2E server runs on: a throwaway copy of examples/blog (the editor writes its
// models.py), migrated and seeded, rebuilt before every run. The example itself is never touched.
import { spawnSync } from 'node:child_process'
import { cpSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import path from 'node:path'

export const E2E_DIR = import.meta.dirname
export const ROOT_DIR = path.join(E2E_DIR, '..', '..', '..')
export const WORKSPACE_DIR = path.join(E2E_DIR, '.workspace')
export const MODELS_FILE = path.join(WORKSPACE_DIR, 'blog', 'models.py')
export const PORT = 5898
export const BASE_URL = `http://127.0.0.1:${PORT}`

const EXAMPLE_DIR = path.join(ROOT_DIR, 'examples', 'blog')
// What a copy of the example leaves behind: its database, its written docs, Python's caches.
const SKIPPED = new Set(['db.sqlite3', 'docs', '__pycache__'])

/** A command of the example project, run with the workspace's Python (uv, from the repository). */
export function manage(...args: readonly string[]) {
  return spawnSync('uv', ['run', '--project', ROOT_DIR, 'python', 'manage.py', ...args], {
    cwd: WORKSPACE_DIR,
    stdio: 'inherit',
  })
}

/** Rebuilds the workspace; the exit status of a step that failed, 0 when every step ran. */
export function prepareWorkspace() {
  rmSync(WORKSPACE_DIR, { recursive: true, force: true })
  cpSync(EXAMPLE_DIR, WORKSPACE_DIR, {
    recursive: true,
    filter: (source) => !SKIPPED.has(path.basename(source)),
  })
  for (const step of [['migrate', '-v', '0'], ['seed']]) {
    const result = manage(...step)
    if (result.status !== 0) return result.status ?? 1
  }
  return 0
}

/** models.py of the workspace as the test found it, to put back after a test that edits it. */
export function readModels() {
  return readFileSync(MODELS_FILE, 'utf8')
}

export function writeModels(content: string) {
  writeFileSync(MODELS_FILE, content)
}
