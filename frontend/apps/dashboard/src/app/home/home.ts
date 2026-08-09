import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ButtonDirective } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Select } from 'primeng/select';
import { Dialog } from 'primeng/dialog';
import { Tab, TabList, TabPanel, TabPanels, Tabs } from 'primeng/tabs';
import { Card } from 'primeng/card';
import { Breadcrumb } from 'primeng/breadcrumb';
import type { MenuItem } from 'primeng/api';
import { MessageService } from 'primeng/api';
import { ProgressBar } from 'primeng/progressbar';
import { Toast } from 'primeng/toast';
import { Tooltip } from 'primeng/tooltip';

/**
 * Placeholder landing view — replaced by the real dashboard in a later phase.
 *
 * The "PrimeNG foundation" section below is **infrastructure verification,
 * not a business feature** (ADR-028, ADR-020 amendment): it exists to prove
 * the design-token-driven preset (`libs/shared/design-tokens/src/lib
 * /primeng-preset.ts`) actually renders correctly — themed, accessible,
 * responsive to light/dark/high-contrast — the same role the AG Grid
 * wrapper's own rendering test served for ADR-020. No component here is
 * wrapped; feature libraries import PrimeNG components directly, exactly as
 * shown, unless a specific component earns an application-level wrapper on
 * its own merits (reusability, accessibility, consistency, vendor
 * isolation) — none of the ones below do.
 */
@Component({
  selector: 'lpg-home',
  standalone: true,
  imports: [
    FormsModule,
    ButtonDirective,
    InputText,
    Select,
    Dialog,
    Tabs,
    TabList,
    Tab,
    TabPanels,
    TabPanel,
    Card,
    Breadcrumb,
    ProgressBar,
    Toast,
    Tooltip,
  ],
  providers: [MessageService],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <p-toast />

    <h1 class="page-title">Repository foundation</h1>
    <p class="page-lede">
      The Angular workspace, design-token system and shared libraries are in place. Business
      features have not been built yet.
    </p>

    <section class="card" aria-labelledby="foundation-heading">
      <h2 id="foundation-heading" class="card__title">What exists</h2>
      <ul class="card__list">
        <li>Nx workspace with enforced feature-library boundaries</li>
        <li>Design tokens — light, dark and high-contrast themes</li>
        <li>Shared UI, util and data-access libraries</li>
        <li>RFC 7807 error handling and correlation IDs</li>
        <li>PrimeNG — primary component library, AG Grid Community — default data grid</li>
      </ul>
    </section>

    <section class="card" aria-labelledby="primeng-heading" style="margin-top: var(--spacing-lg)">
      <h2 id="primeng-heading" class="card__title">PrimeNG foundation</h2>
      <p class="page-lede" style="margin-bottom: var(--spacing-lg)">
        Every colour below comes from the same design tokens the rest of the app uses — switch theme
        to confirm nothing here is hardcoded.
      </p>

      <p-breadcrumb [model]="breadcrumbItems" [home]="breadcrumbHome" />

      <div
        style="display: flex; gap: var(--spacing-sm); align-items: center; margin-top: var(--spacing-lg); flex-wrap: wrap;"
      >
        <button pButton type="button" (click)="showToast()">Primary action</button>
        <button pButton type="button" [outlined]="true">Outlined</button>
        <button
          #dialogTriggerEl
          pButton
          type="button"
          severity="secondary"
          (click)="dialogVisible.set(true)"
          pTooltip="Opens a focus-trapped, keyboard-dismissible dialog"
          tooltipPosition="top"
        >
          Open dialog
        </button>
      </div>

      <div
        style="display: flex; gap: var(--spacing-md); margin-top: var(--spacing-lg); flex-wrap: wrap;"
      >
        <div>
          <label
            for="demo-name"
            class="shell__theme-label"
            style="display: block; margin-bottom: var(--spacing-xs)"
          >
            Name
          </label>
          <input pInputText id="demo-name" type="text" [(ngModel)]="nameValue" name="name" />
        </div>
        <div>
          <label
            for="demo-branch"
            class="shell__theme-label"
            style="display: block; margin-bottom: var(--spacing-xs)"
          >
            Branch
          </label>
          <p-select
            inputId="demo-branch"
            [options]="branchOptions"
            optionLabel="label"
            [(ngModel)]="selectedBranch"
            placeholder="Select a branch"
            [style]="{ minWidth: '12rem' }"
          />
        </div>
      </div>

      <p-tabs [value]="'0'" style="margin-top: var(--spacing-lg); display: block;">
        <p-tablist>
          <p-tab value="0">Overview</p-tab>
          <p-tab value="1">Details</p-tab>
        </p-tablist>
        <p-tabpanels>
          <p-tabpanel value="0">
            <p-card header="Foundation status" style="max-inline-size: 40ch;">
              <p>PrimeNG, AG Grid Community, Angular CDK, Tailwind CSS v4 — all token-driven.</p>
            </p-card>
          </p-tabpanel>
          <p-tabpanel value="1">
            <p>Rollout progress</p>
            <p-progressbar [value]="72" />
          </p-tabpanel>
        </p-tabpanels>
      </p-tabs>

      <p-dialog
        header="PrimeNG Dialog"
        [(visible)]="dialogVisibleModel"
        [modal]="true"
        [style]="{ width: '28rem' }"
        [closeOnEscape]="true"
        [dismissableMask]="true"
        (onHide)="dialogTrigger()?.nativeElement?.focus()"
      >
        <p>
          This dialog traps focus, closes on <kbd>Escape</kbd>, and returns focus to the button that
          opened it — verified against WCAG 2.2 AA (Phase 1 requirement, D-35).
        </p>
        <button pButton type="button" (click)="dialogVisible.set(false)">Close</button>
      </p-dialog>
    </section>
  `,
})
export class Home {
  protected readonly nameValue = signal('');
  protected readonly dialogVisible = signal(false);
  protected readonly selectedBranch = signal<{ label: string; value: string } | undefined>(
    undefined,
  );

  protected readonly branchOptions = [
    { label: 'Main Branch', value: 'main' },
    { label: 'North Branch', value: 'north' },
    { label: 'South Branch', value: 'south' },
  ];

  protected readonly breadcrumbHome: MenuItem = { icon: 'pi pi-home', routerLink: '/' };
  protected readonly breadcrumbItems: MenuItem[] = [{ label: 'Foundation' }, { label: 'PrimeNG' }];

  // PrimeNG's Dialog has no built-in "return focus to trigger" behaviour
  // (checked primeng-dialog.d.ts — no restoreFocus/returnFocus input exists),
  // so WCAG 2.2 AA focus-return-on-close (D-35) has to be done explicitly.
  protected readonly dialogTrigger = viewChild<ElementRef<HTMLButtonElement>>('dialogTriggerEl');

  // p-dialog's [(visible)] two-way-binds to a plain property, not a signal
  // directly, in this PrimeNG version — a thin getter/setter bridges it to
  // the signal so the rest of the component stays signal-first (ADR-019).
  protected get dialogVisibleModel(): boolean {
    return this.dialogVisible();
  }
  protected set dialogVisibleModel(value: boolean) {
    this.dialogVisible.set(value);
  }

  private readonly messageService = inject(MessageService);

  protected showToast(): void {
    this.messageService.add({
      severity: 'success',
      summary: 'Foundation verified',
      detail: 'PrimeNG is wired to the design-token system.',
      life: 4000,
    });
  }
}
