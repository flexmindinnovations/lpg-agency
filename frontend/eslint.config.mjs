import nx from '@nx/eslint-plugin';

export default [
  ...nx.configs['flat/base'],
  ...nx.configs['flat/typescript'],
  ...nx.configs['flat/javascript'],
  {
    // `libs/shared/data-access/src/lib/generated/**` is ng-openapi-gen
    // output (ADR-032) — regenerated from the committed OpenAPI spec, never
    // hand-edited, so it is not held to hand-written-code lint rules.
    ignores: ['**/dist', '**/out-tsc', '**/lib/generated/**'],
  },
  {
    files: ['**/*.ts', '**/*.tsx', '**/*.js', '**/*.jsx'],
    ignores: ['**/.storybook/**'],
    rules: {
      '@nx/enforce-module-boundaries': [
        'error',
        {
          enforceBuildableLibDependency: true,
          allow: ['^.*/eslint(\\.base)?\\.config\\.[cm]?[jt]s$'],
          // ADR-018: feature libraries must never import each other. Cross-feature
          // communication goes through shared/data-access or router navigation.
          // This is the frontend counterpart of import-linter on the backend —
          // the same principle, enforced the same way, for the same reason.
          depConstraints: [
            {
              sourceTag: 'type:app',
              onlyDependOnLibsWithTags: [
                'type:feature',
                'type:ui',
                'type:util',
                'type:data-access',
                'type:design-tokens',
              ],
            },
            {
              sourceTag: 'type:feature',
              onlyDependOnLibsWithTags: [
                'type:ui',
                'type:util',
                'type:data-access',
                'type:design-tokens',
              ],
            },
            {
              sourceTag: 'type:ui',
              onlyDependOnLibsWithTags: ['type:util', 'type:design-tokens'],
            },
            {
              sourceTag: 'type:data-access',
              onlyDependOnLibsWithTags: ['type:util'],
            },
            { sourceTag: 'type:util', onlyDependOnLibsWithTags: ['type:design-tokens'] },
            { sourceTag: 'type:design-tokens', onlyDependOnLibsWithTags: [] },
          ],
        },
      ],
    },
  },
  {
    files: [
      '**/*.ts',
      '**/*.tsx',
      '**/*.cts',
      '**/*.mts',
      '**/*.js',
      '**/*.jsx',
      '**/*.cjs',
      '**/*.mjs',
    ],
    // Override or add rules here
    rules: {},
  },
];
