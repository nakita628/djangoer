// Inference for a model file while it is edited: completion and hover, read by the server
// (jedi, when the project has it installed; without it the answers are empty and the editor is
// an editor without suggestions).
import { parseResponse } from 'hono/client'
import { languages, Range } from 'monaco-editor/editor/editor.api.js'
import type { editor } from 'monaco-editor/editor/editor.api.js'

import { client as api } from '../../api/index.js'
import { completionKindOf } from '../client/kinds.js'
import { PYTHON_LANGUAGE_ID } from './monaco.js'

const FILE_SCHEME = 'file'

/** The project path of a model file's editor model (`file:///blog/models.py`), else null. */
function pathOf(model: editor.ITextModel) {
  return model.uri.scheme === FILE_SCHEME ? model.uri.path.replace(/^\//u, '') : null
}

function wordRange(
  model: editor.ITextModel,
  position: { readonly lineNumber: number; readonly column: number },
) {
  const word = model.getWordUntilPosition(position)
  return new Range(position.lineNumber, word.startColumn, position.lineNumber, word.endColumn)
}

function completionProvider() {
  return {
    triggerCharacters: ['.'],
    provideCompletionItems: async (model, position) => {
      const path = pathOf(model)
      if (path === null) return null
      const range = wordRange(model, position)
      // A request the API refuses leaves the editor without the feature, not with an error.
      const found = await parseResponse(
        api.schema.complete.$post({
          json: { path, content: model.getValue(), offset: model.getOffsetAt(position) },
        }),
      ).catch(() => null)
      if (found === null) return null
      return {
        suggestions: found.items.map((item) => ({
          label: item.label,
          kind: languages.CompletionItemKind[completionKindOf(item.kind)],
          insertText: item.insertText ?? item.label,
          sortText: item.sortText,
          range,
        })),
      }
    },
  } satisfies languages.CompletionItemProvider
}

function hoverProvider() {
  return {
    provideHover: async (model, position) => {
      const path = pathOf(model)
      if (path === null) return null
      const hover = await parseResponse(
        api.schema.hover.$post({
          json: { path, content: model.getValue(), offset: model.getOffsetAt(position) },
        }),
      ).catch(() => null)
      if (hover?.contents === null || hover?.contents === undefined) return null
      return { contents: [{ value: hover.contents }], range: wordRange(model, position) }
    },
  } satisfies languages.HoverProvider
}

const state = { registered: false }

/** Registers the providers for Python once, whichever page mounts an editor first. */
export function setupSourceInference() {
  if (state.registered) return
  state.registered = true
  languages.registerCompletionItemProvider(PYTHON_LANGUAGE_ID, completionProvider())
  languages.registerHoverProvider(PYTHON_LANGUAGE_ID, hoverProvider())
}
