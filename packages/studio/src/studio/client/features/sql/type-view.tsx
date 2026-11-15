import { Button } from '@heroui/react'
import type { InferResponseType } from 'hono/client'
import { LuCopy } from 'react-icons/lu'

import type { client } from '../../api/index.js'
import { CodeBlock } from '../../components/code-block.js'
import { copyText } from '../../hooks/copy.js'

type Analysis = InferResponseType<typeof client.db.analyze.$post, 200>

/**
 * The row and parameter types as Python: a `TypedDict` for what each row carries and the tuple
 * (or the mapping, for named placeholders) the statement binds, written by the analysis.
 */
export function TypeView({ statement }: { readonly statement: Analysis['statements'][number] }) {
  const snippet = [statement.rowType, statement.paramsType]
    .filter((part) => part.trim() !== '')
    .join('\n\n')
  return (
    <div className="min-h-0 flex-1 overflow-auto p-4">
      <div className="mb-2 flex items-center gap-3">
        <div className="heading mb-0">Inferred types</div>
        <Button
          variant="ghost"
          size="sm"
          className="ml-auto"
          onPress={() => {
            copyText(snippet, 'Types')
          }}
        >
          <LuCopy size={14} />
          Copy
        </Button>
      </div>
      <CodeBlock code={snippet} language="python" />
      <p className="mt-3 text-code text-muted">
        {statement.kind === 'select'
          ? 'Row is what each row carries, as cursor.fetchall() hands it back column by column; a column that may be NULL carries | None. Params is the tuple (or the mapping, for named placeholders) the statement binds.'
          : statement.columns.length === 0
            ? 'A write without RETURNING yields no rows; cursor.rowcount reports the affected count instead.'
            : 'Row is what RETURNING hands back for each written row.'}
      </p>
    </div>
  )
}
