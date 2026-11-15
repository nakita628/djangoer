/** The models under the app each belongs to, apps and models in the order the schema lists them. */
export function groupByApp<M extends { readonly app: string }>(models: readonly M[]) {
  const groups = Map.groupBy(models, (model) => model.app)
  return [...groups].map(([app, grouped]) => ({ app, models: grouped }))
}
