// A plain object, not `defineConfig` from vite-plus: the root has no dependency on Vite+, so the
// workspace installs one copy of it (packages/studio's), and the plugins there are typed against
// that one. `vp` reads the default export either way.
export default {
  // Single source of truth for formatting style. `vp fmt` uses this block whether it runs here or
  // in packages/studio, as long as no workspace config has a `fmt` block of its own: Vite+ does
  // not merge one into the other, so a workspace block would format that workspace with the
  // defaults.
  fmt: {
    printWidth: 100,
    singleQuote: true,
    semi: false,
    sortPackageJson: true,
    sortImports: {},
    // Tailwind classes are sorted the way prettier-plugin-tailwindcss would, against the Studio
    // stylesheet (Tailwind v4 reads the theme from CSS).
    sortTailwindcss: { stylesheet: './packages/studio/src/studio/client/styles.css' },
    ignorePatterns: [
      // hono-takibi output (formatted by the generator itself; see
      // packages/studio/hono-takibi.config.ts) and the document it is generated from.
      'packages/studio/src/studio/client/api/app.ts',
      'packages/studio/src/studio/client/api/index.ts',
      'packages/studio/src/studio/client/hooks/index.ts',
      'packages/studio/openapi.json',
      // What `just example-docs` writes: committed as djangoer writes it.
      'examples/blog/docs/**',
      // Written by the TanStack Router plugin.
      'packages/studio/src/studio/client/routeTree.gen.ts',
      // The client as it is built into the Python package.
      'packages/djangoer/src/djangoer/studio/static/**',
      // Python's own tools format these.
      '**/*.py',
      'uv.lock',
      'pnpm-lock.yaml',
    ],
  },
}
