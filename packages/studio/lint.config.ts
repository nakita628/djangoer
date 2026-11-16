import type { UserConfig } from 'vite-plus'

// The lint rules of the Studio client. They are Hekireki's (packages/hekireki/vite.config.ts),
// taken over with the client they were written for: the general rules, the ones for tests, and
// the ones for browser code, the diagram and the shared types. What Hekireki holds its own
// server and generators to stays there; the server here is Python, and is held to its rules by
// ruff, import-linter and lint/studio.py (see the repository's pyproject.toml).
/**
 * The components longer than the limits came from Hekireki as they are. Each has a ceiling at its
 * present length (lines of code, as the rules count them), so it can only get shorter: split it,
 * then lower its number here, or drop the entry once it is under the limit.
 */
const CEILINGS: {
  readonly [key: string]: {
    readonly function?: number
    readonly file?: number
    readonly dependencies?: number
  }
} = {
  'src/studio/client/components/data-grid.tsx': { function: 403, file: 688 },
  'src/studio/client/components/details-panel.tsx': { function: 120 },
  'src/studio/client/components/fields-table.tsx': { function: 125 },
  'src/studio/client/components/model-node.tsx': { function: 130 },
  'src/studio/client/components/result-table.tsx': { function: 140 },
  'src/studio/client/features/client/client-view.tsx': { function: 293, dependencies: 17 },
  'src/studio/client/features/client/result-pane.tsx': { function: 169 },
  'src/studio/client/features/data/model-view.tsx': { function: 377, file: 463, dependencies: 20 },
  'src/studio/client/features/editor/source-view.tsx': { function: 215, dependencies: 20 },
  'src/studio/client/features/palette/palette.tsx': { function: 186 },
  'src/studio/client/features/schema/schema-view.tsx': { function: 215, dependencies: 14 },
  'src/studio/client/features/sidebar/sidebar.tsx': { function: 147 },
  'src/studio/client/features/sql/columns-view.tsx': { function: 125 },
  'src/studio/client/features/sql/flow-view.tsx': { function: 108 },
  'src/studio/client/features/sql/sql-editor.tsx': { function: 126 },
  'src/studio/client/features/sql/sql-view.tsx': { function: 266, dependencies: 20 },
}

const SIZE = { skipBlankLines: true, skipComments: true } as const

type Lint = NonNullable<UserConfig['lint']>
type Override = NonNullable<Lint['overrides']>[number]

/** The override that holds one file to its ceiling. */
function ceilingOverride(file: string, ceiling: (typeof CEILINGS)[string]) {
  const rules: NonNullable<Override['rules']> = {}
  if (ceiling.function !== undefined) {
    rules['max-lines-per-function'] = ['error', { max: ceiling.function, ...SIZE, IIFEs: true }]
  }
  if (ceiling.file !== undefined) {
    rules['max-lines'] = ['error', { max: ceiling.file, ...SIZE }]
  }
  if (ceiling.dependencies !== undefined) {
    rules['import/max-dependencies'] = ['error', { max: ceiling.dependencies }]
  }
  return { files: [file], rules } satisfies Override
}

