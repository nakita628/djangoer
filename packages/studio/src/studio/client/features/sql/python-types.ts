// The types of a statement's columns and parameters are Python's: the analysis names them as a
// Django project would annotate them (`int`, `str`, `datetime`, `Any` when it cannot tell).

/** The type the analysis gives a column or parameter it could not infer. */
export const UNKNOWN_TYPE = 'Any'

const NUMBER_TYPES = new Set(['int', 'float', 'Decimal'])

/** Whether a value of the type is typed as digits. */
export function isNumberType(type: string) {
  return NUMBER_TYPES.has(type)
}

export function isBooleanType(type: string) {
  return type === 'bool'
}

/** The type as an annotation would write it: `str | None` for a column that may be NULL. */
export function annotationOf(column: {
  readonly tsType: string
  readonly nullable: boolean | null
}) {
  return column.nullable === true && column.tsType !== 'None' && column.tsType !== UNKNOWN_TYPE
    ? `${column.tsType} | None`
    : column.tsType
}
