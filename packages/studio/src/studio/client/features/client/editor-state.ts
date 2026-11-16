// What the language features of the Django ORM editor share: whether the server can be asked
// about the text, and the translations between the offsets the API speaks and the ranges Monaco
// draws.
import { Range } from 'monaco-editor/editor/editor.api.js'
import type { editor } from 'monaco-editor/editor/editor.api.js'

// The providers are registered once for the language; they read whichever editor is mounted.
export const registry: { available: boolean } = { available: false }

export function toRange(
  model: editor.ITextModel,
  offsets: { readonly start: number; readonly end: number },
) {
  const start = model.getPositionAt(offsets.start)
  const end = model.getPositionAt(offsets.end)
  return new Range(start.lineNumber, start.column, end.lineNumber, end.column)
}

export function wordRange(
  model: editor.ITextModel,
  position: { readonly lineNumber: number; readonly column: number },
) {
  const word = model.getWordUntilPosition(position)
  return new Range(position.lineNumber, word.startColumn, position.lineNumber, word.endColumn)
}
