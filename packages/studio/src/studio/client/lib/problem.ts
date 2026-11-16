function isRecord(value: unknown): value is { [key: string]: unknown } {
  return typeof value === 'object' && value !== null
}

/**
 * What a failed request says: the `detail` of its problem body (hono's client keeps the body on
 * the error it throws), else the status line.
 */
export function problemMessage(error: unknown) {
  if (!(error instanceof Error)) return 'The request could not be made.'
  const detail: unknown = Reflect.get(error, 'detail')
  const data: unknown = isRecord(detail) ? detail.data : undefined
  try {
    const body: unknown = typeof data === 'string' ? JSON.parse(data) : data
    return isRecord(body) && typeof body.detail === 'string' ? body.detail : error.message
  } catch {
    return error.message
  }
}
