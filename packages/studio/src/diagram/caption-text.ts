// What an edge says about itself: the relation, as it is spoken, and what the database does to a
// child row when the parent changes. Studio's canvas writes the same words the export does.
import type { Cardinality, SchemaRelation } from '../types/index.js'

/** `SetNull` and Django's `SET_NULL` alike, as words: `set null`. */
function humanizeAction(action: string) {
  return action
    .replaceAll(/([a-z])([A-Z])/gu, '$1 $2')
    .replaceAll('_', ' ')
    .trim()
    .toLowerCase()
}

/** The name a relation has when nobody named it: both model names sorted and joined with `To`. */
function defaultRelationName(a: string, b: string) {
  return [a, b].toSorted().join('To')
}

/** The relation's own name (a `related_name`), when the models gave it one. */
function customRelationName(relation: SchemaRelation) {
  const name = relation.name ?? null
  if (name === null) return null
  return name === defaultRelationName(relation.from.model, relation.to.model) ? null : name
}

/** What the database does to the child rows, as words: `on delete set null`. */
function referentialAction(event: string, action: string | null | undefined) {
  return action === null || action === undefined ? null : `on ${event} ${humanizeAction(action)}`
}

function isMany(cardinality: Cardinality) {
  return cardinality === 'many' || cardinality === 'zero-many'
}

/** The relationship the way it is spoken: one to one, one to many, many to many. */
function relationshipKind(relation: SchemaRelation) {
  const from = isMany(relation.from.cardinality)
  const to = isMany(relation.to.cardinality)
  if (from && to) return 'many to many'
  if (from) return 'many to one'
  return to ? 'one to many' : 'one to one'
}

/**
 * What an edge says about itself, a line at a time: what the relation is — its name, when the
 * schema gave it one, and the relationship it stands for — and then what the database does to a
 * child row when the parent changes.
 */
export function edgeCaption(relation: SchemaRelation): readonly string[] {
  const what = [customRelationName(relation), relationshipKind(relation)]
    .filter((part) => part !== null)
    .join(' · ')
  const rules = [
    referentialAction('delete', relation.onDelete),
    referentialAction('update', relation.onUpdate),
  ]
    .filter((part) => part !== null)
    .join(' · ')
  return rules === '' ? [what] : [what, rules]
}
