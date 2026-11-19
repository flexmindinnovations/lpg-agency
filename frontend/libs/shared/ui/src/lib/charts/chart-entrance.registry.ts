import { Injectable } from '@angular/core';

/**
 * Remembers which charts have already drawn themselves in, for the whole
 * session. A chart that comes back (the user left the page and returned) is
 * drawn at once with its last data, and only later changes animate.
 */
@Injectable({ providedIn: 'root' })
export class ChartEntranceRegistry {
  private readonly played = new Set<string>();

  /** True the first time a key is seen, false on every later call. */
  claim(key: string): boolean {
    if (this.played.has(key)) return false;
    this.played.add(key);
    return true;
  }
}
