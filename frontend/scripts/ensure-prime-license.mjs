// Creates apps/dashboard/src/app/prime-license.ts from the committed example
// when it is missing (QA finding SU-03).
//
// app.config.ts imports `./prime-license`, which is git-ignored because a real
// deployment pastes its PrimeNG licence key there. On a fresh clone the file
// did not exist, so `nx serve dashboard` failed with "Could not resolve
// './prime-license'" until someone copied it by hand. The example exports
// `undefined`, which PrimeNG treats as "unlicensed" - fine for local work.
// An existing file (with a real key) is never touched. In the Docker build
// `npm ci` runs before the sources are copied, so there is no example yet;
// the Dockerfile creates the file itself later.
import { copyFileSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const appDir = join(
  dirname(fileURLToPath(import.meta.url)),
  '..',
  'apps',
  'dashboard',
  'src',
  'app',
);
const target = join(appDir, 'prime-license.ts');
const example = join(appDir, 'prime-license.example.ts');

if (!existsSync(target) && existsSync(example)) {
  copyFileSync(example, target);
  console.log('Created apps/dashboard/src/app/prime-license.ts from the example (no licence key).');
}
