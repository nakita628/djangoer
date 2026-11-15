import { createFileRoute } from '@tanstack/react-router'
import * as z from 'zod'

import { SourceView } from '../features/editor/source-view.js'
import { useSchema } from '../hooks/index.js'

export const Route = createFileRoute('/source')({
  validateSearch: z.object({
    focus: z
      .string()
      .optional()
      .meta({ description: 'The model or enum to scroll the source to', example: 'Post' }),
    file: z.string().optional().meta({
      description: 'The models file to open, as Studio loaded it',
      example: 'blog/models.py',
    }),
    line: z
      .number()
      .optional()
      .meta({ description: 'The 1-based line to put the cursor on', example: 12 }),
  }),
  component: SourcePage,
})

// The source is the one page that stays usable while the models do not load, so it takes the
// snapshot as is rather than waiting for a schema.
function SourcePage() {
  const { focus, file, line } = Route.useSearch()
  const snapshotQuery = useSchema()
  const snapshot = snapshotQuery.data ?? null
  if (snapshotQuery.isError && snapshot === null) {
    return <pre className="error-box m-6">Could not load the models.</pre>
  }
  if (snapshot === null) return <div className="p-10 text-muted">Loading models…</div>
  return (
    <SourceView snapshot={snapshot} focus={focus ?? null} file={file ?? null} line={line ?? null} />
  )
}
