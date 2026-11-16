import { describe, expect, it } from 'vite-plus/test'

import { blockAtLine } from './source-blocks.js'

const BLOCKS = [
  { name: 'Author', location: { file: 'blog/models.py', line: 5 } },
  { name: 'Post', location: { file: 'blog/models.py', line: 12 } },
  { name: 'Order', location: { file: 'shop/models.py', line: 8 } },
  { name: 'Through', location: null },
]

describe('blockAtLine', () => {
  it('finds the class the line is in', () => {
    expect(blockAtLine(BLOCKS, 'blog/models.py', 5)).toBe('Author')
    expect(blockAtLine(BLOCKS, 'blog/models.py', 11)).toBe('Author')
    expect(blockAtLine(BLOCKS, 'blog/models.py', 40)).toBe('Post')
  })

  it('finds nothing above the first class of the file', () => {
    expect(blockAtLine(BLOCKS, 'blog/models.py', 2)).toBeNull()
  })

  it('reads only the classes of the file it is asked about', () => {
    expect(blockAtLine(BLOCKS, 'shop/models.py', 9)).toBe('Order')
    expect(blockAtLine(BLOCKS, 'other/models.py', 9)).toBeNull()
  })
})
