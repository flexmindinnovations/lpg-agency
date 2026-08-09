/** A single sidebar navigation destination. */
export interface NavItem {
  readonly label: string;
  /** PrimeIcons class, e.g. `'pi pi-home'`. */
  readonly icon: string;
  readonly route: string;
  /** Passed through to `routerLinkActiveOptions`. Defaults to `false`. */
  readonly exact?: boolean;
  readonly badge?: string | number;
}

/** A labelled group of nav items, or an ungrouped top-level list when `label` is omitted. */
export interface NavGroup {
  readonly label?: string;
  readonly items: readonly NavItem[];
}
