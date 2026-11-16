// Generates what the client knows about the API, from the OpenAPI document the Python server
// writes (openapi.json), with hono-takibi:
//
//   src/studio/client/api/app.ts       the type of the API as a Hono app (types only)
//   src/studio/client/api/index.ts     the Hono client, `hc`, typed by it
//   src/studio/client/hooks/index.ts   the TanStack Query hooks over that client
//
// No route, schema or handler is kept: the server is the Python package. hono-takibi types its
// client by the app its template scaffolds, so the template does run, into node_modules/.cache,
// and the one line of the client that names that scaffold is pointed at app.ts instead. The
// two types describe the same document, so `hc` is typed the same either way; app.ts is the one
// that needs nothing else to exist.
//
// Two things are done to the document on the way; openapi.json stays as the server wrote it.
// FastAPI writes "or null" as `anyOf: [..., { type: 'null' }]`, which is what OpenAPI 3.1 says,
// and hono-takibi 0.31's type generator reads `{ type: 'null' }` as "an object, or null":
// `{ const: null }` is the same schema, and is read as `null`. And the type generator does not
// apply `basePath`, so for it the paths are written with the `/api` they are served under.
import { execFileSync } from 'node:child_process'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import path from 'node:path'

const BASE_PATH = '/api'
const root = path.resolve(import.meta.dirname, '..')
const cache = path.join(root, 'node_modules/.cache/djangoer')
const client = path.join(root, 'src/studio/client/api/index.ts')

// The import hono-takibi writes into the client: the app the template scaffolded.
const SCAFFOLD_IMPORT = /^import type \{ api \} from '[^']*\/app\/index'$/mu
const APP_IMPORT = "import type api from './app.js'"

function isRecord(value: unknown): value is { readonly [key: string]: unknown } {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** `{ type: 'null' }` and nothing else: the schema of the value null. */
function isNullType(schema: { readonly [key: string]: unknown }) {
  return schema.type === 'null' && Object.keys(schema).length === 1
}

/** The document with every `{ type: 'null' }` written as `{ const: null }`. */
function withConstNull(value: unknown): unknown {
  if (Array.isArray(value)) return value.map((item) => withConstNull(item))
  if (!isRecord(value)) return value
  if (isNullType(value)) return { const: null }
  return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, withConstNull(item)]))
}

/** The document with its paths under the base path they are served under. */
function withBasePath(document: unknown) {
  if (!isRecord(document) || !isRecord(document.paths)) {
    throw new Error('openapi.json has no paths.')
  }
  const paths = Object.fromEntries(
    Object.entries(document.paths).map(([route, item]) => [`${BASE_PATH}${route}`, item]),
  )
  return { ...document, paths }
}

function takibi(...args: readonly string[]) {
  execFileSync('hono-takibi', args, { cwd: root, stdio: 'inherit' })
}

const document = withConstNull(JSON.parse(readFileSync(path.join(root, 'openapi.json'), 'utf8')))
mkdirSync(cache, { recursive: true })
writeFileSync(path.join(cache, 'openapi.json'), JSON.stringify(document))
writeFileSync(path.join(cache, 'openapi.type.json'), JSON.stringify(withBasePath(document)))

// The type of the app, then the client and the hooks.
takibi()
takibi('--config', 'hono-takibi.hooks.config.ts')

const generated = readFileSync(client, 'utf8')
if (!SCAFFOLD_IMPORT.test(generated)) {
  throw new Error(
    `${path.relative(root, client)} does not import the scaffolded app as expected: hono-takibi's output changed, and scripts/generate.ts has to follow it.`,
  )
}
writeFileSync(client, generated.replace(SCAFFOLD_IMPORT, APP_IMPORT))
