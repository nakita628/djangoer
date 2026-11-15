import { describe, expect, it } from 'vite-plus/test'

import {
  bindValues,
  defaultParamInput,
  paramInputsOf,
  paramKey,
  parseParamInput,
} from './params.js'

function parameter(tsType: string, nullable: boolean | null = null, placeholder = '?', index = 0) {
  return { index, placeholder, tsType, nullable }
}

describe('parseParamInput', () => {
  it('binds NULL for the literal, whatever the type', () => {
    expect(parseParamInput(parameter('int'), 'NULL')).toBeNull()
    expect(parseParamInput(parameter('str'), ' NULL ')).toBeNull()
  })

  it('binds NULL for an empty field only when the parameter is nullable', () => {
    expect(parseParamInput(parameter('str', true), '')).toBeNull()
    expect(parseParamInput(parameter('str', false), '')).toBe('')
    expect(parseParamInput(parameter('str', null), '')).toBe('')
  })

  it('parses a number and falls back to the text when the digits do not parse', () => {
    expect(parseParamInput(parameter('int'), ' 42 ')).toBe(42)
    expect(parseParamInput(parameter('float'), '-1.5')).toBe(-1.5)
    expect(parseParamInput(parameter('Decimal'), '2.50')).toBe(2.5)
    expect(parseParamInput(parameter('int'), 'abc')).toBe('abc')
    expect(parseParamInput(parameter('int'), '')).toBe('')
  })

  it('reads a boolean from true / false / 1 / 0', () => {
    expect(parseParamInput(parameter('bool'), 'true')).toBe(true)
    expect(parseParamInput(parameter('bool'), '1')).toBe(true)
    expect(parseParamInput(parameter('bool'), 'false')).toBe(false)
    expect(parseParamInput(parameter('bool'), '0')).toBe(false)
    expect(parseParamInput(parameter('bool'), 'yes')).toBe(false)
  })

  it('binds everything else as the text it was given, untrimmed', () => {
    expect(parseParamInput(parameter('str'), ' a ')).toBe(' a ')
    expect(parseParamInput(parameter('Any'), '12')).toBe('12')
  })
})

describe('defaultParamInput', () => {
  it('offers a sample the type accepts', () => {
    expect(defaultParamInput(parameter('int'))).toBe('1')
    expect(defaultParamInput(parameter('bool'))).toBe('true')
    expect(defaultParamInput(parameter('str'))).toBe('')
    expect(defaultParamInput(parameter('Date'))).toBe('')
  })
})

describe('paramKey', () => {
  it('remembers a named placeholder by its name and a positional one by its index', () => {
    expect(paramKey(parameter('str', null, ':name', 3))).toBe(':name')
    expect(paramKey(parameter('str', null, '@p', 3))).toBe('@p')
    expect(paramKey(parameter('str', null, '$user_id', 3))).toBe('$user_id')
    expect(paramKey(parameter('str', null, '?', 3))).toBe('#3')
    expect(paramKey(parameter('str', null, '$1', 3))).toBe('#3')
  })
})

describe('bindValues', () => {
  it('binds one value per parameter, in order, from the inputs or the defaults', () => {
    const parameters = [
      parameter('int', null, '$1', 0),
      parameter('str', null, ':name', 1),
      parameter('bool', null, '?', 2),
    ]
    expect(bindValues(parameters, { '#0': '7', ':name': 'ann' })).toStrictEqual([7, 'ann', true])
    expect(bindValues(parameters, {})).toStrictEqual([1, '', true])
  })
})

describe('paramInputsOf', () => {
  it('fills the positional fields in bind order, NULL for null', () => {
    expect(paramInputsOf(['ann', 10, true, false, null])).toStrictEqual({
      '#1': 'ann',
      '#2': '10',
      '#3': '1',
      '#4': '0',
      '#5': 'NULL',
    })
    expect(
      bindValues(
        [
          parameter('str', null, '$1', 1),
          parameter('int', null, '$2', 2),
          parameter('bool', null, '$3', 3),
          parameter('int', null, '$4', 4),
        ],
        paramInputsOf(['ann', '10', true, true]),
      ),
    ).toStrictEqual(['ann', 10, true, 1])
  })
})
