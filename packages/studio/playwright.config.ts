import { defineConfig, devices } from '@playwright/test'

import { BASE_URL } from './e2e/workspace.ts'

// The tests drive the built Studio (`pnpm build` first) through e2e/serve.ts: `djangoer studio`
// serves the client from the Python package and edits a throwaway copy of examples/blog, so a
// run never touches the example.

const CI = (process.env.CI ?? '') !== ''

export default defineConfig({
  testDir: './e2e',
  testMatch: '**/*.test.ts',
  // The editor saves to disk, the grid writes to the database, and a save restarts the server:
  // the tests share one server and one workspace, so they run one at a time.
  fullyParallel: false,
  workers: 1,
  retries: CI ? 1 : 0,
  reporter: CI ? 'github' : 'list',
  outputDir: './e2e/.results',
  timeout: 60_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: BASE_URL,
    trace: 'retain-on-failure',
    viewport: { width: 1500, height: 900 },
    colorScheme: 'light',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'node e2e/serve.ts',
    url: `${BASE_URL}/api/schema`,
    reuseExistingServer: false,
    timeout: 120_000,
  },
})
