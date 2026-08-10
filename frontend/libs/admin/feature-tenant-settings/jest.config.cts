module.exports = {
  displayName: 'admin-feature-tenant-settings',
  preset: '../../../jest.preset.js',
  setupFilesAfterEnv: ['<rootDir>/src/test-setup.ts'],
  coverageDirectory: '../../../coverage/libs/admin/feature-tenant-settings',
  transform: {
    '^.+\\.(ts|mjs|js|html)$': [
      'jest-preset-angular',
      {
        tsconfig: '<rootDir>/tsconfig.spec.json',
        stringifyContentPathRegex: '\\.(html|svg)$',
      },
    ],
  },
  // primeng/button (license-manager -> @noble/ed25519) ships ESM-only `.js`
  // — same fix already applied in apps/dashboard and libs/shared/ui's own
  // jest configs, needed here for the same reason (login-page imports
  // ButtonDirective).
  transformIgnorePatterns: ['node_modules/(?!(@primeui|@noble)|.*\\.mjs$)'],
  snapshotSerializers: [
    'jest-preset-angular/build/serializers/no-ng-attributes',
    'jest-preset-angular/build/serializers/ng-snapshot',
    'jest-preset-angular/build/serializers/html-comment',
  ],
};