export const lint: Lint = {
  env: { node: true, es2024: true },
  // What is generated is not written by hand, and is not linted as if it were: the type of the
  // app, the Hono client and the hooks by hono-takibi from openapi.json, and routeTree.gen.ts
  // by the TanStack Router plugin.
  ignorePatterns: [
    '**/node_modules/**',
    'src/studio/client/api/app.ts',
    'src/studio/client/api/index.ts',
    'src/studio/client/hooks/index.ts',
    'src/studio/client/routeTree.gen.ts',
    // An ambient wildcard module (Vite's `?worker`) has to be a script file, which import/unambiguous rejects.
    'src/studio/client/vite-env.d.ts',
  ],
  // Setting `plugins` replaces oxlint's default list — restate the defaults, then add import,
  // and jest for the tests: its rules read `describe` / `it` / `expect` by name, which is how
  // the tests call them through `vite-plus/test` (the vitest plugin only knows them imported
  // from `vitest`).
  plugins: ['typescript', 'unicorn', 'oxc', 'import', 'promise', 'node', 'jsdoc', 'jest'],
  // The repository conventions that a glob cannot express (Effect.gen shape, schema
  // documentation, naming); see lint/custom.js for the rule list.
  options: {
    typeAware: true,
    typeCheck: true,
    // A rule that stops firing must have its `oxlint-disable` comment deleted
    // with it, otherwise the suppression silently outlives its reason.
    reportUnusedDisableDirectives: 'deny',
    // Nothing here is configured as a warning; this keeps a rule that defaults
    // to `warn` from slipping through `vp check` unnoticed.
    denyWarnings: true,
  },
  categories: {
    correctness: 'error',
    suspicious: 'error',
    perf: 'error',
    // Beyond Hekireki's three: the pedantic and nursery categories as well, every rule of them an
    // error unless it is turned off below, with the reason.
    pedantic: 'error',
    nursery: 'error',
  },
  // Rules in the correctness / suspicious / perf categories are already errors via
  // `categories` above and are not restated; this list only adds rules from the
  // pedantic / style / restriction / nursery categories, which no category enables.
  rules: {
    // Size: new code stays small. Blank lines and comments do not count, a long explanation is
    // welcome. The components that are longer than this came from Hekireki as they are, and have
    // a ceiling of their own below, at their present length, so they do not grow.
    'max-lines-per-function': ['error', { max: 100, ...SIZE, IIFEs: true }],
    'max-lines': ['error', { max: 350, ...SIZE }],
    // --- Hono Takibi's hardening, as packages/hono-takibi/vite.config.ts has it --------------
    'no-underscore-dangle': ['error', { allow: ['_tag'] }],
    'symbol-description': 'error',
    'typescript/use-unknown-in-catch-callback-variable': 'error',
    'typescript/return-await': 'error',
    'unicorn/throw-new-error': 'error',
    'import/no-self-import': 'error',
    'import/no-absolute-path': 'error',
    'import/no-empty-named-blocks': 'error',
    'no-shadow-restricted-names': 'error',
    'no-delete-var': 'error',
    'import/named': 'error',
    'import/newline-after-import': 'error',
    'import/no-amd': 'error',
    'import/no-dynamic-require': 'error',
    'import/no-webpack-loader-syntax': 'error',
    'no-duplicate-imports': ['error', { allowSeparateTypeImports: true }],
    'import/max-dependencies': ['error', { max: 13 }],
    'node/no-process-env': 'error',
    'unicorn/no-process-exit': 'error',
    'node/no-sync': 'error',
    'promise/avoid-new': 'error',
    'no-promise-executor-return': 'error',
    'id-length': [
      'error',
      {
        min: 2,
        properties: 'never',
        exceptions: [
          'x',
          'y',
          '_',
          'k',
          'v',
          's',
          'p',
          'n',
          'm',
          'i',
          'a',
          'b',
          'z',
          'T',
          'K',
          'A',
          'E',
          'M',
        ],
      },
    ],
    // Names that say nothing. Not `x` and `y`, the coordinates of the diagram; not `data`, the
    // value React Flow hands a node; not `fn`, a token of Monaco's theme: those are the names of
    // the APIs they belong to.
    'id-denylist': [
      'error',
      'tmp',
      'temp',
      'foo',
      'bar',
      'cb',
      'err',
      'e',
      'res',
      'req',
      'obj',
      'val',
      'arr',
      'str',
      'ret',
      'idx',
      'cnt',
      'num',
      'buf',
      'ctx',
      'elem',
      'el',
      'cur',
    ],
    'func-name-matching': 'error',
    'max-depth': ['error', 4],
    'max-nested-callbacks': ['error', 4],
    'max-classes-per-file': ['error', 2],
    'typescript/consistent-indexed-object-style': ['error', 'index-signature'],
    'typescript/adjacent-overload-signatures': 'error',
    'typescript/unified-signatures': 'error',
    'typescript/ban-tslint-comment': 'error',
    'typescript/no-unnecessary-qualifier': 'error',
    'typescript/no-namespace': 'error',
    'typescript/no-mixed-enums': 'error',
    'typescript/prefer-enum-initializers': 'error',
    'typescript/prefer-literal-enum-member': 'error',
    'oxc/no-const-enum': 'error',
    'typescript/parameter-properties': 'error',
    'typescript/no-empty-interface': 'error',
    'typescript/class-literal-property-style': 'error',
    'typescript/prefer-return-this-type': 'error',
    'typescript/related-getter-setter-pairs': 'error',
    'accessor-pairs': 'error',
    'grouped-accessor-pairs': 'error',
    'class-methods-use-this': 'error',
    'no-constructor-return': 'error',
    'unicorn/no-static-only-class': 'error',
    'unicorn/no-this-assignment': 'error',
    'unicorn/prefer-class-fields': 'error',
    'unicorn/custom-error-definition': 'error',
    'typescript/prefer-regexp-exec': 'error',
    'unicorn/no-console-spaces': 'error',
    'unicorn/require-number-to-fixed-digits-argument': 'error',
    'default-case': 'error',
    'unicorn/switch-case-braces': ['error', 'avoid'],
    'unicorn/switch-case-break-position': 'error',
    'unicorn/prefer-ternary': 'error',
    'unicorn/no-negation-in-equality-check': 'error',
    'logical-assignment-operators': 'error',
    'no-eq-null': 'error',
    'sort-vars': 'error',
    'vars-on-top': 'error',
    'oxc/branches-sharing-code': 'error',
    'oxc/bad-bitwise-operator': 'error',
    'no-proto': 'error',
    'no-alert': 'error',
    'unicorn/no-instanceof-array': 'error',
    'unicorn/no-new-buffer': 'error',
    'unicorn/no-unnecessary-array-splice-count': 'error',
    'unicorn/no-useless-iterator-to-array': 'error',
    'unicorn/prefer-prototype-methods': 'error',
    'unicorn/prefer-reflect-apply': 'error',
    'unicorn/prefer-date-now': 'error',
    'unicorn/consistent-date-clone': 'error',
    'unicorn/prefer-event-target': 'error',
    'unicorn/prefer-bigint-literals': 'error',
    'unicorn/text-encoding-identifier-case': 'error',
    'unicorn/explicit-timer-delay': 'error',
    'unicorn/consistent-assert': 'error',
    'unicorn/prefer-top-level-await': 'error',
    'unicorn/require-module-attributes': 'error',
    'jsdoc/no-blank-blocks': 'error',
    'jsdoc/require-throws-description': 'error',
    'jsdoc/require-yields-description': 'error',
    // --- Pedantic rules that do not fit, and why ----------------------------------------------
    // Props are declared readonly where they are written; the rule wants every parameter deeply
    // readonly, which React's events, Monaco's editor and the DOM's nodes are not and cannot be.
    'typescript/prefer-readonly-parameter-types': 'off',
    // The types say what a function takes and returns; JSDoc says why, in prose, not in tags that
    // repeat the types.
    'jsdoc/require-param': 'off',
    'jsdoc/require-returns': 'off',
    'jsdoc/require-param-type': 'off',
    'jsdoc/require-returns-type': 'off',
    // An effect that returns its cleanup in one branch returns `undefined` in the other:
    // consistent-return asks for it, and this rule would take it away again.
    'unicorn/no-useless-undefined': 'off',
    // Doc comments. The `jsdoc` plugin is off by default and enables nothing on its own, so
    // every rule is named here. Doc comments in this package are TSDoc: the type lives in the
    // signature, never in the comment, which is why `require-param-type`, `require-returns-type`
    // and `require-property-type` are the three rules deliberately left out — each one asks for
    // the `{type}` TSDoc bans. `require-param` / `require-returns` are left out too: a one-line
    // `/** Reads a UTF-8 text file. */` over a self-describing signature is the house style, and
    // those two would turn ~175 of them into `@param` boilerplate that restates the types.
    // What stays on is the shape of a block once someone writes one.
    'jsdoc/check-access': 'error',
    'jsdoc/check-property-names': 'error',
    // The default vocabulary is JSDoc's and does not know the TSDoc-only tags, so a valid
    // `@remarks` or `@typeParam` would be reported as a typo without this list.
    'jsdoc/check-tag-names': [
      'error',
      {
        definedTags: [
          'alpha',
          'beta',
          'decorator',
          'defaultValue',
          'eventProperty',
          'experimental',
          'inheritDoc',
          'label',
          'packageDocumentation',
          'privateRemarks',
          'remarks',
          'sealed',
          'typeParam',
          'virtual',
        ],
      },
    ],
    'jsdoc/empty-tags': 'error',
    'jsdoc/implements-on-classes': 'error',
    'jsdoc/no-defaults': 'error',
    'jsdoc/require-param-description': 'error',
    'jsdoc/require-param-name': 'error',
    'jsdoc/require-property': 'error',
    'jsdoc/require-property-description': 'error',
    'jsdoc/require-property-name': 'error',
    'jsdoc/require-returns-description': 'error',
    eqeqeq: 'error',
    'no-var': 'error',
    'prefer-const': 'error',
    'no-param-reassign': ['error', { props: true }],
    'no-console': 'error',
    'no-plusplus': 'error',
    'no-undef': 'error',
    // The tests (jest plugin). Codegen tests own a byte-for-byte contract: equality is strict,
    // a primitive is compared with toBe, and nothing is a snapshot — the expected text is in the
    // test, where a reviewer reads it. A test runs, is named once, and asserts unconditionally.
    'jest/valid-expect': ['error', { maxArgs: 2 }],
    'jest/no-identical-title': 'error',
    'jest/no-disabled-tests': 'error',
    'jest/no-focused-tests': 'error',
    'jest/no-duplicate-hooks': 'error',
    'jest/no-test-return-statement': 'error',
    // A hook that sets up a toolchain or a database asserts that it did.
    'jest/no-standalone-expect': [
      'error',
      { additionalTestBlockFunctions: ['beforeAll', 'beforeEach', 'afterAll', 'afterEach'] },
    ],
    'jest/no-done-callback': 'error',
    'jest/no-export': 'error',
    'jest/no-alias-methods': 'error',
    'jest/prefer-to-be': 'error',
    'jest/prefer-strict-equal': 'error',
    'jest/prefer-to-have-length': 'error',
    'jest/prefer-equality-matcher': 'error',
    'jest/prefer-comparison-matcher': 'error',
    'jest/prefer-todo': 'error',
    'jest/no-restricted-matchers': [
      'error',
      {
        toMatchSnapshot: 'Write the expected value out with toBe / toStrictEqual.',
        toMatchInlineSnapshot: 'Write the expected value out with toBe / toStrictEqual.',
        toThrowErrorMatchingSnapshot: 'Name the error the call throws.',
        toThrowErrorMatchingInlineSnapshot: 'Name the error the call throws.',
        toEqual: 'Use toStrictEqual: toEqual passes on undefined properties and other classes.',
      },
    ],
    'typescript/no-explicit-any': 'error',
    'typescript/no-non-null-assertion': 'error',
    'typescript/consistent-type-imports': 'error',
    'typescript/consistent-type-assertions': ['error', { assertionStyle: 'never' }],
    'typescript/no-misused-promises': 'error',
    'typescript/require-await': 'error',
    'typescript/prefer-readonly': 'error',
    'typescript/prefer-nullish-coalescing': 'error',
    // The default options allow number + string; a codegen library concatenates on purpose
    // through template literals only.
    'typescript/restrict-plus-operands': [
      'error',
      { allowNumberAndString: false, allowBoolean: false, allowNullish: false },
    ],
    'typescript/switch-exhaustiveness-check': 'error',
    'typescript/no-unsafe-argument': 'error',
    'typescript/no-unsafe-assignment': 'error',
    'typescript/no-unsafe-member-access': 'error',
    'typescript/no-unsafe-call': 'error',
    'typescript/no-unsafe-return': 'error',
    'unicorn/no-array-for-each': 'error',
    'unicorn/prefer-array-some': 'error',
    'unicorn/prefer-spread': 'error',
    'unicorn/prefer-string-replace-all': 'error',
    // Pedantic-category picks that fit a codegen library; the rest of that
    // category (max-lines, strict-boolean-expressions, …) is not adopted.
    'typescript/strict-void-return': 'error',
    'unicorn/prefer-string-slice': 'error',
    'unicorn/prefer-native-coercion-functions': 'error',
    'unicorn/prefer-import-meta-properties': 'error',
    'unicorn/no-lonely-if': 'error',
    'require-unicode-regexp': 'error',
    'import/no-cycle': 'error',
    // `custom/layer-namespace-import` has a usecases/services/domain module imported as a
    // namespace through its layer barrel, so a file that uses several modules of one layer
    // imports that barrel once per namespace (`import * as SqlDomain from '../domain/index.js'`
    // beside `import * as ModelDomain from '../domain/index.js'`). Merging those is what the
    // convention rejects, so this rule cannot apply.
    'import/no-duplicates': 'off',
    // promise / node rules sit outside the enabled categories, so the ones
    // that matter for an async Node CLI are named explicitly.
    'promise/param-names': 'error',
    'promise/valid-params': 'error',
    'promise/spec-only': 'error',
    'promise/no-new-statics': 'error',
    'promise/no-multiple-resolved': 'error',
    'promise/no-return-wrap': 'error',
    'promise/no-return-in-finally': 'error',
    'promise/no-nesting': 'error',
    'promise/no-promise-in-callback': 'error',
    'promise/no-callback-in-promise': 'error',
    'promise/catch-or-return': 'error',
    'promise/always-return': 'error',
    'promise/prefer-catch': 'error',
    'promise/prefer-await-to-then': 'error',
    'node/no-exports-assign': 'error',
    'node/no-new-require': 'error',
    'node/no-mixed-requires': 'error',
    'node/global-require': 'error',
    'node/no-path-concat': 'error',
    'node/no-top-level-await': 'error',
    'node/handle-callback-err': 'error',
    'node/callback-return': 'error',
    // --- Hardening beyond the enabled categories -------------------------
    // Everything below sits in `pedantic` / `style` / `restriction` /
    // `nursery`, which oxlint leaves off by default. Only rules reachable
    // from this codebase are listed: it is pure functions over Prisma DMMF
    // plus template strings, so class / enum / namespace / DOM rules are
    // deliberately absent rather than enabled as dead weight.

    // Escape hatches out of the type system, and the unsound types that
    // survive `strict`.
    'typescript/ban-ts-comment': 'error',
    'typescript/prefer-ts-expect-error': 'error',
    'typescript/no-unsafe-function-type': 'error',
    'typescript/no-empty-object-type': 'error',
    'typescript/no-invalid-void-type': 'error',
    'typescript/no-non-null-asserted-nullish-coalescing': 'error',
    'typescript/non-nullable-type-assertion-style': 'error',
    // Type-aware: flags calls into APIs their own `@deprecated` tag retired,
    // which plain `tsc` only surfaces as an editor strikethrough.
    'typescript/no-deprecated': 'error',
    'typescript/no-confusing-void-expression': 'error',
    'typescript/no-dynamic-delete': 'error',

    // Declaration style. `consistent-type-definitions: 'type'` locks in the
    // repo-wide `type X = {...}`; the default of this rule is the opposite
    // ('interface'), so the option is load-bearing, not decoration.
    'typescript/consistent-type-definitions': ['error', 'type'],
    'typescript/consistent-type-exports': 'error',
    'typescript/consistent-generic-constructors': 'error',
    'typescript/array-type': 'error',
    'typescript/method-signature-style': 'error',
    // Annotating what the initializer already proves works against
    // letting inference work (CONTRIBUTING.md).
    'typescript/no-inferrable-types': 'error',

    'typescript/dot-notation': 'error',
    'typescript/prefer-optional-chain': 'error',
    'typescript/prefer-for-of': 'error',
    'typescript/prefer-find': 'error',
    'typescript/prefer-includes': 'error',
    'typescript/prefer-string-starts-ends-with': 'error',
    'typescript/prefer-function-type': 'error',
    'typescript/prefer-reduce-type-parameter': 'error',
    // ESM-only package: a `require` call would not survive the build.
    'typescript/no-require-imports': 'error',
    'typescript/no-import-type-side-effects': 'error',

    // Rejections and throws must carry an Error, or the CLI reports
    // `[object Object]` instead of an actionable message
    // for whoever catches it.
    'typescript/only-throw-error': 'error',
    'typescript/prefer-promise-reject-errors': 'error',
    'no-throw-literal': 'error',
    'unicorn/error-message': 'error',
    'unicorn/prefer-type-error': 'error',

    // Node / ESM hygiene.
    'unicorn/prefer-node-protocol': 'error',
    'unicorn/prefer-module': 'error',
    'unicorn/prefer-global-this': 'error',
    'unicorn/require-module-specifiers': 'error',
    'unicorn/import-style': 'error',
    'unicorn/prefer-export-from': 'error',
    // `no-abusive-eslint-disable` pairs with `reportUnusedDisableDirectives`
    // above: a suppression must name the rule it silences and must still be
    // earning its place.
    'unicorn/no-abusive-eslint-disable': 'error',
    'unicorn/no-anonymous-default-export': 'error',

    // String and array work: this is what a codegen library does all day.
    'prefer-template': 'error',
    'no-useless-concat': 'error',
    'no-multi-str': 'error',
    'unicorn/consistent-template-literal-escape': 'error',
    'unicorn/explicit-length-check': 'error',
    'unicorn/consistent-existence-index-check': 'error',
    'unicorn/require-array-join-separator': 'error',
    'unicorn/prefer-at': 'error',
    'unicorn/prefer-negative-index': 'error',
    'unicorn/prefer-array-index-of': 'error',
    'unicorn/prefer-array-flat': 'error',
    'unicorn/prefer-object-from-entries': 'error',
    'unicorn/prefer-string-trim-start-end': 'error',
    'unicorn/prefer-code-point': 'error',
    'unicorn/consistent-empty-array-spread': 'error',
    // `.push(a); .push(b)` and `?? []` fed to a collection that already
    // accepts the empty case.
    'unicorn/prefer-single-call': 'error',
    'unicorn/no-useless-collection-argument': 'error',
    'unicorn/no-useless-fallback-in-spread': 'error',
    'unicorn/no-unnecessary-array-flat-depth': 'error',
    'unicorn/no-magic-array-flat-depth': 'error',
    'unicorn/no-unnecessary-slice-end': 'error',
    'unicorn/no-length-as-slice-end': 'error',
    'unicorn/no-unreadable-array-destructuring': 'error',
    // Mutating a literal that was just constructed hides the mutation from
    // the reader, which is the opposite of building values with const.
    'unicorn/no-immediate-mutation': 'error',

    // Regex and numbers.
    'unicorn/prefer-regexp-test': 'error',
    'prefer-regex-literals': 'error',
    'no-div-regex': 'error',
    'no-regex-spaces': 'error',
    'unicorn/prefer-number-properties': 'error',
    'unicorn/prefer-math-min-max': 'error',
    'unicorn/prefer-math-trunc': 'error',
    'unicorn/prefer-modern-math-apis': 'error',
    'unicorn/numeric-separators-style': 'error',
    'unicorn/no-zero-fractions': 'error',
    'unicorn/escape-case': 'error',
    'unicorn/no-hex-escape': 'error',
    radix: 'error',
    'prefer-numeric-literals': 'error',
    'prefer-exponentiation-operator': 'error',
    'no-implicit-coercion': 'error',
    'unicorn/no-typeof-undefined': 'error',

    // Control flow and declarations. `curly` is set to `multi-line` rather
    // than `all` so the guard-clause form
    // (`if (!x) return null` on one line) stays legal, while a body that
    // wraps onto its own line must be braced.
    curly: ['error', 'multi-line'],
    'no-else-return': 'error',
    'no-useless-return': 'error',
    'no-lonely-if': 'error',
    'unicorn/prefer-logical-operator-over-ternary': 'error',
    'unicorn/prefer-default-parameters': 'error',
    'unicorn/no-object-as-default-parameter': 'error',
    'unicorn/no-unreadable-iife': 'error',
    'unicorn/no-useless-switch-case': 'error',
    'default-case-last': 'error',
    'default-param-last': 'error',
    'no-fallthrough': 'error',
    'no-case-declarations': 'error',
    'array-callback-return': 'error',
    'no-loop-func': 'error',
    'no-inner-declarations': 'error',
    'block-scoped-var': 'error',
    'init-declarations': 'error',
    'no-redeclare': 'error',
    'no-multi-assign': 'error',
    'no-return-assign': 'error',
    'no-sequences': 'error',
    'no-useless-assignment': 'error',
    'no-unreachable-loop': 'error',
    // Hoisted `function` declarations are safe to reference above their
    // definition; `const` / `class` are the TDZ hazard this rule is for.
    'no-use-before-define': ['error', { functions: false }],
    'func-style': ['error', 'declaration', { allowArrowFunctions: true }],
    'arrow-body-style': 'error',
    'prefer-arrow-callback': 'error',
    'guard-for-in': 'error',
    'no-labels': 'error',
    'no-label-var': 'error',
    'no-extra-label': 'error',
    'no-lone-blocks': 'error',
    yoda: 'error',
    'no-self-compare': 'error',

    // Objects and globals.
    'object-shorthand': 'error',
    'operator-assignment': 'error',
    'prefer-object-spread': 'error',
    'prefer-object-has-own': 'error',
    'no-prototype-builtins': 'error',
    'no-object-constructor': 'error',
    'no-array-constructor': 'error',
    'no-new-wrappers': 'error',
    'unicorn/new-for-builtins': 'error',
    'prefer-rest-params': 'error',
    'no-implicit-globals': 'error',
    'no-extra-bind': 'error',
    'no-useless-computed-key': 'error',
    'unicorn/no-await-expression-member': 'error',
    'unicorn/no-useless-promise-resolve-reject': 'error',
    'unicorn/prefer-structured-clone': 'error',
    'unicorn/prefer-optional-catch-binding': 'error',
    // Every `catch` in this package binds `e`; the rule's own default is
    // `error`, so the option is what pins the existing convention.
    'unicorn/catch-error-name': ['error', { name: 'e' }],

    // Code injection surfaces (`eval` itself is already `correctness`).
    'no-new-func': 'error',
    'no-script-url': 'error',
    'no-bitwise': 'error',
    // `void promise` is the marker `typescript/no-floating-promises` prescribes for a deliberate
    // fire-and-forget (CLI entry, Vite middleware, browser event handlers); `void 0` stays banned.
    'no-void': ['error', { allowAsStatement: true }],
    'no-empty': 'error',
    'no-empty-function': 'error',
    'unicode-bom': 'error',
    'new-cap': 'error',
    // A `${...}` inside a single-quoted string is almost always a template
    // literal that lost its backticks — a real hazard when the product is
    // emitted source. Test fixtures that assert on that exact text opt out
    // in the `*.test.ts` override below.
    'no-template-curly-in-string': 'error',
    // Decisions live in git log / CHANGELOG / PR (CONTRIBUTING.md), not
    // in the source; a parked TODO is the same debt in a different shape.
    'no-warning-comments': 'error',

    // Module graph. `no-default-export` keeps every export named;
    // `extensions` keeps relative specifiers `.js`-suffixed,
    // which NodeNext resolution requires at runtime and `tsc` does not check.
    'import/no-default-export': 'error',
    'import/extensions': ['error', 'always', { ignorePackages: true }],
    'import/first': 'error',
    'import/export': 'error',
    'import/unambiguous': 'error',
    'import/no-commonjs': 'error',
    'import/no-mutable-exports': 'error',
    'import/no-named-default': 'error',
    // Zod (server) and Valibot (client) are imported as namespaces (`import * as z` /
    // `import * as v`) by project convention.
    'import/no-namespace': ['error', { ignore: ['zod', 'valibot'] }],
    'import/no-unassigned-import': 'error',
    'import/no-named-as-default': 'error',
    'import/no-anonymous-default-export': 'error',
    'import/consistent-type-specifier-style': 'error',
    // 120+ of the 123 source files are already kebab-case; this stops the
    // odd camelCase one from re-appearing.
    'unicorn/filename-case': 'error',
  },
  overrides: [
    ...Object.entries(CEILINGS).map(([file, ceiling]) => ceilingOverride(file, ceiling)),
    {
      // Playwright's tests: Node, with the page's globals in the callbacks they hand the page.
      // The unit-test rules (Vitest's) are for src/**/*.test.ts, not for these.
      files: ['e2e/**/*.ts', 'scripts/**/*.ts', 'playwright.config.ts', 'vite.config.ts'],
      env: { node: true, browser: false },
      rules: {
        // Tools run from the command line, one step after another: the synchronous file and
        // process calls are what they are written in, and the environment is how they are told
        // where things are.
        'node/no-sync': 'off',
        'node/no-process-env': 'off',
        'unicorn/no-process-exit': 'off',
        // A test drives one page step by step: each await waits for the one before it.
        'no-await-in-loop': 'off',
        // Playwright names its own `test` and `expect`; the jest rules read them as Vitest's.
        'jest/no-standalone-expect': 'off',
        'jest/expect-expect': 'off',
        'jest/no-done-callback': 'off',
        'jest/valid-title': 'off',
        // A teardown waits on what a test changed, and only when it changed something.
        'jest/no-conditional-in-test': 'off',
      },
    },
    {
      // A config file's contract is a default export; the ban stays on for src.
      files: [
        'vite.config.ts',
        'hono-takibi.config.ts',
        'hono-takibi.hooks.config.ts',
        'playwright.config.ts',
      ],
      rules: {
        'import/no-default-export': 'off',
      },
    },
    {
      // Tests build DMMF fixtures by hand; asserting them into the real
      // ReadonlyDeep<DMMF.*> shapes is the sanctioned `as` exception
      // (CONTRIBUTING.md: tests are exempt from `no as`). Only the rules that police those casts are
      // scoped off here, nothing else is.
      files: ['src/**/*.test.ts'],
      plugins: ['vitest'],
      rules: {
        // A table of cases branches on the case (and the jest copy of the rule reads Vitest's tests too).
        'vitest/no-conditional-in-test': 'off',
        'jest/no-conditional-in-test': 'off',
        'typescript/no-explicit-any': 'off',
        'typescript/consistent-type-assertions': 'off',
        'typescript/no-unsafe-type-assertion': 'off',
        'typescript/no-unsafe-argument': 'off',
        'typescript/no-unsafe-assignment': 'off',
        'typescript/no-unsafe-member-access': 'off',
        'typescript/no-unsafe-call': 'off',
        'typescript/no-unsafe-return': 'off',
        // Fixtures and stubs are defined per test on purpose (CONTRIBUTING.md:
        // no shared logic helpers between tests), which is exactly what this rule flags.
        'unicorn/consistent-function-scoping': 'off',
        // The other vitest rules this suite relies on (no-focused-tests, expect-expect, ...)
        // sit in the correctness / suspicious categories, so enabling the plugin is enough.
        // The Result-returning APIs are asserted by narrowing the union first
        // (`if (!result.ok) expect(result.error)…`), which reads as conditional.
        'vitest/no-conditional-expect': 'off',
        // Fixtures feed and assert on source text that contains a literal
        // `${...}`; here that is the value under test, not a lost backtick.
        'no-template-curly-in-string': 'off',
        'vitest/no-identical-title': 'error',
        'vitest/valid-expect': 'error',
        'vitest/valid-title': 'error',
        'vitest/valid-describe-callback': 'error',
        // An `expect` outside a test case is never run and never reported.
        'vitest/no-standalone-expect': 'error',
        'vitest/no-test-return-statement': 'error',
        'vitest/no-test-prefixes': 'error',
        'vitest/no-duplicate-hooks': 'error',
        'vitest/prefer-hooks-on-top': 'error',
        'vitest/prefer-hooks-in-order': 'error',
        'vitest/consistent-test-it': 'error',
        'vitest/no-alias-methods': 'error',
        // `toStrictEqual` over `toEqual` matches the full-equality rule in
        // CONTRIBUTING.md; `toEqual` ignores `undefined` properties and
        // would let a codegen regression through.
        'vitest/prefer-strict-equal': 'error',
        'vitest/prefer-equality-matcher': 'error',
        'vitest/prefer-called-with': 'error',
        'vitest/require-to-throw-message': 'error',
        'vitest/prefer-each': 'error',
        'vitest/prefer-spy-on': 'error',
        'vitest/no-mocks-import': 'error',
        // Snapshots are a partial-match assertion by another name, so they
        // are kept small and literal where they appear at all.
        'vitest/no-interpolation-in-snapshots': 'error',
        'vitest/no-large-snapshots': 'error',
      },
    },
    {
      // The studio client is browser code bundled by Vite: it only takes the contract types
      // from the server side.
      files: ['src/studio/client/**'],
      env: { browser: true, node: false },
      plugins: ['react', 'jsx-a11y'],
      rules: {
        // Vite never exposes `process` to the browser bundle.
        'no-restricted-globals': ['error', 'process'],
        // The automatic JSX runtime does not import React.
        'react/react-in-jsx-scope': 'off',
        // The hooks contract: rules-of-hooks is pedantic, so it does nothing unless named.
        'react/rules-of-hooks': 'error',
        'react/exhaustive-deps': 'error',
        // A <button> with no type is a submit button inside a form.
        'react/button-has-type': 'error',
        'react/jsx-no-target-blank': 'error',
        'react/jsx-no-script-url': 'error',
        'react/jsx-key': 'error',
        'react/jsx-no-duplicate-props': 'error',
        'react/jsx-no-useless-fragment': 'error',
        'react/jsx-boolean-value': 'error',
        'react/jsx-curly-brace-presence': 'error',
        'react/self-closing-comp': 'error',
        'react/no-array-index-key': 'error',
        'react/no-danger': 'error',
        'react/no-unstable-nested-components': 'error',
        'react/void-dom-elements-no-children': 'error',
        'react/checked-requires-onchange-or-readonly': 'error',
        'react/iframe-missing-sandbox': 'error',
        'react/no-unescaped-entities': 'error',
        'react/no-namespace': 'error',
        'react/style-prop-object': 'error',
        'react/jsx-props-no-spread-multi': 'error',
        'react/only-export-components': 'error',
        // Accessibility rules outside the correctness category.
        'jsx-a11y/anchor-ambiguous-text': 'error',
        'jsx-a11y/no-aria-hidden-on-focusable': 'error',
        'jsx-a11y/prefer-tag-over-role': 'error',
        'no-restricted-imports': [
          'error',
          {
            patterns: [
              {
                regex:
                  '^(\\.\\./)+(bin|cli|core|emit|format|file|generator|helper|utils|server|studio/server)(/.*)?$',
                message:
                  'browser code may only take types from the server (type-only imports of routes are allowed)',
                allowTypeImports: true,
              },
            ],
          },
        ],
      },
    },
    {
      // The ER diagram renderer is shared by the generator (PNG output) and the studio client
      // (export): pure layout and SVG text, with the resvg rasteriser as its only Node-side.
      files: ['src/diagram/**'],
      rules: {
        'no-restricted-imports': [
          'error',
          {
            paths: [
              { name: 'node:fs', message: 'file I/O belongs in src/file' },
              { name: 'node:fs/promises', message: 'file I/O belongs in src/file' },
            ],
            patterns: [
              {
                regex:
                  '^(\\.\\./)+(bin|cli|core|emit|format|file|generator|helper|utils|studio/client|studio/server)(/.*)?$',
                message:
                  'diagram is pure: it only takes the contract types from studio/server/routes',
                allowTypeImports: true,
              },
            ],
          },
        ],
      },
    },
    {
      // The shapes and measures of the ER diagram, shared by the renderer, the generator and
      // Studio's canvas: they read none of those, so any of them can read these. The constants
      // may name a shape; the shapes take only React Flow's, for the canvas's nodes and edges.
      files: ['src/types/**', 'src/constants/**'],
      rules: {
        'no-restricted-imports': [
          'error',
          {
            patterns: [
              {
                group: ['../**', '!../types/**'],
                message:
                  'types and constants are shared leaves: they import nothing of the project but the types',
              },
            ],
          },
        ],
      },
    },
    {
      // A cell editor is focused when the user activates it, not on page load; the rule is
      // about the latter.
      files: ['src/studio/client/components/data-grid.tsx'],
      plugins: ['jsx-a11y'],
      rules: {
        'jsx-a11y/no-autofocus': 'off',
      },
    },
    {
      // The structural conventions (immutability, camelCase logic) describe the Effect
      // backend: studio/server, cli, file, emit, format. The generators build source text
      // imperatively and the React client names components in
      // PascalCase, so those rules stop at their doors.
      files: [
        'src/helper/**',
        'src/generator/**',
        'src/core/**',
        'src/bin/**',
        'src/utils/**',
        'src/sql/**',
        'src/studio/client/**',
      ],
      rules: {
        // The SQL parser and analyzer advance a cursor object they are handed: writing through
        // that parameter is the design, not an accident.
        'no-param-reassign': ['error', { props: false }],
      },
    },
    {
      // A route module exports its `Route` next to the page component by design.
      files: ['src/studio/client/routes/**'],
      plugins: ['react', 'jsx-a11y'],
      rules: {
        'react/only-export-components': 'off',
      },
    },
    {
      // Last override wins for a given rule, so this must stay after the
      // architecture blocks above. Those rules describe the dependency graph
      // of the shipped modules; a test sits outside that graph and reads the
      // filesystem back to prove what the I/O layer actually wrote.
      files: ['src/**/*.test.ts'],
      rules: {
        'no-restricted-imports': 'off',
      },
    },
    {
      // Last, so it holds over the Vitest block above. A test is a list of cases: a describe block
      // is as long as its cases, and a table of cases branches on the case. This file is a list
      // of rules and their reasons.
      files: ['src/**/*.test.ts', 'lint.config.ts'],
      rules: {
        'max-lines-per-function': 'off',
        'max-lines': 'off',
        // A test reads a fixture the way a script does.
        'node/no-sync': 'off',
        'jest/no-conditional-in-test': 'off',
        'vitest/no-conditional-in-test': 'off',
      },
    },
  ],
}
