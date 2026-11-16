import { describe, expect, it } from 'vite-plus/test'

import { completionKindOf } from './kinds.js'

describe('completionKindOf', () => {
  it('shows a general kind with the Monaco kind of the same name', () => {
    expect(
      ['property', 'method', 'function', 'const', 'let', 'enum member', 'keyword', 'class'].map(
        (kind) => completionKindOf(kind),
      ),
    ).toStrictEqual([
      'Property',
      'Method',
      'Function',
      'Constant',
      'Variable',
      'EnumMember',
      'Keyword',
      'Class',
    ])
  })

  it('shows what a name is in a Django ORM query', () => {
    expect(
      ['model', 'field', 'relation', 'lookup', 'manager'].map((kind) => completionKindOf(kind)),
    ).toStrictEqual(['Class', 'Field', 'Reference', 'Operator', 'Property'])
  })

  it('shows a kind the server adds later as plain text rather than failing', () => {
    expect(completionKindOf('accessor')).toBe('Text')
    expect(completionKindOf('')).toBe('Text')
  })
})
