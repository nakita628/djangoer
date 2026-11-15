function isRecord(value: unknown): value is Readonly<Record<string, unknown>> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/**
 * The result as a table, when it is one: an array of objects is a row per object, a single
 * object is one row, and a nested value (an included relation, an aggregate) is its JSON text in
 * the cell. Anything else — a count, a list of numbers, null — has no columns to show.
 */
export function tableOf(value: unknown) {
  const items = Array.isArray(value) ? value : [value]
  if (items.length === 0 || !items.every(isRecord)) return null
  const columns = [...new Set(items.flatMap((item) => Object.keys(item)))]
  const rows = items.map((item) =>
    Object.fromEntries(
      columns.map((column): [string, string | number | boolean | null] => {
        const cell = item[column]
        if (cell === null || cell === undefined) return [column, null]
        if (typeof cell === 'string' || typeof cell === 'number' || typeof cell === 'boolean') {
          return [column, cell]
        }
        return [column, JSON.stringify(cell)]
      }),
    ),
  )
  return { columns, rows }
}
