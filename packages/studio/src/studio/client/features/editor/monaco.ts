// The Monaco build Studio ships: the editor core, the features the editors use and Python's
// grammar, bundled by Vite. Nothing is fetched from a CDN, so Studio works offline.
import { loader } from '@monaco-editor/react'
// oxlint-disable-next-line import/no-namespace -- the React wrapper takes the whole Monaco API object
import * as monacoApi from 'monaco-editor/editor/editor.api.js'
import {
  editor,
  KeyCode,
  KeyMod,
  languages,
  MarkerSeverity,
  Position,
  Range,
  Uri,
} from 'monaco-editor/editor/editor.api.js'
// oxlint-disable-next-line import/default -- Vite's `?worker` module has a default export the resolver cannot see
import EditorWorker from 'monaco-editor/editor/editor.worker.js?worker'
// oxlint-disable-next-line import/no-unassigned-import -- registers Python, whose grammar loads with the first .py model
import 'monaco-editor/languages/definitions/python/register.js'

// oxlint-disable-next-line import/no-unassigned-import -- registers the editor features for their side effects
import './monaco-features.js'
import type { Theme } from '../../lib/index.js'

const monaco = { editor, languages, KeyCode, KeyMod, MarkerSeverity, Position, Range, Uri }

/** The language of a `models.py`, as Monaco's own Python grammar registers it. */
export const PYTHON_LANGUAGE_ID = 'python'

const EDITOR_FONT =
  'ui-monospace, SF Mono, Menlo, Consolas, Liberation Mono, DejaVu Sans Mono, monospace'

/**
 * What the operating system would rather you had typed. macOS turns two spaces into a period and
 * a space, straight quotes into curly ones, two hyphens into a dash; it does that to a
 * `<textarea>`, which is what drives Monaco here (`editContext` below turns the space bar back
 * on, and a textarea is what that costs). None of it belongs in code: a period is not what
 * the space bar was pressed for, and a curly quote is a syntax error.
 *
 * Each arrives as one `insertText` carrying the substituted text, so each is answered with what
 * the keys actually said.
 */
const SUBSTITUTIONS: { readonly [key: string]: string } = {
  '. ': ' ',
  '\u201C': '"',
  '\u201D': '"',
  '\u2018': "'",
  '\u2019': "'",
  '\u2013': '-',
  '\u2014': '-',
  '\u2026': '...',
}

/**
 * Refuses those substitutions on the editor's input area and types what was meant instead.
 *
 * @param code - the editor whose input area to watch
 * @returns how to stop watching it
 */
export function refuseTextSubstitutions(code: editor.IStandaloneCodeEditor) {
  const area = code.getDomNode()?.querySelector('textarea.inputarea')
  if (!(area instanceof HTMLTextAreaElement)) return () => undefined
  const refuse = (event: Event) => {
    if (!(event instanceof InputEvent) || event.inputType !== 'insertText') return
    const meant = event.data === null ? undefined : SUBSTITUTIONS[event.data]
    if (meant === undefined) return
    // The substitution replaces what is already there, so cancelling it leaves that alone; what
    // the key press was worth goes in through Monaco, with its undo and its auto-closing.
    event.preventDefault()
    code.trigger('keyboard', 'type', { text: meant })
  }
  area.addEventListener('beforeinput', refuse, { capture: true })
  return () => {
    area.removeEventListener('beforeinput', refuse, { capture: true })
  }
}

export const EDITOR_OPTIONS: editor.IStandaloneEditorConstructionOptions = {
  // Monaco 0.56 defaults its input to the experimental `EditContext`, which drives a plain
  // `<div class="native-edit-context">` — no `contenteditable`, no textarea. In Chromium a letter
  // reaches it as a `beforeinput`, and the space bar does not: the key arrives, nothing cancels
  // it, and no text is ever inserted. Typing `order_by("id") [:10]` writes it without the space.
  // The textarea this turns back on is the input path Monaco used for a decade.
  editContext: false,
  fontFamily: EDITOR_FONT,
  fontSize: 12.5,
  lineHeight: 20,
  tabSize: 2,
  insertSpaces: true,
  minimap: { enabled: false },
  scrollBeyondLastLine: false,
  automaticLayout: true,
  padding: { top: 12, bottom: 12 },
  renderLineHighlight: 'line',
  lineNumbersMinChars: 3,
  glyphMargin: false,
  folding: true,
  wordBasedSuggestions: 'off',
  quickSuggestions: { other: true, comments: false, strings: false },
  // Enter takes the highlighted item when there is something left to finish, and breaks the line
  // when there is not. The list is open for most of a query — every field and every lookup is a
  // completion — so plain `on` would swallow the newline at the end of a line that is already
  // written out. `smart` only takes an item that changes the line, which is the difference
  // between finishing a word and ending it.
  acceptSuggestionOnEnter: 'smart',
  suggest: { showWords: false, preview: true },
  bracketPairColorization: { enabled: false },
  guides: { bracketPairs: false, indentation: true },
  stickyScroll: { enabled: false },
  overviewRulerLanes: 0,
  hideCursorInOverviewRuler: true,
  scrollbar: { verticalScrollbarSize: 8, horizontalScrollbarSize: 8, useShadows: false },
  fixedOverflowWidgets: true,
  smoothScrolling: true,
  cursorBlinking: 'smooth',
  renderWhitespace: 'none',
}

