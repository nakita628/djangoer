import { createFileRoute } from '@tanstack/react-router'
import * as z from 'zod'

import { ClientView } from '../features/client/client-view.js'

export const Route = createFileRoute('/client')({
  validateSearch: z.object({
    query: z.string().optional().meta({
      description: 'A query to open the editor with, as the docs hand one over',
      example: 'Post.objects.all()',
    }),
  }),
  component: ClientPage,
})

function ClientPage() {
  const { query } = Route.useSearch()
  // A query handed over from another page opens as a fresh editor, whatever was typed before.
  return <ClientView key={query ?? ''} initialQuery={query ?? ''} />
}
