import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { DOCUMENT } from '@angular/common';
import { FormControl, ReactiveFormsModule, Validators } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { SelectModule } from 'primeng/select';
import { DatePickerModule } from 'primeng/datepicker';
import { ToggleSwitchModule } from 'primeng/toggleswitch';
import { CheckboxModule } from 'primeng/checkbox';
import {
  ActivityListComponent,
  DataGridComponent,
  type DataGridColumn,
  EmptyStateComponent,
  FormFieldComponent,
  LiveIndicatorComponent,
  PageHeaderComponent,
  SectionCardComponent,
  SkeletonComponent,
  StatCardComponent,
} from '@lpg/shared/ui';
import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';

interface Swatch {
  readonly name: string;
  readonly token: string;
}

const SEMANTIC: Swatch[] = [
  { name: 'Action primary', token: '--color-action-primary' },
  { name: 'Action primary hover', token: '--color-action-primary-hover' },
  { name: 'Accent 500', token: '--primitive-color-accent-500' },
  { name: 'Success', token: '--color-status-success' },
  { name: 'Warning', token: '--color-status-warning' },
  { name: 'Danger', token: '--color-status-danger' },
  { name: 'Info', token: '--color-status-info' },
];

const SURFACES: Swatch[] = [
  { name: 'Surface base', token: '--color-surface-base' },
  { name: 'Surface raised', token: '--color-surface-raised' },
  { name: 'Surface overlay', token: '--color-surface-overlay' },
  { name: 'Border default', token: '--color-border-default' },
  { name: 'Border strong', token: '--color-border-strong' },
  { name: 'Text primary', token: '--color-text-primary' },
  { name: 'Text secondary', token: '--color-text-secondary' },
];

const NEUTRALS: Swatch[] = [
  0, 50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950,
].map((n) => ({ name: `neutral ${n}`, token: `--primitive-color-neutral-${n}` }));

const TYPE_SCALE = [
  { name: 'Display', size: '--typography-display-font-size', weight: '--typography-display-font-weight' },
  { name: 'Page title (H1)', size: '--typography-heading1-font-size', weight: '--typography-heading1-font-weight' },
  { name: 'Section (H2)', size: '--typography-heading2-font-size', weight: '--typography-heading2-font-weight' },
  { name: 'Card title', size: '--typography-card-title-font-size', weight: '--typography-card-title-font-weight' },
  { name: 'Body', size: '--typography-body-small-font-size', weight: '--typography-body-small-font-weight' },
  { name: 'Secondary', size: '--typography-secondary-font-size', weight: '--typography-secondary-font-weight' },
  { name: 'Caption', size: '--typography-caption-font-size', weight: '--typography-caption-font-weight' },
  { name: 'Data', size: '--typography-data-font-size', weight: '--typography-data-font-weight' },
  { name: 'Large KPI', size: '--typography-kpi-font-size', weight: '--typography-kpi-font-weight' },
];

const RADII = [
  '--radius-xs',
  '--radius-input',
  '--radius-md',
  '--radius-card',
  '--radius-lg',
  '--radius-dialog',
  '--radius-surface',
  '--radius-full',
];

const MOTION = [
  { name: 'micro', token: '--motion-duration-micro' },
  { name: 'small / fast', token: '--motion-duration-small' },
  { name: 'medium / normal', token: '--motion-duration-medium' },
  { name: 'large / complex', token: '--motion-duration-large' },
  { name: 'easing standard', token: '--motion-easing-standard' },
  { name: 'easing emphasized', token: '--motion-easing-emphasized' },
  { name: 'easing accelerate', token: '--motion-easing-accelerate' },
];

