/**
 * The model or enum whose class the 1-based line is in: the last one of the file that starts at
 * or above the line. A class runs until the next one starts, which is as much as a line number
 * says about Python.
 *
 * @param blocks - the models and enums of the schema, each where its class is written
 * @param file - the path of the file the line is in, as Studio loaded it
 */
export function blockAtLine(
  blocks: readonly {
    readonly name: string
    readonly location: { readonly file: string; readonly line: number } | null
  }[],
  file: string,
  line: number,
) {
  return (
    blocks
      .flatMap((block) =>
        block.location?.file === file && block.location.line <= line
          ? [{ name: block.name, line: block.location.line }]
          : [],
      )
      .toSorted((a, b) => b.line - a.line)[0]?.name ?? null
  )
}
