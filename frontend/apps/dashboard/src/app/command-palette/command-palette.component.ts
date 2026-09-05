import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  computed,
  effect,
  inject,
  input,
  signal,
  viewChild,
} from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { DOCUMENT } from '@angular/common';
import { Router } from '@angular/router';
import { catchError, debounceTime, distinctUntilChanged, map, of, switchMap } from 'rxjs';
import type { NavItem } from '@lpg/shared/ui/app-shell';
import { CustomerService } from '@lpg/shared/data-access';
import { CommandPaletteService } from './command-palette.service';

interface PaletteItem {
  readonly id: string;
  readonly label: string;
  readonly icon: string;
  readonly sublabel?: string;
  readonly run: () => void;
}

interface PaletteGroup {
  readonly label: string;
  readonly items: readonly PaletteItem[];
}

/** Subsequence-aware match score. 0 = no match; higher = better. */
export function fuzzyScore(text: string, q: string): number {
  if (!q) return 1;
  const t = text.toLowerCase();
  const query = q.toLowerCase();
  const idx = t.indexOf(query);
  if (idx !== -1) return 1000 - idx;
  let ti = 0;
  let score = 0;
  for (const ch of query) {
    const found = t.indexOf(ch, ti);
    if (found === -1) return 0;
    score += found === ti ? 3 : 1;
    ti = found + 1;
  }
  return score;
}

