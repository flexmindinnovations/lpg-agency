import { InjectionToken } from '@angular/core';

/**
 * Full-page navigation (`window.location.assign`), injectable so tests can
 * observe it.
 *
 * Used where the SPA router cannot be trusted to complete a navigation: signing
 * out, and the "session expired" dialog. A tab left open across a deploy still
 * runs the old build, whose lazy-loaded files (the login page included) no
 * longer exist on the server, so `router.navigate('/login')` fails silently
 * there and the user is stuck on a dead page. A real page load always fetches
 * the current `index.html` and its files.
 */
export const HARD_NAVIGATE = new InjectionToken<(url: string) => void>('HARD_NAVIGATE', {
  providedIn: 'root',
  factory: () => (url: string) => window.location.assign(url),
});

const STALE_ASSET_PATTERN = new RegExp(
  [
    'Failed to fetch dynamically imported module',
    'error loading dynamically imported module',
    'Importing a module script failed',
    'Loading chunk [\\w-]+ failed',
    'ChunkLoadError',
    // The server answers a missing file with `index.html` (SPA fallback), which the
    // browser then fails to parse as JavaScript.
    "Unexpected token '<'",
    'not a valid JavaScript MIME type',
    'Expected a JavaScript(-or-Wasm)? module script',
  ].join('|'),
  'i',
);

/** True when a navigation failed because a lazy-loaded file no longer exists (a stale tab). */
export function isStaleAssetError(error: unknown): boolean {
  const text = error instanceof Error ? `${error.name}: ${error.message}` : String(error);
  return STALE_ASSET_PATTERN.test(text);
}

const RELOAD_GUARD_KEY = 'lpg:stale-asset-reload';
const RELOAD_GUARD_MS = 15_000;

/**
 * Reloads `url` once so a stale tab picks up the current build. A second stale-asset
 * failure within 15 seconds is left alone, so a genuinely broken deploy cannot put the
 * browser in a reload loop. Returns whether it reloaded.
 */
export function reloadOnceForStaleAsset(
  url: string,
  hardNavigate: (url: string) => void,
  now: number = Date.now(),
  storage: Pick<Storage, 'getItem' | 'setItem'> | null = safeSessionStorage(),
): boolean {
  const last = Number(storage?.getItem(RELOAD_GUARD_KEY) ?? 0);
  if (last && now - last < RELOAD_GUARD_MS) return false;
  storage?.setItem(RELOAD_GUARD_KEY, String(now));
  hardNavigate(url);
  return true;
}

function safeSessionStorage(): Storage | null {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}
