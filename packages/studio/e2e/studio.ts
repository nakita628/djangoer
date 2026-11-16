// The shared test: every page collects browser errors and failed API calls, and a test fails on
// any of them, so a rendering regression that only shows up in the console is still caught.
import { expect, test as base } from '@playwright/test'
import type { Locator, Page } from '@playwright/test'
import * as z from 'zod'

import { readModels, writeModels } from './workspace.ts'

export { expect } from '@playwright/test'

type Problems = { readonly errors: readonly string[] }

// What the teardown reads of `/api/schema`: the files the server read.
const Snapshot = z.object({ files: z.array(z.object({ content: z.string() })) })

function isExpected(entry: string, expected: readonly RegExp[]) {
  return expected.some((pattern) => pattern.test(entry))
}

export const test = base.extend<{
  readonly problems: Problems
  /**
   * What a test provokes on purpose and says so: `test.use({ expectedProblems: [/422/u] })`
   * lets the console line of a refused request through, and nothing else.
   */
  readonly expectedProblems: readonly RegExp[]
  /** models.py as the test found it; written back when the test ends, whatever it did. */
  readonly models: string
}>({
  expectedProblems: [[], { option: true }],
  problems: [
    async ({ page, expectedProblems }, use) => {
      const errors: string[] = []
      page.on('pageerror', (error) => {
        errors.push(`pageerror: ${error.message}`)
      })
      page.on('console', (message) => {
        if (message.type() === 'error') errors.push(`console: ${message.text()}`)
      })
      page.on('response', (response) => {
        if (response.url().includes('/api/') && response.status() >= 500) {
          errors.push(`${response.status()} ${response.request().method()} ${response.url()}`)
        }
      })
      await use({ errors })
      const unexpected = errors.filter((entry) => !isExpected(entry, expectedProblems))
      expect(unexpected, 'the page reported errors').toStrictEqual([])
    },
    { auto: true },
  ],
  models: async ({ request }, use) => {
    const original = readModels()
    await use(original)
    if (readModels() !== original) writeModels(original)
    // The server restarts on a change, and reads the file again: the next test starts once the
    // schema it serves is the one of the file as it was. Waiting for any answer is not enough,
    // since the old server answers until the reloader has seen the change.
    await expect
      .poll(
        async () => {
          const response = await request.get('/api/schema').catch(() => null)
          if (!response?.ok()) return null
          const snapshot = Snapshot.parse(await response.json())
          return snapshot.files[0]?.content ?? null
        },
        { timeout: 30_000 },
      )
      .toBe(original)
  },
})

/** The Monaco editor of a page: the first one, or the one inside `within`. */
export function editor(page: Page, within?: Locator) {
  return (within ?? page).locator('.monaco-editor').first()
}

/** The text of a Monaco editor as it is on screen, one line per line. */
export async function editorText(page: Page, within?: Locator) {
  const text = await editor(page, within).locator('.view-lines').innerText()
  return text.replaceAll(' ', ' ')
}

/** The labels of the open suggestion list. */
export async function suggestions(page: Page) {
  const rows = page.locator('.suggest-widget.visible .monaco-list-row')
  await expect(rows.first()).toBeVisible()
  const texts = await rows.allInnerTexts()
  return texts.map((text) => text.split('\n')[0] ?? '')
}

/** The ER diagram of a page: React Flow's canvas. */
export function diagram(page: Page) {
  return page.locator('.react-flow').first()
}
