module.exports = {
  displayName: 'dashboard',
  preset: '../../jest.preset.js',
  setupFilesAfterEnv: ['<rootDir>/src/test-setup.ts'],
  coverageDirectory: '../../coverage/apps/dashboard',
  transform: {
    '^.+\\.(ts|mjs|js|html)$': [
      'jest-preset-angular',
      {
        tsconfig: '<rootDir>/tsconfig.spec.json',
        stringifyContentPathRegex: '\\.(html|svg)$',
      },
    ],
  },
  // .mjs is always transformed. @primeui/@noble are added explicitly:
  // primeng/menu's licence-check machinery pulls in @primeui/license-manager,
  // which depends on @noble/ed25519 and @noble/hashes — both ship ESM `export`
  // syntax in plain `.js` files (not `.mjs`), which the .mjs-only allowlist
  // doesn't catch, so Jest tried to run them as CommonJS and failed.
  transformIgnorePatterns: ['node_modules/(?!(@primeui|@noble)|.*\\.mjs$)'],
  snapshotSerializers: [
    'jest-preset-angular/build/serializers/no-ng-attributes',
    'jest-preset-angular/build/serializers/ng-snapshot',
    'jest-preset-angular/build/serializers/html-comment',
  ],
};
