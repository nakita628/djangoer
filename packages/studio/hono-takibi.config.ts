import { defineConfig } from 'hono-takibi'

// The type of the API, as a Hono app: what `hc` needs to know, and nothing that runs.
// The input is openapi.json as scripts/generate.ts prepares it; run `pnpm generate`.
export default defineConfig({
  input: 'node_modules/.cache/djangoer/openapi.type.json',
  type: {
    output: 'src/studio/client/api/app.ts',
    readonly: true,
  },
})
