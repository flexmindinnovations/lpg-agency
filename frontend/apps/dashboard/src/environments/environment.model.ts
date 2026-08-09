/**
 * Shared shape for `environment.ts` / `environment.prod.ts`. Kept in its own
 * file because `fileReplacements` (`apps/dashboard/project.json`) swaps the
 * entire contents of `environment.ts` for `environment.prod.ts` in
 * production builds — a type re-exported from `environment.ts` itself would
 * vanish under that swap, since the file importing it and the file defining
 * it would collapse into the same file.
 */
export interface Environment {
  readonly production: boolean;
  readonly apiUrl: string;
}