const PRINCIPLES = [
  { icon: 'pi pi-eye', title: 'Clarity first', body: 'Obvious hierarchy, prioritised information, calm for long sessions.' },
  { icon: 'pi pi-th-large', title: 'Consistency', body: 'One token system, one component vocabulary across every module.' },
  { icon: 'pi pi-bolt', title: 'Feedback', body: 'Every interaction has a state; motion communicates, never decorates.' },
  { icon: 'pi pi-check-circle', title: 'Accessibility', body: 'WCAG 2.2 AA, keyboard-operable, status never by colour alone.' },
  { icon: 'pi pi-gauge', title: 'Performance', body: 'Glass used selectively; transform/opacity animations only.' },
  { icon: 'pi pi-sparkles', title: 'Modern aesthetic', body: 'Fluent-inspired Mica/Acrylic materials, restrained and premium.' },
];

@Component({
  selector: 'lpg-design-system-page',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    HeaderTitlePortalDirective,
    PageHeaderComponent,
    SectionCardComponent,
    StatCardComponent,
    SkeletonComponent,
    EmptyStateComponent,
    ActivityListComponent,
    LiveIndicatorComponent,
    FormFieldComponent,
    DataGridComponent,
    ButtonModule,
    InputTextModule,
    SelectModule,
    DatePickerModule,
    ToggleSwitchModule,
    CheckboxModule,
  ],
  templateUrl: './design-system.page.html',
  styleUrl: './design-system.page.css',
})
export class DesignSystemPage {
  private readonly document = inject(DOCUMENT);

  protected readonly semantic = SEMANTIC;
  protected readonly surfaces = SURFACES;
  protected readonly neutrals = NEUTRALS;
  protected readonly typeScale = TYPE_SCALE;
  protected readonly radii = RADII;
  protected readonly motion = MOTION;
  protected readonly principles = PRINCIPLES;
  protected readonly elevations = [0, 1, 2, 3, 4];

  /** Bump to force the computed reads below to re-resolve after a theme flip. */
  protected readonly themeTick = signal(0);

  protected readonly resolve = computed(() => {
    this.themeTick();
    const cs = getComputedStyle(this.document.documentElement);
    return (token: string) => cs.getPropertyValue(token).trim();
  });

  protected readonly loadingDemo = signal(true);

  protected readonly nameCtrl = new FormControl('', { validators: [Validators.required] });
  protected readonly emailCtrl = new FormControl('not-an-email', { validators: [Validators.email] });
  protected readonly roleCtrl = new FormControl<string | null>(null);
  protected readonly dateCtrl = new FormControl<Date | null>(null);
  protected readonly toggleCtrl = new FormControl(true);
  protected readonly checkCtrl = new FormControl(true);
  protected readonly roleOptions = [
    { label: 'Dispatcher', value: 'dispatcher' },
    { label: 'Manager', value: 'manager' },
  ];

  protected readonly gridColumns: DataGridColumn<{ id: string; name: string; qty: number }>[] = [
    { field: 'id', header: 'ID', width: 120 },
    { field: 'name', header: 'Cylinder type', flex: 1 },
    { field: 'qty', header: 'On hand', numeric: true, width: 120 },
  ];
  protected readonly gridRows = [
    { id: 'CYL-001', name: '14.2 kg domestic', qty: 428 },
    { id: 'CYL-002', name: '19 kg commercial', qty: 176 },
    { id: 'CYL-003', name: '5 kg portable', qty: 63 },
  ];

  protected readonly activityItems = [
    { time: '2m ago', icon: 'pi pi-check-circle', title: 'Order #ORD-1248', description: 'Delivered', status: 'Delivered', statusTone: 'success' as const },
    { time: '15m ago', icon: 'pi pi-wallet', title: 'Payment received', description: '₹45,000' },
    { time: '1h ago', icon: 'pi pi-exclamation-triangle', title: 'Low stock', description: 'Indane 14.2 kg', status: 'Warning', statusTone: 'warning' as const },
  ];

  protected readonly trend = [8, 10, 9, 12, 11, 15, 14, 18];

  constructor() {
    // The token reads are one-shot on init; nudge them if the theme changes.
    const mo = new MutationObserver(() => this.themeTick.update((n) => n + 1));
    mo.observe(this.document.documentElement, { attributes: true, attributeFilter: ['data-theme', 'style'] });
    setTimeout(() => this.loadingDemo.set(false), 2400);
  }
}
