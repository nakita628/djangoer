import { Editor } from '@monaco-editor/react'
import type { OnMount } from '@monaco-editor/react'
import type { editor as MonacoEditor } from 'monaco-editor/editor/editor.api.js'
import { useEffect, useRef } from 'react'

import { useUiStore } from '../../lib/index.js'
import { EDITOR_OPTIONS, setupMonaco, themeName } from '../editor/monaco.js'
import { registry } from './editor-state.js'
import { applyClientMarkers, setupClientEditor } from './monaco-query.js'
import type { ClientMarker } from './monaco-query.js'
import { QUERY_LANGUAGE_ID } from './query-monarch.js'

// One model for the page: the providers and the markers find it by this name.
const QUERY_PATH = 'file:///djangoer-studio-query.py'

// A query is Python: four spaces, as every Django project writes it.
const QUERY_OPTIONS = { ...EDITOR_OPTIONS, tabSize: 4 }

/**
 * The Django ORM editor: Monaco with the grammar of a query, completion, hovers and signature
 * help answered by the server through the Studio API, and the problems found in the text — by
 * the reading and by the check — underlined.
 */
export function ClientEditor({
  value,
  onChange,
  onRun,
  onReady,
  available,
  markers,
  selection,
}: {
  readonly value: string
  readonly onChange: (value: string) => void
  readonly onRun: () => void
  /** Receives the editor once mounted, for the page's own commands (Format). */
  readonly onReady: (editor: MonacoEditor.IStandaloneCodeEditor) => void
  /** Whether the server can be asked about the text: completion, hovers and signatures. */
  readonly available: boolean
  readonly markers: readonly ClientMarker[]
  /** A range to select and scroll to, such as the diagnostic that was clicked. */
  readonly selection: ClientMarker['range'] | null
}) {
  const monaco = setupMonaco()
  setupClientEditor()
  const theme = useUiStore((s) => s.theme)
  const editor = useRef<MonacoEditor.IStandaloneCodeEditor | null>(null)
  const latest = useRef({ onChange, onRun })
  useEffect(() => {
    latest.current = { onChange, onRun }
  })

  useEffect(() => {
    registry.available = available
  }, [available])

  useEffect(() => {
    const model = editor.current?.getModel()
    if (model) applyClientMarkers(model, markers)
  }, [markers])

  useEffect(() => {
    const current = editor.current
    if (current === null || selection === null) return
    const model = current.getModel()
    if (!model) return
    const start = model.getPositionAt(selection.start)
    const end = model.getPositionAt(selection.end)
    current.setSelection(
      new monaco.Range(start.lineNumber, start.column, end.lineNumber, end.column),
    )
    current.revealPositionInCenterIfOutsideViewport(start)
    current.focus()
  }, [selection, monaco])

  const onMount: OnMount = (mounted) => {
    editor.current = mounted
    mounted.addCommand(
      // oxlint-disable-next-line no-bitwise -- Monaco keybindings are bit flags by design
      monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter,
      () => {
        latest.current.onRun()
      },
    )
    // Monaco binds Ctrl+Shift+I on Linux; the header advertises Shift+Alt+F, so bind it everywhere.
    mounted.addCommand(
      // oxlint-disable-next-line no-bitwise -- Monaco keybindings are bit flags by design
      monaco.KeyMod.Shift | monaco.KeyMod.Alt | monaco.KeyCode.KeyF,
      () => {
        void mounted.getAction('editor.action.formatDocument')?.run()
      },
    )
    // The model outlives the page (`keepCurrentModel`), so it may hold the text of an earlier
    // visit. A query handed to the page replaces it; with none, the kept text is the query, and
    // the page is told so.
    const kept = mounted.getValue()
    if (kept !== value) {
      if (value === '') latest.current.onChange(kept)
      else mounted.setValue(value)
    }
    onReady(mounted)
    const model = mounted.getModel()
    if (model) applyClientMarkers(model, markers)
    mounted.focus()
  }

  return (
    <Editor
      path={QUERY_PATH}
      language={QUERY_LANGUAGE_ID}
      value={value}
      theme={themeName(theme)}
      options={QUERY_OPTIONS}
      keepCurrentModel
      loading={<div className="p-4 text-code text-muted">Loading editor…</div>}
      onMount={onMount}
      onChange={(text) => {
        if (text !== undefined) latest.current.onChange(text)
      }}
    />
  )
}
