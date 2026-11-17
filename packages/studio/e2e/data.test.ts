// The rows of a model: what the database refuses is said, not only that it refused.
import { expect, test } from './studio.ts'

test.describe('a write the database refuses', () => {
  test.use({ expectedProblems: [/422/u] })

  test('says why in its toast', async ({ page }) => {
    await page.goto('/models/Tag')
    await expect(page.getByText(/of 6 rows/u)).toBeVisible()
    await page.getByRole('button', { name: 'Add row' }).click()
    // `django` is a tag of the seed already: the label is unique.
    const label = page.locator('input[type="text"], input:not([type])').last()
    await label.fill('django')
    // On the input itself: the grid may render again after the fill, and the page's focus with it.
    await label.press('Enter')
    await expect(page.getByText('The row could not be written.').first()).toBeVisible()
    await expect(page.getByText('UNIQUE constraint failed: blog_tag.label').first()).toBeVisible()
  })
})