@Component({
  selector: 'lpg-command-palette',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (palette.isOpen()) {
      <div class="cmdk" (pointerdown)="onBackdrop($event)">
        <div
          class="cmdk__panel"
          role="dialog"
          aria-modal="true"
          aria-label="Command palette"
          (keydown)="onKeydown($event)"
        >
          <div class="cmdk__search">
            <i class="pi pi-search" aria-hidden="true"></i>
            <input
              #inputEl
              class="cmdk__input"
              type="text"
              placeholder="Search pages, customers, actions…"
              [value]="query()"
              (input)="query.set($any($event.target).value)"
              role="combobox"
              aria-expanded="true"
              aria-controls="cmdk-list"
              [attr.aria-activedescendant]="activeId() || null"
              autocomplete="off"
              spellcheck="false"
            />
            <kbd class="cmdk__kbd">Esc</kbd>
          </div>

          <ul id="cmdk-list" class="cmdk__list" role="listbox">
            @for (group of groups(); track group.label) {
              <li class="cmdk__group" role="presentation">{{ group.label }}</li>
              @for (item of group.items; track item.id) {
                <!-- ARIA combobox pattern: options aren't tab stops; the
                     input owns focus and points here via aria-activedescendant.
                     Keyboard activation is the input's Enter handler. -->
                <!-- eslint-disable-next-line @angular-eslint/template/click-events-have-key-events, @angular-eslint/template/interactive-supports-focus -->
                <li
                  [id]="item.id"
                  class="cmdk__item"
                  [class.is-active]="item.id === activeId()"
                  role="option"
                  [attr.aria-selected]="item.id === activeId()"
                  (click)="item.run(); palette.close()"
                  (mouseenter)="activeId.set(item.id)"
                >
                  <i class="{{ item.icon }}" aria-hidden="true"></i>
                  <span class="cmdk__label">{{ item.label }}</span>
                  @if (item.sublabel) {
                    <span class="cmdk__sub">{{ item.sublabel }}</span>
                  }
                </li>
              }
            }
            @if (flat().length === 0) {
              <li class="cmdk__empty">No results for “{{ query() }}”.</li>
            }
          </ul>

          <div class="cmdk__hints" aria-hidden="true">
            <span><kbd>↑</kbd><kbd>↓</kbd> navigate</span>
            <span><kbd>↵</kbd> select</span>
            <span><kbd>esc</kbd> close</span>
          </div>
        </div>
      </div>
    }
  `,
  styles: [
    `
      .cmdk {
        position: fixed;
        inset: 0;
        z-index: var(--z-index-modal);
        display: flex;
        justify-content: center;
        align-items: flex-start;
        padding-block-start: 12vh;
        background: color-mix(in srgb, var(--primitive-color-neutral-0), transparent 45%);
        backdrop-filter: blur(2px);
        -webkit-backdrop-filter: blur(2px);
        animation: cmdk-fade var(--motion-duration-small) var(--motion-easing-emphasized) both;
      }

      .cmdk__panel {
        inline-size: min(92vw, 40rem);
        max-block-size: 60vh;
        display: flex;
        flex-direction: column;
        background: var(--surface-acrylic);
        backdrop-filter: var(--surface-acrylic-blur);
        -webkit-backdrop-filter: var(--surface-acrylic-blur);
        border: var(--border-width) solid var(--surface-acrylic-border);
        border-radius: var(--radius-dialog);
        box-shadow: var(--surface-acrylic-shadow);
        overflow: hidden;
        animation: cmdk-in var(--motion-duration-medium) var(--motion-easing-emphasized) both;
      }

      .cmdk__search {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
        padding: var(--spacing-md);
        border-block-end: var(--border-width) solid var(--color-border-default);
      }

      .cmdk__search .pi-search {
        color: var(--color-text-secondary);
        font-size: var(--icon-size-sm);
      }

      .cmdk__input {
        flex: 1;
        border: none;
        background: transparent;
        outline: none;
        color: var(--color-text-primary);
        font-size: var(--typography-body-font-size);
        font-family: inherit;
      }

      .cmdk__input::placeholder {
        color: var(--color-text-secondary);
      }

      .cmdk__list {
        list-style: none;
        margin: 0;
        padding: var(--spacing-xs);
        overflow-y: auto;
        flex: 1;
      }

      .cmdk__group {
        padding: var(--spacing-sm) var(--spacing-sm) var(--spacing-xs);
        font-size: 11px;
        font-weight: var(--typography-label-font-weight);
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--color-text-secondary);
      }

      .cmdk__item {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
        padding: var(--spacing-sm);
        border-radius: var(--radius-input);
        cursor: pointer;
        color: var(--color-text-primary);
        font-size: var(--typography-secondary-font-size);
      }

      .cmdk__item.is-active {
        background: var(--color-highlight-background);
      }

      .cmdk__item i {
        color: var(--color-text-secondary);
        font-size: var(--icon-size-sm);
        inline-size: 1.25rem;
        text-align: center;
      }

      .cmdk__label {
        flex: 1;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .cmdk__sub {
        color: var(--color-text-secondary);
        font-size: var(--typography-caption-font-size);
      }

      .cmdk__empty {
        padding: var(--spacing-lg) var(--spacing-sm);
        text-align: center;
        color: var(--color-text-secondary);
        font-size: var(--typography-secondary-font-size);
      }

      .cmdk__hints {
        display: flex;
        gap: var(--spacing-md);
        padding: var(--spacing-sm) var(--spacing-md);
        border-block-start: var(--border-width) solid var(--color-border-default);
        font-size: var(--typography-caption-font-size);
        color: var(--color-text-secondary);
      }

      kbd {
        display: inline-block;
        min-inline-size: 1.1rem;
        padding: 1px 4px;
        border: var(--border-width) solid var(--color-border-strong);
        border-radius: var(--radius-xs);
        background: var(--color-surface-overlay);
        font-family: inherit;
        font-size: 10px;
        line-height: 1.4;
        text-align: center;
      }

      .cmdk__hints kbd {
        margin-inline-end: 2px;
      }

      @keyframes cmdk-fade {
        from {
          opacity: 0;
        }
      }

      @keyframes cmdk-in {
        from {
          opacity: 0;
          transform: translateY(-6px) scale(0.98);
        }
      }

      @media (prefers-reduced-motion: reduce) {
        .cmdk,
        .cmdk__panel {
          animation: none;
        }
      }
    `,
  ],
})
export class CommandPaletteComponent {
  protected readonly palette = inject(CommandPaletteService);
  private readonly router = inject(Router);
  private readonly customerService = inject(CustomerService);
  private readonly document = inject(DOCUMENT);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);

  readonly navItems = input<readonly NavItem[]>([]);

  protected readonly query = signal('');
  protected readonly activeId = signal('');

  private readonly inputEl = viewChild<ElementRef<HTMLInputElement>>('inputEl');

  private readonly actions: readonly PaletteItem[] = [
    {
      id: 'act-new-order',
      label: 'New order',
      icon: 'pi pi-plus',
      run: () => void this.router.navigate(['/orders'], { queryParams: { create: true } }),
    },
    {
      id: 'act-new-customer',
      label: 'New customer',
      icon: 'pi pi-user-plus',
      run: () => void this.router.navigateByUrl('/customers/new'),
    },
  ];

  /** Live customer lookup — debounced, min 2 chars, best-effort. */
  private readonly customerHits = toSignal(
    toObservable(this.query).pipe(
      map((q) => q.trim()),
      debounceTime(200),
      distinctUntilChanged(),
      switchMap((q) =>
        q.length < 2
          ? of<PaletteItem[]>([])
          : this.customerService.list(0, 6, q).pipe(
              map((page) =>
                page.items.map<PaletteItem>((c) => ({
                  id: `cust-${c.id}`,
                  label: c.full_name,
                  sublabel: c.phone_number,
                  icon: 'pi pi-user',
                  run: () =>
                    void this.router.navigate(['/customers'], { queryParams: { id: c.id } }),
                })),
              ),
              catchError(() => of<PaletteItem[]>([])),
            ),
      ),
    ),
    { initialValue: [] as PaletteItem[] },
  );

  protected readonly groups = computed<readonly PaletteGroup[]>(() => {
    const q = this.query().trim();
    const rank = (items: readonly PaletteItem[]) =>
      items
        .map((it) => ({ it, s: fuzzyScore(it.label, q) }))
        .filter((x) => x.s > 0)
        .sort((a, b) => b.s - a.s)
        .map((x) => x.it);

    const nav = rank(
      this.navItems().map((n) => ({
        id: `nav-${n.route}`,
        label: n.label,
        icon: n.icon,
        run: () => void this.router.navigateByUrl(n.route),
      })),
    ).slice(0, 7);

    const out: PaletteGroup[] = [];
    if (nav.length) out.push({ label: 'Navigation', items: nav });
    if (this.customerHits().length) out.push({ label: 'Customers', items: this.customerHits() });
    const acts = rank(this.actions);
    if (acts.length) out.push({ label: 'Actions', items: acts });
    return out;
  });

  protected readonly flat = computed(() => this.groups().flatMap((g) => g.items));

  constructor() {
    // On open: reset, focus the input, prime the active row.
    effect(() => {
      if (this.palette.isOpen()) {
        this.query.set('');
        queueMicrotask(() => this.inputEl()?.nativeElement.focus());
      }
    });
    // Keep a valid active row as results change.
    effect(() => {
      const items = this.flat();
      if (!items.some((i) => i.id === this.activeId())) {
        this.activeId.set(items[0]?.id ?? '');
      }
    });
  }

  protected onKeydown(event: KeyboardEvent): void {
    const items = this.flat();
    switch (event.key) {
      case 'Escape':
        event.preventDefault();
        this.palette.close();
        break;
      case 'ArrowDown':
        event.preventDefault();
        this.move(items, 1);
        break;
      case 'ArrowUp':
        event.preventDefault();
        this.move(items, -1);
        break;
      case 'Enter': {
        event.preventDefault();
        const active = items.find((i) => i.id === this.activeId());
        if (active) {
          active.run();
          this.palette.close();
        }
        break;
      }
    }
  }

  protected onBackdrop(event: PointerEvent): void {
    const panel = this.host.nativeElement.querySelector('.cmdk__panel');
    if (panel && !panel.contains(event.target as Node)) {
      this.palette.close();
    }
  }

  private move(items: readonly PaletteItem[], delta: number): void {
    if (!items.length) return;
    const current = items.findIndex((i) => i.id === this.activeId());
    const next = (current + delta + items.length) % items.length;
    this.activeId.set(items[next].id);
    const id = items[next].id;
    queueMicrotask(() =>
      this.document.getElementById(id)?.scrollIntoView?.({ block: 'nearest' }),
    );
  }
}
