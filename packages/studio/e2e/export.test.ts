// The Schema page's downloads: the diagram as an image, the schema as Mermaid, DBML and docs.
import { readFileSync } from 'node:fs'

import { expect, test } from './studio.ts'

const DOWNLOADS = [
  { button: 'PNG', file: 'schema.png', starts: '\u0089PNG' },
  { button: 'SVG', file: 'schema.svg', starts: '<svg' },
  { button: 'Mermaid', file: 'er.md', starts: '```mermaid\nerDiagram' },
  { button: 'DBML', file: 'schema.dbml', starts: 'Enum PostStatus' },
  { button: 'Markdown', file: 'docs.md', starts: '# Schema docs' },
] as const

for (const { button, file, starts } of DOWNLOADS) {
  test(`${button} downloads ${file}`, async ({ page }, info) => {
    await page.goto('/')
    await expect(page.getByText(/\d+ models · \d+ relations/u)).toBeVisible()
    const downloading = page.waitForEvent('download')
    await page.locator(`button:has-text("${button}"), a:has-text("${button}")`).first().click()
    const download = await downloading
    expect(download.suggestedFilename()).toBe(file)
    const saved = info.outputPath(file)
    await download.saveAs(saved)
    expect(readFileSync(saved, 'latin1').startsWith(starts)).toBe(true)
  })
}

test('the Mermaid file covers the project’s own models and their relations', async ({
  request,
}) => {
  const response = await request.get('/api/export/er.md')
  const text = await response.text()
  expect(text).toContain('blog_author ||--o{ blog_post : "(id) - (author_id)"')
  expect(text).toContain('blog_post }o--o{ blog_tag : "(tags) - (posts)"')
  // The user model is django.contrib.auth's: kept as far as Author refers to it, its key only.
  expect(text).toContain('auth_user |o--o| blog_author : "(id) - (user_id)"')
  expect(text).toContain('    auth_user {\n        AutoField id PK\n    }')
  expect(text).not.toContain('username')
})
