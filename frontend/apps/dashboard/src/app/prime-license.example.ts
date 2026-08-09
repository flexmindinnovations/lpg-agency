/**
 * PrimeNG license key — local override template.
 *
 * Copy this file to `prime-license.ts` (git-ignored, see root `.gitignore`)
 * and paste your real key there. Mirrors the AG Grid Enterprise pattern
 * (`AG_GRID_LICENSE_KEY`, ADR-020): the real value is never committed, is
 * supplied per-environment by whoever owns it, and its absence must not
 * break the build — PrimeNG simply runs unlicensed (shows its own banner)
 * until a real key is supplied locally or via CI secret injection.
 */
export const PRIME_NG_LICENSE_KEY: string | undefined = undefined;
