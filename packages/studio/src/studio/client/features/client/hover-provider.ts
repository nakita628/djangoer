import { parseResponse } from 'hono/client'
import type { languages } from 'monaco-editor/editor/editor.api.js'

import { client as api } from '../../api/index.js'
import { registry, toRange, wordRange } from './editor-state.js'

/** What the server says about the symbol under the pointer, as Markdown. */
export function hoverProvider() {
  return {
    provideHover: async (model, position) => {
      if (!registry.available) return null
      const query = model.getValue()
      if (query.trim() === '') return null
      const hover = await parseResponse(
        api.client.hover.$post({ json: { query, offset: model.getOffsetAt(position) } }),
      ).catch(() => null)
      if (hover?.contents === null || hover?.contents === undefined) return null
      return {
        contents: [{ value: hover.contents }],
        range: hover.range === null ? wordRange(model, position) : toRange(model, hover.range),
      }
    },
  } satisfies languages.HoverProvider
}
