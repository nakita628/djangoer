import path from 'node:path'

import tailwindcss from '@tailwindcss/vite'
import { tanstackRouter } from '@tanstack/router-plugin/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite-plus'
import type { Plugin } from 'vite-plus'

import { lint } from './lint.config.ts'

const CLIENT_ROOT = path.resolve(import.meta.dirname, 'src/studio/client')

// The build lands inside the Python package: `djangoer studio` serves it as it is, and the wheel
// ships it, so a `pip install djangoer` needs no Node.
const OUT_DIR = path.resolve(import.meta.dirname, '../djangoer/src/djangoer/studio/static')

// `vp dev` serves the client and hands /api to a running `djangoer studio`.
// DJANGOER_STUDIO_API overrides where that is.
const API_TARGET = process.env.DJANGOER_STUDIO_API ?? 'http://127.0.0.1:5555'

const MONACO_CHUNK = 'monaco'

/** The size past which a chunk slows the first visit to a page down (Vite's default). */
const CHUNK_SIZE_LIMIT = 500 * 1024

/**
 * The build's chunk size warning for every chunk but the Monaco core, which is as large as it is
 * and loads only with the editor pages.
 */
function chunkSizeWarning(): Plugin {
  return {
    name: 'djangoer-chunk-size',
    apply: 'build',
    generateBundle(_options, bundle) {
      for (const chunk of Object.values(bundle)) {
        if (chunk.type !== 'chunk' || chunk.name === MONACO_CHUNK) continue
        const size = Buffer.byteLength(chunk.code)
        if (size > CHUNK_SIZE_LIMIT) {
          this.warn(
            `${chunk.fileName} is ${Math.round(size / 1024)} kB, over ${CHUNK_SIZE_LIMIT / 1024} kB: split it with a dynamic import() or a codeSplitting group.`,
          )
        }
      }
    },
  }
}

export default defineConfig({
  root: CLIENT_ROOT,
  // `vp lint` and `vp check`: see lint.config.ts.
  lint,
  plugins: [
    // File-based routes under src/studio/client/routes → routeTree.gen.ts (imported relatively).
    tanstackRouter({
      target: 'react',
      autoCodeSplitting: true,
      routesDirectory: path.join(CLIENT_ROOT, 'routes'),
      generatedRouteTree: path.join(CLIENT_ROOT, 'routeTree.gen.ts'),
      quoteStyle: 'single',
      semicolons: false,
    }),
    tailwindcss(),
    react(),
    chunkSizeWarning(),
  ],
  server: {
    proxy: {
      // The event stream is a response that never ends; the proxy passes it through as it comes.
      '/api': { target: API_TARGET, changeOrigin: true },
    },
  },
  build: {
    outDir: OUT_DIR,
    emptyOutDir: true,
    // Monaco's own warning is replaced by the plugin above, which keeps it for every other chunk.
    chunkSizeWarningLimit: Number.POSITIVE_INFINITY,
    rolldownOptions: {
      output: {
        codeSplitting: {
          // The Monaco core in one chunk of a known name: the editor pages load it, nothing else
          // does, and it cannot be cut further — its services register themselves in module
          // order, and split across chunks the editor fails to start (`serviceIds` of undefined).
          groups: [{ name: MONACO_CHUNK, test: /node_modules[\\/]monaco-editor[\\/]/u }],
        },
      },
    },
  },
  test: {
    root: import.meta.dirname,
    include: ['src/**/*.test.ts'],
    exclude: ['**/node_modules/**'],
  },
})
