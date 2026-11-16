import { parseResponse } from 'hono/client'
import { languages } from 'monaco-editor/editor/editor.api.js'

import { client as api } from '../../api/index.js'
import { registry, wordRange } from './editor-state.js'
import { completionKindOf } from './kinds.js'

// What each completion item was asked about, for the detail lookup when it is highlighted.
const asked = new WeakMap<
  languages.CompletionItem,
  { readonly query: string; readonly offset: number }
>()

/**
 * Completion: the server's reading of the text up to the cursor — models, manager and QuerySet
 * methods, fields and their lookups — with the detail of the highlighted item fetched as it is
 * highlighted.
 */
export function completionProvider() {
  return {
    triggerCharacters: ['.', '(', ',', '"', "'", '_'],
    provideCompletionItems: async (model, position) => {
      if (!registry.available) return null
      const query = model.getValue()
      const offset = model.getOffsetAt(position)
      const word = wordRange(model, position)
      // The server names the last part of a lookup path (`name` for `author__na`), so that part
      // alone is what an accepted item replaces.
      const typed = model.getValueInRange(word)
      const part = typed.lastIndexOf('__')
      const range =
        part === -1
          ? word
          : word.setStartPosition(word.startLineNumber, word.startColumn + part + 2)
      // A request the API refuses (a project that does not load) leaves the editor without the
      // feature, not with an error.
      const found = await parseResponse(
        api.client.complete.$post({ json: { query, offset } }),
      ).catch(() => null)
      if (found === null) return null
      const suggestions = found.items.map((item) => {
        const suggestion = {
          label: item.label,
          kind: languages.CompletionItemKind[completionKindOf(item.kind)],
          insertText: item.insertText ?? item.label,
          sortText: item.sortText,
          range,
        }
        asked.set(suggestion, { query, offset })
        return suggestion
      })
      return { suggestions }
    },
    resolveCompletionItem: async (item) => {
      const context = asked.get(item)
      if (context === undefined) return item
      const label = typeof item.label === 'string' ? item.label : item.label.label
      const detail = await parseResponse(
        api.client.complete.detail.$post({ json: { ...context, name: label } }),
      ).catch(() => null)
      if (detail === null) return item
      return {
        ...item,
        detail: detail.detail ?? undefined,
        documentation: detail.documentation === null ? undefined : { value: detail.documentation },
      }
    },
  } satisfies languages.CompletionItemProvider
}
