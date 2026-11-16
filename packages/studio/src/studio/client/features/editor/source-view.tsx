import { Button, Tabs, toast } from '@heroui/react'
import { Editor } from '@monaco-editor/react'
import type { OnMount } from '@monaco-editor/react'
import { useQuery } from '@tanstack/react-query'
import { parseResponse } from 'hono/client'
import type { InferResponseType } from 'hono/client'
import type { editor as MonacoEditor } from 'monaco-editor/editor/editor.api.js'
import { useEffect, useMemo, useRef, useState } from 'react'
import { LuCopy, LuRotateCcw, LuSave } from 'react-icons/lu'

import { client as api } from '../../api/index.js'
import type { client } from '../../api/index.js'
import { SchemaErrorStatus } from '../../components/schema-error-status.js'
import { SplitPane } from '../../components/split-pane.js'
import { useCopy } from '../../hooks/copy.js'
import { useDebounced } from '../../hooks/debounce.js'
import { getSchemaKey, usePutSchemaFiles } from '../../hooks/index.js'
import { useUiStore } from '../../lib/index.js'
import { problemMessage } from '../../lib/problem.js'
import { hasText } from '../../lib/text.js'
import { SchemaCanvas } from '../schema/schema-view.js'
import { EDITOR_OPTIONS, PYTHON_LANGUAGE_ID, setupMonaco, themeName } from './monaco.js'
import { blockAtLine } from './source-blocks.js'
import { setupSourceInference } from './source-inference.js'

type Snapshot = InferResponseType<typeof client.schema.$get, 200>

const SPLIT_KEY = 'djangoer-studio:source-split'
const CHECK_DEBOUNCE_MS = 300
const MARKER_OWNER = 'djangoer'
const PREVIEW_DEBOUNCE_MS = 400

// The files are the project's own model files, edited here and written back as they are saved.
// Python is indented by four spaces.
const SOURCE_OPTIONS: MonacoEditor.IStandaloneEditorConstructionOptions = {
  ...EDITOR_OPTIONS,
  tabSize: 4,
  insertSpaces: true,
  // Suggestions, hover and syntax errors come from the server (./source-inference.ts).
  quickSuggestions: true,
  renderValidationDecorations: 'on',
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
  onChange,
  onSave,
}: {
  readonly path: string
  /** The text to show: what was typed here, or the file as it is on disk. */
  readonly value: string
  /** A line to scroll to and put the cursor on, when the view opens the file at a place. */
  readonly revealLine: number | null
  readonly onCursorLine: (line: number) => void
  readonly onChange: (text: string) => void
  readonly onSave: () => void
}) {
  const monaco = setupMonaco()
  setupSourceInference()
  const theme = useUiStore((s) => s.theme)
  const mounted = useRef<MonacoEditor.IStandaloneCodeEditor | null>(null)
  const latest = useRef({ onCursorLine, onChange, onSave })
  useEffect(() => {
    latest.current = { onCursorLine, onChange, onSave }
  })

  // A link to another class of the file that is already open moves the cursor there.
  useEffect(() => {
    if (mounted.current !== null && revealLine !== null) reveal(mounted.current, revealLine)
  }, [revealLine])

  // Where the syntax breaks, read by the server once per settled edit and drawn under the text.
  const settled = useDebounced(value, CHECK_DEBOUNCE_MS)
  const check = useQuery({
    queryKey: [...getSchemaKey(), '/schema/check', path, settled] as const,
    queryFn: ({ signal }) =>
      parseResponse(
        api.schema.check.$post({ json: { path, content: settled } }, { init: { signal } }),
      ),
    placeholderData: (previous) => previous,
  })
  const diagnostics = check.data?.diagnostics
  useEffect(() => {
    const model = mounted.current?.getModel()
    if (!model || diagnostics === undefined) return
    monaco.editor.setModelMarkers(
      model,
      MARKER_OWNER,
      diagnostics.map((diagnostic) => {
        const start = model.getPositionAt(diagnostic.range.start)
        const end = model.getPositionAt(diagnostic.range.end)
        return {
          severity: monaco.MarkerSeverity.Error,
          message: diagnostic.message,
          startLineNumber: start.lineNumber,
          startColumn: start.column,
          endLineNumber: end.lineNumber,
          endColumn: end.column,
        }
      }),
    )
  }, [diagnostics, monaco])

  const onMount: OnMount = (editor) => {
    mounted.current = editor
    editor.onDidChangeCursorPosition((event) => {
      latest.current.onCursorLine(event.position.lineNumber)
    })
    editor.addCommand(
      // oxlint-disable-next-line no-bitwise -- Monaco keybindings are bit flags by design
      monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS,
      () => {
        latest.current.onSave()
      },
    )
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
      onChange={(text) => {
        if (text !== undefined) latest.current.onChange(text)
      }}
    />
  )
}

/** What was typed into a file and is not on disk yet, with the disk's text it was typed over. */
type Draft = { readonly text: string; readonly base: string }

