// Syntax colouring of a Django ORM query: Monaco tokenizes with a Monarch grammar, so this is the
// one place the query is read by pattern. It tells apart what a query is made of — the model, the
// manager, the QuerySet methods, the keyword arguments with their `__` lookups, and the values —
// where a plain Python grammar colours every name the same. Everything that needs understanding
// (completion, hovers, signatures, the check) comes from the server, which reads the text with
// Python's own `ast`.
import type { languages } from 'monaco-editor/editor/editor.api.js'

export const QUERY_LANGUAGE_ID = 'django-orm-query'

const KEYWORDS = [
  'and',
  'as',
  'assert',
  'async',
  'await',
  'break',
  'class',
  'continue',
  'def',
  'del',
  'elif',
  'else',
  'except',
  'finally',
  'for',
  'from',
  'global',
  'if',
  'import',
  'in',
  'is',
  'lambda',
  'nonlocal',
  'not',
  'or',
  'pass',
  'raise',
  'return',
  'try',
  'while',
  'with',
  'yield',
] as const

const LITERALS = ['True', 'False', 'None'] as const

/** A name of a query: Python's identifier, which is also what Monaco takes for a word here. */
export const WORD_PATTERN = /-?\d*\.\d\w*|[A-Za-z_]\w*/u

/** The Monarch tokenizer for a Django ORM query. */
export const QUERY_MONARCH: languages.IMonarchLanguage = {
  defaultToken: '',
  tokenPostfix: '.query',
  keywords: KEYWORDS,
  literals: LITERALS,
  brackets: [
    { open: '{', close: '}', token: 'delimiter.curly' },
    { open: '[', close: ']', token: 'delimiter.square' },
    { open: '(', close: ')', token: 'delimiter.parenthesis' },
  ],
  tokenizer: {
    root: [
      [/#.*$/u, 'comment'],
      // `.filter(`: a manager or QuerySet method, called.
      [/(\.)([A-Za-z_]\w*)(?=\s*\()/u, ['delimiter', 'function']],
      // `.objects`: a manager, or any other attribute.
      [/(\.)([A-Za-z_]\w*)/u, ['delimiter', 'member']],
      // `title__icontains=`: a keyword argument, lookups and all (but not `==`).
      [/[A-Za-z_]\w*(?=\s*=(?!=))/u, 'key'],
      // `Post`, `Q`, `Count`: a model or an expression class.
      [/[A-Z]\w*/u, { cases: { '@literals': 'keyword.literal', '@default': 'type.identifier' } }],
      [/[A-Za-z_]\w*/u, { cases: { '@keywords': 'keyword', '@default': 'identifier' } }],
      [/0[xX][\da-fA-F_]+|0[bB][01_]+|0[oO][0-7_]+/u, 'number'],
      [/(?:\d[\d_]*(?:\.[\d_]*)?|\.\d[\d_]*)(?:[eE][+-]?\d+)?[jJ]?/u, 'number'],
      [/[rRbBfFuU]{0,2}"""/u, { token: 'string.quote', next: '@tripleDouble' }],
      [/[rRbBfFuU]{0,2}'''/u, { token: 'string.quote', next: '@tripleSingle' }],
      [/[rRbBfFuU]{0,2}"([^"\\\n]|\\.)*$/u, 'string.invalid'],
      [/[rRbBfFuU]{0,2}'([^'\\\n]|\\.)*$/u, 'string.invalid'],
      [/[rRbBfFuU]{0,2}"/u, { token: 'string.quote', next: '@stringDouble' }],
      [/[rRbBfFuU]{0,2}'/u, { token: 'string.quote', next: '@stringSingle' }],
      [/[{}()[\]]/u, '@brackets'],
      [/[,:;.]/u, 'delimiter'],
      [/[-+*/%=<>!&|^~@]+/u, 'operator'],
      [/\s+/u, 'white'],
    ],
    stringDouble: [
      [/[^\\"]+/u, 'string'],
      [/\\./u, 'string.escape'],
      [/"/u, { token: 'string.quote', next: '@pop' }],
    ],
    stringSingle: [
      [/[^\\']+/u, 'string'],
      [/\\./u, 'string.escape'],
      [/'/u, { token: 'string.quote', next: '@pop' }],
    ],
    tripleDouble: [
      [/"""/u, { token: 'string.quote', next: '@pop' }],
      [/\\./u, 'string.escape'],
      [/[^\\"]+|"/u, 'string'],
    ],
    tripleSingle: [
      [/'''/u, { token: 'string.quote', next: '@pop' }],
      [/\\./u, 'string.escape'],
      [/[^\\']+|'/u, 'string'],
    ],
  },
}

/** Brackets, auto-closing pairs, comments and indentation of the query language. */
export const QUERY_LANGUAGE_CONFIGURATION: languages.LanguageConfiguration = {
  comments: { lineComment: '#' },
  brackets: [
    ['{', '}'],
    ['[', ']'],
    ['(', ')'],
  ],
  autoClosingPairs: [
    { open: '{', close: '}' },
    { open: '[', close: ']' },
    { open: '(', close: ')' },
    { open: '"', close: '"', notIn: ['string'] },
    { open: "'", close: "'", notIn: ['string'] },
  ],
  surroundingPairs: [
    { open: '{', close: '}' },
    { open: '[', close: ']' },
    { open: '(', close: ')' },
    { open: '"', close: '"' },
    { open: "'", close: "'" },
  ],
  wordPattern: WORD_PATTERN,
}
