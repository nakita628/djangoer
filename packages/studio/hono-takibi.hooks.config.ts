import { defineConfig } from 'hono-takibi'

// The Hono client and the TanStack Query hooks over it.
//
// hono-takibi types its client by the app its template scaffolds, so the template runs too:
// into node_modules/.cache, where its routes and handler stubs stay. Only the client and the
// hooks are written into src, and scripts/generate.ts points the client at the type of the app
// (./hono-takibi.config.ts) instead of at that scaffold.
export default defineConfig({
  input: 'node_modules/.cache/djangoer/openapi.json',
  output: 'node_modules/.cache/djangoer/app/routes.ts',
  basePath: '/api',
  readonly: true,
  format: {
    printWidth: 100,
    singleQuote: true,
    semi: false,
  },
  template: {
    routeHandler: true,
  },
  client: {
    output: 'src/studio/client/api/index.ts',
  },
  'tanstack-query': {
    output: 'src/studio/client/hooks/index.ts',
  },
})
