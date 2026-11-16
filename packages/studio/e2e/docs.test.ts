// From the docs to the playground: "Try it" opens the example, and a read runs as it arrives.
import type { Page } from '@playwright/test'

import { editor, editorText, expect, test } from './studio.ts'

async function tryIt(page: Page, id: string) {
  await page.getByRole('link', { name: 'Docs', exact: true }).first().click()
  const operation = page.locator(id)
  await operation.scrollIntoViewIfNeeded()
  await operation.getByRole('link', { name: 'Try it' }).click()
  await expect(page).toHaveURL(/\/client\?query=/u)
}

test('a read opens in the playground, runs, and shows its SQL', async ({ page }) => {
  await page.goto('/docs')
  await tryIt(page, '#model-Post-count')
  await expect.poll(() => editorText(page)).toContain('Post.objects.count()')
  await expect(page.getByText('one value')).toBeVisible()
  await expect(page.getByRole('region', { name: 'SQL the query sent' })).toContainText(
    'SELECT COUNT(*)',
  )
})

test('the example replaces what was typed in the playground before', async ({ page }) => {
  await page.goto('/client')
  await editor(page).click()
  await page.keyboard.type('Tag.objects.all()')
  await tryIt(page, '#model-Author-all')
  await expect.poll(() => editorText(page)).toContain('Author.objects.all()')
  expect(await editorText(page)).not.toContain('Tag.objects')
})

test('a write waits for Run', async ({ page }) => {
  const runs: string[] = []
  page.on('request', (request) => {
    if (request.url().endsWith('/api/client/run')) runs.push(request.url())
  })
  await page.goto('/docs')
  await tryIt(page, '#model-Post-delete')
  await expect.poll(() => editorText(page)).toContain('.delete()')
  await page.waitForTimeout(1500)
  expect(runs).toStrictEqual([])
  await expect(page.getByText('Run the query to see what it returns.')).toBeVisible()
})