/**
 * The source page: each app's `models.py`, edited here and saved back to disk, beside the ER
 * diagram of what Django made of it. The model the cursor is in lights up in the diagram; a
 * save restarts the server, and the diagram follows the file a moment later.
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
  const [drafts, setDrafts] = useState<Readonly<Record<string, Draft>>>({})
  // The text of the last save of each file: until the server has read it back, the file on
  // disk and the editor differ, and that is not an unsaved change.
  const [saved, setSaved] = useState<Readonly<Record<string, string>>>({})
  // What each file held, as the page knew it, when it was last saved over.
  const [beforeSave, setBeforeSave] = useState<Readonly<Record<string, string>>>({})
  const write = usePutSchemaFiles({
    mutation: {
      onSuccess: (written) => {
        setSaved((current) => ({ ...current, [written.path]: written.content }))
        // What was saved is what the disk now holds: a later change is typed over that.
        setDrafts((current) => {
          const draft = current[written.path]
          if (draft === undefined) return current
          return { ...current, [written.path]: { text: draft.text, base: written.content } }
        })
      },
      onError: (error) => {
        toast.danger('The file could not be saved.', { description: problemMessage(error) })
      },
    },
  })

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

  // The text the preview is drawn from: what the editor holds, once typing pauses.
  const editing = file === null ? '' : (drafts[file.path]?.text ?? file.content)
  const previewText = useDebounced(editing, PREVIEW_DEBOUNCE_MS)
  // The diagram of the text as it is being edited, before it is saved: the server loads it in a
  // process of its own. A text that does not load keeps the last diagram that did, and says why.
  const previewPath = file?.path ?? null
  // Only a draft is previewed, and only once typing has paused on it: a file that changed on disk
  // is the diagram the server already serves.
  const draftText = file === null ? undefined : drafts[file.path]?.text
  const unsaved =
    file !== null &&
    draftText !== undefined &&
    previewText === draftText &&
    draftText !== saved[file.path]
  const preview = useQuery({
    queryKey: [...getSchemaKey(), '/schema/preview', previewPath, previewText] as const,
    queryFn: ({ signal }) =>
      parseResponse(
        api.schema.preview.$post(
          { json: { path: previewPath ?? '', content: previewText } },
          { init: { signal } },
        ),
      ),
    enabled: unsaved && previewPath !== null,
    placeholderData: (previous) => previous,
    retry: false,
  })

  const highlight = useMemo(
    () => (file === null ? null : blockAtLine(blocks, file.path, cursorLine)),
    [blocks, file, cursorLine],
  )

  if (file === null) {
    return <section className="p-6 text-muted">No models.py in the project&apos;s apps.</section>
  }

  // The save has been read back: the text from before it is not being waited out any more, so
  // the file going back to it later (a `git checkout`) is a change like any other.
  if (beforeSave[file.path] !== undefined && file.content === saved[file.path]) {
    setBeforeSave(({ [file.path]: _seen, ...others }) => others)
  }

  const draft = drafts[file.path] ?? null
  const text = draft?.text ?? file.content
  const dirty = text !== file.content && text !== saved[file.path]
  // The file was written by another editor while this one held changes of its own. Right after
  // a save the page still shows the text from before it, until the server has read the file
  // back: that text is the one being waited out, not a change.
  const changedOnDisk =
    draft !== null && dirty && draft.base !== file.content && file.content !== beforeSave[file.path]

  const edit = (next: string) => {
    setDrafts((current) => {
      const { [file.path]: previous, ...others } = current
      // Typing the file back to what is on disk leaves nothing to save.
      if (next === file.content) return others
      return { ...others, [file.path]: { text: next, base: previous?.base ?? file.content } }
    })
  }
  const discard = () => {
    setDrafts(({ [file.path]: _dropped, ...others }) => others)
  }
  const save = () => {
    if (!dirty || write.isPending) return
    setBeforeSave((current) => ({ ...current, [file.path]: file.content }))
    write.mutate({ json: { path: file.path, content: text } })
  }
  const shown = dirty ? (preview.data ?? schema) : schema
  const previewFailed = dirty && preview.isError && !preview.isFetching

  const status = write.isPending
    ? 'Saving…'
    : changedOnDisk
      ? 'Changed on disk'
      : dirty
        ? 'Unsaved changes'
        : 'Saved'

  const source = (
    <div className="min-h-0 min-w-0 bg-surface">
      <SourceEditor
        key={file.path}
        path={file.path}
        value={text}
        revealLine={revealLine}
        onCursorLine={setCursorLine}
        onChange={edit}
        onSave={save}
      />
    </div>
  )

  const diagram = (
    <div className="flex min-h-0 min-w-0 flex-col">
      {dirty ? (
        <div
          role="note"
          aria-label="Diagram preview"
          className={`border-b border-line px-4 py-1.5 text-code ${previewFailed ? 'text-danger' : 'text-muted'}`}
        >
          {previewFailed
            ? `The edit does not load yet: ${problemMessage(preview.error)}`
            : 'Preview of the unsaved changes'}
        </div>
      ) : null}
      {shown ? (
        <SchemaCanvas schema={shown} focus={null} highlight={highlight} compact />
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
          <span className="font-mono">{file.path}</span> · {text.split('\n').length} lines
          {hasText(schema?.provider) ? ` · ${schema.provider}` : ''}
        </span>
        <output aria-label="Save status" className="shrink-0 text-code text-faint">
          {status}
        </output>
        <span className="ml-auto flex min-w-0 items-center gap-3">
          <SchemaErrorStatus error={snapshot.error} diagnostics={snapshot.diagnostics} />
        </span>
        {changedOnDisk ? (
          <Button className="shrink-0" variant="ghost" onPress={discard}>
            <LuRotateCcw size={15} />
            Load from disk
          </Button>
        ) : null}
        <Button
          className="shrink-0"
          variant="primary"
          isDisabled={!dirty || write.isPending}
          onPress={save}
        >
          <LuSave size={15} />
          Save
        </Button>
        <Button
          className="shrink-0"
          variant="ghost"
          onPress={() => {
            copy(text)
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
