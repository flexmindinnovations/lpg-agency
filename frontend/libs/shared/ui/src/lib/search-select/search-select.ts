import {
  ChangeDetectionStrategy,
  Component,
  computed,
  forwardRef,
  inject,
  input,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ControlValueAccessor, FormsModule, NG_VALUE_ACCESSOR } from '@angular/forms';
import { FilterService } from 'primeng/api';
import { Select } from 'primeng/select';
import { Observable, Subject, catchError, debounce, map, of, switchMap, timer } from 'rxjs';

/** What the list can hold: anything with an id. */
export interface SearchSelectItem {
  readonly id: string;
}

interface SearchOption<T> {
  readonly label: string;
  readonly detail: string;
  readonly item: T;
}

/** The server has already searched, so the dropdown keeps every answer. */
const SERVER_MATCH = 'lpgServerMatch';
const TYPING_PAUSE_MS = 300;

/**
 * A dropdown whose search runs on the server, for lists too long to load at
 * once (customers). It is the same `p-select` as every other dropdown: opening
 * it lists the first matches and its search box asks the server for more.
 */
@Component({
  selector: 'lpg-search-select',
  standalone: true,
  imports: [FormsModule, Select],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <p-select
      [inputId]="inputId()"
      [options]="options()"
      optionLabel="label"
      optionValue="item"
      [ngModel]="selected()"
      [ngModelOptions]="{ standalone: true }"
      (ngModelChange)="pick($event)"
      [filter]="true"
      [resetFilterOnHide]="true"
      filterBy="label"
      [filterMatchMode]="matchMode"
      [loading]="loading()"
      [placeholder]="placeholder()"
      [pt]="searchBox()"
      [disabled]="disabled()"
      [emptyMessage]="message()"
      [emptyFilterMessage]="message()"
      [fluid]="true"
      (onShow)="ask('')"
      (onFilter)="ask($event.filter ?? '')"
      (onHide)="query.set('')"
      (onBlur)="onTouched()"
    >
      <ng-template let-option #item>
        <div class="search-select__option">
          <strong>{{ option.label }}</strong>
          @if (option.detail) {
            <span class="search-select__detail">· {{ option.detail }}</span>
          }
        </div>
      </ng-template>
    </p-select>
  `,
  styles: [
    `
      :host {
        display: block;
      }
      .search-select__option {
        display: flex;
        flex-wrap: wrap;
        align-items: baseline;
        gap: var(--spacing-xs);
      }
      .search-select__detail {
        color: var(--color-text-secondary);
        font-size: var(--typography-caption-font-size);
      }
    `,
  ],
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => SearchSelect),
      multi: true,
    },
  ],
})
export class SearchSelect<T extends SearchSelectItem> implements ControlValueAccessor {
  /** Runs the search; an empty query asks for the first entries. */
  readonly search = input.required<(query: string) => Observable<readonly T[]>>();
  /** The words shown for an item, in the list and once picked. */
  readonly itemLabel = input.required<(item: T) => string>();
  /** A second, quieter line of facts that tell two items apart. */
  readonly itemDetail = input<(item: T) => string>(() => '');
  readonly inputId = input.required<string>();
  readonly placeholder = input('Select');
  readonly noMatchMessage = input('No matches');
  /** What the search box says it can search by. */
  readonly searchHint = input('Search');

  protected readonly matchMode = SERVER_MATCH as unknown as 'contains';
  protected readonly selected = signal<T | null>(null);
  protected readonly disabled = signal(false);
  protected readonly loading = signal(false);
  protected readonly query = signal('');
  private readonly results = signal<readonly T[]>([]);
  private readonly failed = signal(false);

  protected readonly message = computed(() => {
    if (this.loading()) return 'Searching…';
    return this.failed() ? "Couldn't load the list. Try again." : this.noMatchMessage();
  });

  protected readonly options = computed<SearchOption<T>[]>(() => {
    const results = this.results();
    const picked = this.selected();
    // The picked item must stay in the list, or the closed field goes blank.
    const missing =
      picked !== null && this.query() === '' && !results.some((item) => item.id === picked.id);
    return (missing ? [picked, ...results] : results).map((item) => ({
      label: this.itemLabel()(item),
      detail: this.itemDetail()(item),
      item,
    }));
  });

  /** Replaces the app-wide "Search" wording on this dropdown's search box. */
  protected readonly searchBox = computed(() => ({
    pcFilter: { root: { placeholder: this.searchHint(), 'aria-label': this.searchHint() } },
  }));

  private readonly queries = new Subject<string>();

  constructor() {
    inject(FilterService).register(SERVER_MATCH, () => true);
    this.queries
      .pipe(
        // The first list comes at once; typing waits for a pause.
        debounce((query) => (query ? timer(TYPING_PAUSE_MS) : of(0))),
        // A newer query drops the answer to an older one.
        switchMap((query) =>
          this.search()(query).pipe(
            map((items) => ({ items, failed: false })),
            catchError(() => of({ items: [] as readonly T[], failed: true })),
          ),
        ),
        takeUntilDestroyed(),
      )
      .subscribe(({ items, failed }) => {
        this.results.set(items);
        this.failed.set(failed);
        this.loading.set(false);
      });
  }

  protected ask(query: string): void {
    const tidy = query.replace(/\s+/g, ' ').trim();
    this.query.set(tidy);
    this.loading.set(true);
    this.queries.next(tidy);
  }

  protected pick(item: T | null): void {
    this.selected.set(item);
    this.onChange(item);
  }

  // eslint-disable-next-line @typescript-eslint/no-empty-function -- overwritten by registerOnChange
  private onChange: (value: T | null) => void = () => {};
  // eslint-disable-next-line @typescript-eslint/no-empty-function -- overwritten by registerOnTouched
  protected onTouched: () => void = () => {};

  writeValue(value: T | null): void {
    this.selected.set(value ?? null);
    if (!value) this.results.set([]);
  }

  registerOnChange(fn: (value: T | null) => void): void {
    this.onChange = fn;
  }

  registerOnTouched(fn: () => void): void {
    this.onTouched = fn;
  }

  setDisabledState(isDisabled: boolean): void {
    this.disabled.set(isDisabled);
  }
}
