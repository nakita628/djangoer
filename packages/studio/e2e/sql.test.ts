// The SQL console: a statement runs against the project's database, and its tables light up.
import { expect, test } from './studio.ts'

test('a statement runs and shows its rows', async ({ page }) => {
  await page.goto('/sql')
  await page.locator('.cm-content').click()
  await page.keyboard.type('select status, count(*) as n from blog_post group by status')
  await page.keyboard.press('Control+Enter')
  await expect(page.getByText(/3 rows/u)).toBeVisible()
  for (const status of ['draft', 'published', 'archived']) {
    // The first column of a row is its header.
    await expect(page.getByRole('rowheader', { name: status, exact: true })).toBeVisible()
  }
})

test.describe('a statement the database refuses', () => {
  test.use({ expectedProblems: [/422/u] })

  test('shows what the database said', async ({ page }) => {
    await page.goto('/sql')
    await page.locator('.cm-content').click()
    await page.keyboard.type('select * from nope')
    await page.keyboard.press('Control+Enter')
    await expect(page.locator('.error-box').first()).toHaveText('no such table: nope')
  })
})
