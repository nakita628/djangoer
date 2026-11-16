// The Django ORM playground: completion from the models, the value of a query and its SQL.
import { editor, expect, suggestions, test } from './studio.ts'

test('completion follows the chain to the fields of a relation', async ({ page }) => {
  await page.goto('/client')
  await editor(page).click()
  await page.keyboard.type('Post.objects.fil', { delay: 30 })
  expect(await suggestions(page)).toContain('filter')
  await page.keyboard.press('Enter')
  await page.keyboard.type('(author__', { delay: 30 })
  expect(await suggestions(page)).toEqual(expect.arrayContaining(['name', 'email']))
})

test('a query runs and shows its value with the SQL it sent', async ({ page }) => {
  await page.goto('/client')
  await editor(page).click()
  await page.keyboard.type('Post.objects.filter(status="published").count()', { delay: 10 })
  await page.keyboard.press('Escape')
  await page.keyboard.press('Control+Enter')
  await expect(page.getByText('one value')).toBeVisible()
  const sql = page.getByRole('region', { name: 'SQL the query sent' })
  await expect(sql).toContainText('SELECT COUNT(*)')
  await expect(sql).toContainText('"blog_post"."status"')
})

test.describe('a query that raises', () => {
  test.use({ expectedProblems: [/422/u] })

  test('shows what it raised', async ({ page }) => {
    await page.goto('/client')
    await editor(page).click()
    await page.keyboard.type('Author.objects.get(pk=999)', { delay: 10 })
    await page.keyboard.press('Escape')
    await page.keyboard.press('Control+Enter')
    await expect(page.locator('.error-box').first()).toHaveText(
      'DoesNotExist: Author matching query does not exist.',
    )
  })
})
