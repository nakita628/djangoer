import { Button, Tabs } from '@heroui/react'
import { Editor } from '@monaco-editor/react'
import type { OnMount } from '@monaco-editor/react'
import type { InferResponseType } from 'hono/client'
import type { editor as MonacoEditor } from 'monaco-editor/editor/editor.api.js'
import { useEffect, useMemo, useRef, useState } from 'react'
import { LuCopy } from 'react-icons/lu'

import type { client } from '../../api/index.js'
import { SchemaErrorStatus } from '../../components/schema-error-status.js'
import { SplitPane } from '../../components/split-pane.js'
import { useCopy } from '../../hooks/copy.js'
import { useUiStore } from '../../lib/index.js'
import { SchemaCanvas } from '../schema/schema-view.js'
import { EDITOR_OPTIONS, PYTHON_LANGUAGE_ID, setupMonaco, themeName } from './monaco.js'
import { blockAtLine } from './source-blocks.js'

type Snapshot = InferResponseType<typeof client.schema.$get, 200>

const SPLIT_KEY = 'djangoer-studio:source-split'

// The files are the project's own; Studio shows them and leaves the writing to the editor they
// were written in. Python is indented by four.
const SOURCE_OPTIONS: MonacoEditor.IStandaloneEditorConstructionOptions = {
  ...EDITOR_OPTIONS,
  readOnly: true,
  domReadOnly: true,
  tabSize: 4,
  quickSuggestions: false,
  renderValidationDecorations: 'off',
}

/** Puts the cursor on a line and scrolls it near the top of the editor. */
function reveal(editor: MonacoEditor.IStandaloneCodeEditor, line: number) {
  editor.setPosition({ lineNumber: line, column: 1 })
  editor.revealLineNearTop(line)
}

function SourceEditor({
  path,
  value,
  revealLine,
  onCursorLine,
}: {
  readonly path: string
  readonly value: string
  /** A line to scroll to and put the cursor on, when the view opens the file at a place. */
  readonly revealLine: number | null
  readonly onCursorLine: (line: number) => void
}) {
  setupMonaco()
  const theme = useUiStore((s) => s.theme)
  const mounted = useRef<MonacoEditor.IStandaloneCodeEditor | null>(null)
  const latest = useRef(onCursorLine)
  useEffect(() => {
    latest.current = onCursorLine
  })

  // A link to another class of the file that is already open moves the cursor there.
  useEffect(() => {
    if (mounted.current !== null && revealLine !== null) reveal(mounted.current, revealLine)
  }, [revealLine])

  const onMount: OnMount = (editor) => {
    mounted.current = editor
    editor.onDidChangeCursorPosition((event) => {
      latest.current(event.position.lineNumber)
    })
    if (revealLine !== null) reveal(editor, revealLine)
  }

  return (
    <Editor
      // Monaco keeps one model per path; the path is made a file URI so `.py` picks the grammar.
      path={`file:///${path}`}
      language={PYTHON_LANGUAGE_ID}
      value={value}
      theme={themeName(theme)}
      options={SOURCE_OPTIONS}
      loading={<div className="p-4 text-code text-muted">Loading editor…</div>}
      onMount={onMount}
    />
  )
}

/**
 * The source page: each app's `models.py` as it is on disk, read-only, beside the ER diagram of
 * what Django made of it. The model the cursor is in lights up in the diagram.
 */
export function SourceView({
  snapshot,
  focus,
  file: requestedFile,
  line,
}: {
  readonly snapshot: Snapshot
  /** A model or enum to open the page on, as a link from its page hands one over. */
  readonly focus: string | null
  readonly file: string | null
  readonly line: number | null
}) {
  const schema = snapshot.schema
  const blocks = useMemo(() => [...(schema?.models ?? []), ...(schema?.enums ?? [])], [schema])
  // Where the link points: the place it names, or the class of the model it names.
  const target = useMemo(() => {
    if (requestedFile !== null) return { file: requestedFile, line }
    const location = blocks.find((block) => block.name === focus)?.location ?? null
    return location === null ? null : { file: location.file, line: location.line }
  }, [requestedFile, line, focus, blocks])

  const [chosenPath, setChosenPath] = useState<string | null>(null)
  const [cursorLine, setCursorLine] = useState(1)
  const { copied, copy } = useCopy()

  // A tab picked by hand holds until a link names another place.
  const [seenTarget, setSeenTarget] = useState(target)
  if (seenTarget?.file !== target?.file || seenTarget?.line !== target?.line) {
    setSeenTarget(target)
    setChosenPath(null)
  }

  const path = chosenPath ?? target?.file ?? snapshot.files[0]?.path ?? null
  const file = snapshot.files.find((entry) => entry.path === path) ?? snapshot.files[0] ?? null
  const revealLine =
    file !== null && chosenPath === null && target?.file === file.path ? target.line : null

  const highlight = useMemo(
    () => (file === null ? null : blockAtLine(blocks, file.path, cursorLine)),
    [blocks, file, cursorLine],
  )

  if (file === null) {
    return <section className="p-6 text-muted">No models.py in the project&apos;s apps.</section>
  }

  const source = (
    <div className="min-h-0 min-w-0 bg-surface">
      <SourceEditor
        key={file.path}
        path={file.path}
        value={file.content}
        revealLine={revealLine}
        onCursorLine={setCursorLine}
      />
    </div>
  )

  const diagram = (
    <div className="flex min-h-0 min-w-0 flex-col">
      {schema ? (
        <SchemaCanvas schema={schema} focus={null} highlight={highlight} compact />
      ) : (
        <div className="p-6 text-muted">The diagram appears once the models load.</div>
      )}
    </div>
  )

  return (
    <section className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <header className="flex flex-nowrap items-center gap-3.5 border-b border-line bg-surface px-6 py-3">
        <h1 className="page-title shrink-0">Django models</h1>
        <span className="hidden min-w-0 truncate text-lead text-muted sm:inline">
          <span className="font-mono">{file.path}</span> · {file.content.split('\n').length} lines
          {schema?.provider ? ` · ${schema.provider}` : ''} · read-only
        </span>
        <span className="ml-auto flex min-w-0 items-center gap-3">
          <SchemaErrorStatus error={snapshot.error} diagnostics={snapshot.diagnostics} />
        </span>
        <Button
          className="shrink-0"
          variant="ghost"
          onPress={() => {
            copy(file.content)
          }}
        >
          <LuCopy size={15} />
          {copied ? 'Copied' : 'Copy'}
        </Button>
      </header>
      {snapshot.files.length > 1 ? (
        <Tabs
          className="overflow-x-auto border-b border-line bg-surface px-6 py-2"
          selectedKey={file.path}
          onSelectionChange={(key) => {
            setChosenPath(String(key))
            setCursorLine(1)
          }}
        >
          <Tabs.ListContainer className="w-fit">
            <Tabs.List aria-label="Model files">
              {snapshot.files.map((entry) => (
                <Tabs.Tab key={entry.path} id={entry.path} className="font-mono">
                  {entry.path}
                </Tabs.Tab>
              ))}
            </Tabs.List>
          </Tabs.ListContainer>
        </Tabs>
      ) : null}
      <SplitPane
        direction="row"
        storageKey={SPLIT_KEY}
        defaultRatio={0.5}
        min={0.2}
        max={0.8}
        label="Resize the source"
        first={source}
        second={diagram}
      />
    </section>
  )
}
