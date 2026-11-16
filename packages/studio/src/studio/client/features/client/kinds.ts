import type { languages } from 'monaco-editor/editor/editor.api.js'

// The kinds the server labels its completions with: what a name is in a Django ORM query, and
// the general ones of a language service.
const KINDS: ReadonlyMap<string, keyof typeof languages.CompletionItemKind> = new Map([
  ['model', 'Class'],
  ['manager', 'Property'],
  ['field', 'Field'],
  ['relation', 'Reference'],
  ['lookup', 'Operator'],
  ['argument', 'Variable'],
  ['value', 'Value'],
  ['variable', 'Variable'],
  ['method', 'Method'],
  ['function', 'Function'],
  ['local function', 'Function'],
  ['construct', 'Constructor'],
  ['constructor', 'Constructor'],
  ['property', 'Property'],
  ['getter', 'Property'],
  ['setter', 'Property'],
  ['var', 'Variable'],
  ['let', 'Variable'],
  ['const', 'Constant'],
  ['local var', 'Variable'],
  ['parameter', 'Variable'],
  ['alias', 'Variable'],
  ['class', 'Class'],
  ['local class', 'Class'],
  ['interface', 'Interface'],
  ['type', 'Struct'],
  ['primitive type', 'Struct'],
  ['type parameter', 'TypeParameter'],
  ['enum', 'Enum'],
  ['enum member', 'EnumMember'],
  ['module', 'Module'],
  ['external_module', 'Module'],
  ['keyword', 'Keyword'],
  ['string', 'Text'],
  ['directory', 'Folder'],
  ['script', 'File'],
])

/** The Monaco kind a completion shows with; anything unfamiliar is plain text. */
export function completionKindOf(kind: string) {
  return KINDS.get(kind) ?? 'Text'
}
