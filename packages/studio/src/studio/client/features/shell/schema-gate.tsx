import { buttonVariants } from '@heroui/react'
import { Link } from '@tanstack/react-router'
import type { InferResponseType } from 'hono/client'
import type { ReactNode } from 'react'

import type { client } from '../../api/index.js'
import { useSchema } from '../../hooks/index.js'

type Snapshot = InferResponseType<typeof client.schema.$get, 200>

// The schema as the API sends it; the pages below take the slices they read.
type Schema = NonNullable<Snapshot['schema']>

/** Renders the page once a schema is available; loading, request errors and models that never loaded are shown instead. */
export function SchemaGate({ children }: { readonly children: (schema: Schema) => ReactNode }) {
  const snapshotQuery = useSchema()
  const snapshot = snapshotQuery.data ?? null
  if (snapshotQuery.isError && snapshot === null) {
    return <pre className="error-box m-6">Could not load the models.</pre>
  }
  if (snapshot === null) return <div className="p-10 text-muted">Loading models…</div>
  if (snapshot.schema === null) {
    return (
      <section className="p-6">
        <h1 className="page-title mb-4">The models could not be loaded</h1>
        <pre className="error-box">{snapshot.error ?? 'Unknown error'}</pre>
        <Link className={`${buttonVariants({ variant: 'outline' })} mt-4`} to="/source" search={{}}>
          Open the source of the models
        </Link>
      </section>
    )
  }
  return children(snapshot.schema)
}