const PALETTE = {
  light: {
    surface: '#ffffff',
    ink: '#16181f',
    muted: '#6b7084',
    faint: '#9a9fb3',
    line: '#e4e6ee',
    lineStrong: '#cfd3e0',
    accent: '#4f46e5',
    accentSoft: '#eef0ff',
    keyword: '#4f46e5',
    type: '#0f766e',
    blockName: '#16181f',
    annotation: '#b45309',
    string: '#15803d',
    number: '#0e7490',
    comment: '#9a9fb3',
    docComment: '#6b7084',
    fn: '#0369a1',
    danger: '#c2410c',
    warning: '#d97706',
  },
  dark: {
    surface: '#171a23',
    ink: '#e6e8ef',
    muted: '#9aa0b4',
    faint: '#6b7189',
    line: '#262b38',
    lineStrong: '#343a4a',
    accent: '#7c74ff',
    accentSoft: '#24264a',
    keyword: '#a5a0ff',
    type: '#5eead4',
    blockName: '#e6e8ef',
    annotation: '#fbbf24',
    string: '#86efac',
    number: '#67e8f9',
    comment: '#6b7189',
    docComment: '#9aa0b4',
    fn: '#7dd3fc',
    danger: '#fb923c',
    warning: '#fbbf24',
  },
} as const

function themeData(theme: Theme): editor.IStandaloneThemeData {
  const colors = PALETTE[theme]
  return {
    base: theme === 'dark' ? 'vs-dark' : 'vs',
    inherit: true,
    rules: [
      { token: 'keyword', foreground: colors.keyword.slice(1), fontStyle: 'bold' },
      { token: 'type', foreground: colors.type.slice(1) },
      { token: 'type.identifier', foreground: colors.blockName.slice(1), fontStyle: 'bold' },
      { token: 'annotation', foreground: colors.annotation.slice(1) },
      { token: 'string', foreground: colors.string.slice(1) },
      { token: 'string.quote', foreground: colors.string.slice(1) },
      { token: 'string.escape', foreground: colors.number.slice(1) },
      { token: 'string.invalid', foreground: colors.danger.slice(1) },
      { token: 'number', foreground: colors.number.slice(1) },
      { token: 'comment', foreground: colors.comment.slice(1), fontStyle: 'italic' },
      { token: 'comment.doc', foreground: colors.docComment.slice(1), fontStyle: 'italic' },
      { token: 'function', foreground: colors.fn.slice(1) },
      { token: 'identifier', foreground: colors.ink.slice(1) },
      // A Django ORM query: its manager, the keyword arguments, the literals. `tag` is what
      // Monaco's Python grammar calls a decorator.
      { token: 'tag', foreground: colors.annotation.slice(1) },
      { token: 'variable.predefined', foreground: colors.annotation.slice(1) },
      { token: 'member', foreground: colors.blockName.slice(1), fontStyle: 'bold' },
      { token: 'key', foreground: colors.type.slice(1) },
      { token: 'keyword.literal', foreground: colors.keyword.slice(1) },
      { token: 'operator', foreground: colors.muted.slice(1) },
      { token: 'delimiter', foreground: colors.muted.slice(1) },
    ],
    colors: {
      'editor.background': colors.surface,
      'editor.foreground': colors.ink,
      'editorGutter.background': colors.surface,
      'editorLineNumber.foreground': colors.faint,
      'editorLineNumber.activeForeground': colors.muted,
      'editor.lineHighlightBackground': `${colors.accentSoft}99`,
      'editor.lineHighlightBorder': '#00000000',
      'editor.selectionBackground': colors.accentSoft,
      'editor.inactiveSelectionBackground': `${colors.accentSoft}99`,
      'editorCursor.foreground': colors.accent,
      'editorIndentGuide.background1': colors.line,
      'editorIndentGuide.activeBackground1': colors.lineStrong,
      'editorBracketMatch.background': colors.accentSoft,
      'editorBracketMatch.border': colors.lineStrong,
      'editorWidget.background': colors.surface,
      'editorWidget.border': colors.lineStrong,
      'editorHoverWidget.background': colors.surface,
      'editorHoverWidget.border': colors.lineStrong,
      'editorSuggestWidget.background': colors.surface,
      'editorSuggestWidget.border': colors.lineStrong,
      'editorSuggestWidget.selectedBackground': colors.accentSoft,
      'editorSuggestWidget.selectedForeground': colors.ink,
      'editorSuggestWidget.highlightForeground': colors.accent,
      'editorSuggestWidget.focusHighlightForeground': colors.accent,
      'editorError.foreground': colors.danger,
      'editorWarning.foreground': colors.warning,
      'scrollbarSlider.background': `${colors.lineStrong}66`,
      'scrollbarSlider.hoverBackground': `${colors.lineStrong}aa`,
      'scrollbarSlider.activeBackground': `${colors.lineStrong}cc`,
      'editorOverviewRuler.border': '#00000000',
      focusBorder: colors.accent,
      'input.background': colors.surface,
      'input.border': colors.lineStrong,
      'list.hoverBackground': `${colors.accentSoft}99`,
      'quickInput.background': colors.surface,
      'peekView.border': colors.accent,
      'peekViewEditor.background': colors.surface,
      'peekViewResult.background': colors.surface,
      'peekViewTitle.background': colors.surface,
      'widget.shadow': theme === 'dark' ? '#00000066' : '#16181f1a',
    },
  }
}

export function themeName(theme: Theme) {
  return theme === 'dark' ? 'djangoer-dark' : 'djangoer-light'
}

const state = { ready: false }

/** Registers the worker and the themes; safe to call repeatedly. */
export function setupMonaco() {
  if (state.ready) return monaco
  state.ready = true
  globalThis.MonacoEnvironment = { getWorker: () => new EditorWorker() }
  loader.config({ monaco: monacoApi })
  editor.defineTheme(themeName('light'), themeData('light'))
  editor.defineTheme(themeName('dark'), themeData('dark'))
  return monaco
}
