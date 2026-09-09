import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import {
  FormArray,
  FormControl,
  FormGroup,
  NonNullableFormBuilder,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { forkJoin } from 'rxjs';
import { ButtonDirective } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { InputNumber } from 'primeng/inputnumber';
import { Select } from 'primeng/select';
import { Message } from 'primeng/message';
import { AdminTenantConfigurationService, NotifyService } from '@lpg/shared/data-access';
import { FormFieldComponent } from '@lpg/shared/ui';

type BandGroup = FormGroup<{
  stars: FormControl<number>;
  maxDays: FormControl<number | null>;
}>;

type FineRuleGroup = FormGroup<{
  consecutiveLowQuarters: FormControl<number>;
  finePercent: FormControl<number>;
}>;

const STAR_OPTIONS = [5, 4, 3, 2, 1].map((stars) => ({ label: `${stars} ★`, value: stars }));

/** A reasonable starting template — every number here is a placeholder,
 * never a value this form treats as already-confirmed. Shown only when the
 * tenant has no `tdt_star_rating_bands`/`tdt_fine_schedule` configured yet;
 * nothing is written until the user reviews it and clicks Save. */
const DEFAULT_BANDS: { stars: number; maxDays: number | null }[] = [
  { stars: 5, maxDays: 1 },
  { stars: 4, maxDays: 2 },
  { stars: 3, maxDays: 3 },
  { stars: 2, maxDays: 5 },
  { stars: 1, maxDays: null },
];

interface RawBand {
  stars: number;
  max_days: number | null;
}

interface RawFineRule {
  consecutive_low_quarters: number;
  fine_percent: string;
}

/**
 * TDT rating band / fine-schedule config sub-form (Phase 20 subsystem 2,
 * stage 6 of 7) — a structured editor for the `tdt_star_rating_bands` and
 * `tdt_fine_schedule` `TenantConfiguration` keys, which the generic
 * "Set a configuration value" single-line input on the Tenant Config page
 * can't reasonably edit. Posts through the *existing*
 * `AdminTenantConfigurationService.setConfiguration(...)` — no dedicated
 * backend endpoint. Reached from a link on that page, not a new top-level
 * nav entry.
 *
 * Mirrors `domain/compliance/tdt_rating.py`'s own `_validate_bands` shape
 * client-side (stars 1-5, ascending `max_days`, only the last band
 * unbounded) so an invalid config is caught before the round-trip, not
 * just after — same reasoning `feature-scales.ts`'s `MAX_LEAST_COUNT_GRAMS`
 * check documents.
 */
@Component({
  selector: 'lpg-tdt-rating-config',
  standalone: true,
  imports: [
    HeaderTitlePortalDirective,
    RouterLink,
    ReactiveFormsModule,
    ButtonDirective,
    InputText,
    InputNumber,
    Select,
    Message,
    FormFieldComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './tdt-rating-config.html',
  styleUrl: './tdt-rating-config.css',
})
export class TdtRatingConfig implements OnInit {
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly configService = inject(AdminTenantConfigurationService);
  private readonly notify = inject(NotifyService);

  protected readonly starOptions = STAR_OPTIONS;
  protected readonly loading = signal(false);
  protected readonly saving = signal(false);
  protected readonly hadExistingBands = signal(false);
  protected readonly hadExistingFineSchedule = signal(false);

  protected readonly form = this.fb.group({
    mdgEdition: ['MDG-2022', [Validators.required]],
    bands: this.fb.array<BandGroup>(DEFAULT_BANDS.map((b) => this.newBandGroup(b.stars, b.maxDays))),
    fineRules: this.fb.array<FineRuleGroup>([]),
  });

  protected get bands(): FormArray<BandGroup> {
    return this.form.controls.bands;
  }

  protected get fineRules(): FormArray<FineRuleGroup> {
    return this.form.controls.fineRules;
  }

  /** Plain methods, not `computed()` — reactive forms mutate `FormArray`/
   * `FormControl` values in place rather than through signals, so a memoized
   * `computed()` here would go stale. Re-evaluated on every change-detection
   * pass instead (a handful of rows — no perf concern), same as the
   * template calling a getter directly. */
  protected bandRows() {
    return this.bands.controls.map((control, index) => ({
      control,
      index,
      isLast: index === this.bands.length - 1,
    }));
  }

  /** The ascending-`max_days` ordering check `_validate_bands` enforces —
   * surfaced here so the error shows before submit, not only after a 422. */
  protected bandOrderError(): string | null {
    const finite = this.bands.controls
      .map((c) => c.controls.maxDays.value)
      .filter((d): d is number => d !== null);
    for (let i = 1; i < finite.length; i++) {
      if (finite[i] <= finite[i - 1]) {
        return 'Max days must strictly increase from the top row down to the last, unbounded row.';
      }
    }
    return null;
  }

  ngOnInit(): void {
    this.loading.set(true);
    forkJoin({
      bands: this.configService.getEffectiveConfiguration('tdt_star_rating_bands'),
      fineSchedule: this.configService.getEffectiveConfiguration('tdt_fine_schedule'),
    }).subscribe({
      next: ({ bands, fineSchedule }) => {
        if (bands?.config_value && typeof bands.config_value === 'object') {
          const value = bands.config_value as { mdg_edition?: string; bands?: RawBand[] };
          if (Array.isArray(value.bands) && value.bands.length > 0) {
            this.bands.clear();
            for (const b of value.bands) this.bands.push(this.newBandGroup(b.stars, b.max_days));
            this.hadExistingBands.set(true);
          }
          if (value.mdg_edition) this.form.controls.mdgEdition.setValue(value.mdg_edition);
        }
        if (fineSchedule?.config_value && typeof fineSchedule.config_value === 'object') {
          const value = fineSchedule.config_value as { mdg_edition?: string; rules?: RawFineRule[] };
          if (Array.isArray(value.rules)) {
            for (const r of value.rules) {
              this.fineRules.push(
                this.newFineRuleGroup(r.consecutive_low_quarters, Number(r.fine_percent)),
              );
            }
            this.hadExistingFineSchedule.set(true);
          }
        }
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  private newBandGroup(stars: number, maxDays: number | null): BandGroup {
    return this.fb.group({
      stars: this.fb.control<number>(stars, [Validators.required, Validators.min(1), Validators.max(5)]),
      maxDays: this.fb.control<number | null>(maxDays),
    });
  }

  private newFineRuleGroup(consecutiveLowQuarters: number, finePercent: number): FineRuleGroup {
    return this.fb.group({
      consecutiveLowQuarters: this.fb.control<number>(consecutiveLowQuarters, [
        Validators.required,
        Validators.min(1),
      ]),
      finePercent: this.fb.control<number>(finePercent, [
        Validators.required,
        Validators.min(0),
        Validators.max(100),
      ]),
    });
  }

  protected addBand(): void {
    // Inserted just before the last (catch-all) row.
    this.bands.insert(this.bands.length - 1, this.newBandGroup(3, null));
  }

  /** Refuses to drop below one row, and refuses to remove the last
   * (catch-all) row — `_validate_bands` requires it, so the invariant is
   * enforced here too, not only via the "Remove" button's `[disabled]`
   * binding in the template. */
  protected removeBand(index: number): void {
    if (this.bands.length <= 1) return;
    if (index === this.bands.length - 1) return;
    this.bands.removeAt(index);
  }

  protected addFineRule(): void {
    this.fineRules.push(this.newFineRuleGroup(1, 0));
  }

  protected removeFineRule(index: number): void {
    this.fineRules.removeAt(index);
  }

  protected submit(): void {
    if (this.saving()) return;
    if (this.form.invalid || this.bandOrderError()) {
      this.form.markAllAsTouched();
      return;
    }

    const raw = this.form.getRawValue();
    const bandsPayload = {
      mdg_edition: raw.mdgEdition,
      bands: raw.bands.map((b) => ({ stars: b.stars, max_days: b.maxDays })),
    };
    const fineSchedulePayload = {
      mdg_edition: raw.mdgEdition,
      rules: raw.fineRules.map((r) => ({
        consecutive_low_quarters: r.consecutiveLowQuarters,
        fine_percent: r.finePercent.toFixed(2),
      })),
    };

    this.saving.set(true);
    forkJoin({
      bands: this.configService.setConfiguration('tdt_star_rating_bands', bandsPayload),
      fineSchedule: this.configService.setConfiguration('tdt_fine_schedule', fineSchedulePayload),
    }).subscribe({
      next: () => {
        this.saving.set(false);
        this.hadExistingBands.set(true);
        this.hadExistingFineSchedule.set(true);
        this.notify.success('TDT rating configuration saved.');
      },
      error: () => this.saving.set(false),
    });
  }
}
