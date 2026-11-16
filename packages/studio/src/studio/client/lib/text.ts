/** Whether there is text to show: a string that is not empty. `null` and `''` are both nothing. */
export function hasText(value: string | null | undefined): value is string {
  return typeof value === 'string' && value !== ''
}
