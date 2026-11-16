// Every page opens on the example project and shows what it is for, with nothing in the console.
import { diagram, expect, test } from './studio.ts'

test('the schema page draws every model of the project', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Schema' })).toBeVisible()
  await expect(page.getByText(/\d+ models · \d+ relations/u)).toBeVisible()
  for (const model of ['Author', 'Post', 'Comment', 'Tag', 'PostStatus']) {
    await expect(diagram(page).getByText(model, { exact: true }).first()).toBeVisible()
  }
})

test('the sidebar groups the models by app', async ({ page }) => {
  await page.goto('/')
  const sidebar = page.locator('aside, nav').first()
  await expect(sidebar.getByText('blog', { exact: true })).toBeVisible()
  await expect(sidebar.getByText('auth', { exact: true })).toBeVisible()
})

test('a model page lists its rows', async ({ page }) => {
  await page.goto('/models/Post')
  await expect(page.getByRole('heading', { name: 'Post' })).toBeVisible()
  await expect(page.getByText('blog_post').first()).toBeVisible()
  await expect(page.getByText('1–40 of 40 rows')).toBeVisible()
})

test('an enum page lists its values', async ({ page }) => {
  await page.goto('/enums/PostStatus')
  for (const value of ['DRAFT', 'PUBLISHED', 'ARCHIVED']) {
    await expect(page.getByText(value, { exact: true }).first()).toBeVisible()
  }
})

test('the docs describe every model with its operations', async ({ page }) => {
  await page.goto('/docs')
  await expect(page.locator('#model-Post-filter')).toBeVisible()
  await expect(page.locator('#model-Post-filter pre').first()).toContainText(
    "Post.objects.filter(status='draft')",
  )
})

test('the models.py page shows the project’s one models file beside the diagram', async ({
  page,
}) => {
  await page.goto('/source')
  await expect(page.getByRole('heading', { name: 'Django models' })).toBeVisible()
  await expect(page.getByText('blog/models.py').first()).toBeVisible()
  // One file: django.contrib's models are on the diagram, not listed as sources.
  await expect(page.getByRole('tab')).toHaveCount(0)
  await expect(diagram(page).getByText('Post', { exact: true }).first()).toBeVisible()
})
