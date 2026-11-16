// models.py in Studio: edited and saved back, inferred as it is typed, and followed when it
// changes on disk. Every test that changes the file gets it back as it was (the `models`
// fixture), and waits for the server to have read it again.
import type { Page } from '@playwright/test'

import { diagram, editor, expect, suggestions, test } from './studio.ts'
import { readModels, writeModels } from './workspace.ts'

// A save, or a write from outside, restarts the server: what the page asks for in that moment
// can find nobody listening.
// The event stream is cut when the server stops (ERR_INCOMPLETE_CHUNKED_ENCODING), and the page
// connects again.
const RESTARTING = [
  /ERR_CONNECTION_REFUSED|ERR_EMPTY_RESPONSE|ERR_CONNECTION_RESET|ERR_INCOMPLETE_CHUNKED_ENCODING|503/u,
]

const status = (page: Page) => page.getByRole('status', { name: 'Save status' })

async function typeAtEnd(page: Page, text: string) {
  await editor(page).click()
  await page.keyboard.press('Control+End')
  await page.keyboard.type(text, { delay: 15 })
}

test.describe('editing', () => {
  test.use({ expectedProblems: RESTARTING })

  test('a save writes the file, and the diagram follows', async ({ page, models }) => {
    await page.goto('/source')
    await expect(status(page)).toHaveText('Saved')
    await expect(page.getByRole('button', { name: 'Save' })).toBeDisabled()
    await typeAtEnd(page, '\n\nclass Note(models.Model):\ntext = models.TextField()\n')
    await expect(status(page)).toHaveText('Unsaved changes')
    expect(readModels()).toBe(models)
    await page.keyboard.press('Control+s')
    await expect
      .poll(() => readModels())
      .toContain('class Note(models.Model):\n    text = models.TextField()')
    await expect(diagram(page).getByText('Note', { exact: true }).first()).toBeVisible()
    await expect(status(page)).toHaveText('Saved')
  })

  test('a file changed on disk under unsaved changes can be loaded again', async ({
    page,
    models,
  }) => {
    await page.goto('/source')
    await typeAtEnd(page, '\n# mine')
    await expect(status(page)).toHaveText('Unsaved changes')
    writeModels(`${models}\n# theirs\n`)
    await expect(status(page)).toHaveText('Changed on disk')
    await page.getByRole('button', { name: 'Load from disk' }).click()
    await expect(status(page)).toHaveText('Saved')
    await expect(editor(page)).toContainText('# theirs')
    await expect(editor(page)).not.toContainText('# mine')
  })
})

test.describe('the file on disk', () => {
  test.use({ expectedProblems: RESTARTING })

  test('a field added in another editor appears on the diagram', async ({ page, models }) => {
    await page.goto('/')
    await expect(page.getByText(/8 models · 10 relations/u)).toBeVisible()
    writeModels(
      models.replace(
        '    label = models.SlugField(unique=True)\n',
        '    label = models.SlugField(unique=True)\n    owner = models.ForeignKey("Author", on_delete=models.CASCADE, null=True)\n',
      ),
    )
    await expect(diagram(page).getByText('owner_id').first()).toBeVisible()
    await expect(page.getByText(/8 models · 11 relations/u)).toBeVisible()
  })

  test('a file saved half-written says where, and the fix brings the diagram back', async ({
    page,
    models,
  }) => {
    await page.goto('/source')
    writeModels(models.replace('class Tag(models.Model):', 'class Tag(models.Model)'))
    await expect(page.getByText(/SyntaxError: expected ':'/u).first()).toBeVisible()
    await expect(page.getByText('The diagram appears once the models load.')).toBeVisible()
    writeModels(models)
    await expect(diagram(page).getByText('Tag', { exact: true }).first()).toBeVisible()
  })
})

test.describe('inference', () => {
  // Half-typed code (`models.Cha`) does not load: its diagram preview is refused, as it should be.
  test.use({ expectedProblems: [/422/u] })

  test('completion knows Django and what a queryset returns', async ({ page }) => {
    await page.goto('/source')
    await typeAtEnd(page, '\n\nfield = models.Cha')
    expect(await suggestions(page)).toContain('CharField')
    await page.keyboard.press('Escape')
    await page.keyboard.type('rField()\n\n', { delay: 15 })
    await page.keyboard.type(
      'def first():\np = Post.objects.filter(views=1).first()\nreturn p.ti',
      {
        delay: 25,
      },
    )
    expect(await suggestions(page)).toStrictEqual(['title'])
  })

  test('a syntax error is underlined as it is typed', async ({ page }) => {
    await page.goto('/source')
    await expect(page.locator('.monaco-editor .squiggly-error')).toHaveCount(0)
    await typeAtEnd(page, '\n\nclass Broken(:')
    await expect(page.locator('.monaco-editor .squiggly-error').first()).toBeVisible()
  })

  test('hover describes a name', async ({ page }) => {
    await page.goto('/source')
    // The line is waited for (a slower machine draws it later), then the pointer is put on the
    // word by where it is in its token: Monaco may draw an identifier with what is around it as
    // one span, and the font is monospace.
    const line = page.locator('.monaco-editor .view-line', {
      hasText: 'name = models.CharField(max_length=100)',
    })
    await expect(line).toBeVisible()
    const token = line.locator('span[class^="mtk"]', { hasText: 'CharField' }).last()
    await expect(token).toBeVisible()
    const text = await token.innerText()
    const box = await token.boundingBox()
    if (box === null) throw new Error('The token of `CharField` is not on screen.')
    const at = (text.indexOf('CharField') + 3) / text.length
    await page.mouse.move(box.x + box.width * at, box.y + box.height / 2)
    await expect(page.locator('.monaco-hover-content').first()).toContainText('CharField(')
  })
})

test.describe('the diagram while models.py is edited', () => {
  test('follows the unsaved text, and the file on disk stays as it was', async ({
    page,
    models,
  }) => {
    await page.goto('/source')
    await expect(diagram(page).getByText('Tag', { exact: true }).first()).toBeVisible()
    const label = page.locator('.monaco-editor .view-line', {
      hasText: 'label = models.SlugField(unique=True)',
    })
    await label.click()
    await page.keyboard.press('End')
    await page.keyboard.type(
      '\nowner = models.ForeignKey("Author", on_delete=models.CASCADE, null=True)',
      { delay: 10 },
    )
    await expect(page.getByRole('note', { name: 'Diagram preview' })).toHaveText(
      'Preview of the unsaved changes',
    )
    await expect(diagram(page).getByText('owner_id').first()).toBeVisible()
    expect(readModels()).toBe(models)
  })

  test.describe('a text that does not load yet', () => {
    test.use({ expectedProblems: [/422/u] })

    test('keeps the last diagram and says why', async ({ page }) => {
      await page.goto('/source')
      const tag = page.locator('.monaco-editor .view-line', { hasText: 'class Tag(models.Model):' })
      await tag.click()
      await page.keyboard.press('End')
      // `class Tag(models.Model)` without its colon.
      await page.keyboard.press('Backspace')
      await expect(page.getByRole('note', { name: 'Diagram preview' })).toContainText(
        "The edit does not load yet: SyntaxError: expected ':'",
      )
      await expect(diagram(page).getByText('Tag', { exact: true }).first()).toBeVisible()
    })
  })
})
