import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  ComplianceDocumentsPanel,
  DataGridComponent,
  StatusChipCell,
  type ChipSeverity,
  type DataGridColumn,
  type AddComplianceDocumentCmd,
  type ComplianceDocumentItem,
  type ReplaceComplianceDocumentCmd,
  type VerifyComplianceDocumentCmd,
  PageHeaderComponent,
} from '@lpg/shared/ui';
import { Message } from 'primeng/message';
import { Select } from 'primeng/select';
import { MessageService } from 'primeng/api';
import {
  AdminWarehouseService,
  DeliveryService,
  DocumentService,
  type ComplianceDocumentResponse,
  type WarehouseResponse,
} from '@lpg/shared/data-access';
import { type Observable, catchError, forkJoin, map, of } from 'rxjs';

/** How soon a document falls due, for the upcoming-expiry list. */
type ExpiryUrgency = 'overdue' | 'due_soon' | 'upcoming';

/** One row of the upcoming-expiry list: a document plus who it belongs to. */
interface UpcomingExpiryRow {
  readonly id: string;
  readonly expiry_date: string;
  readonly urgency: ExpiryUrgency;
  readonly days: number;
  readonly document: string;
  readonly document_number: string;
  readonly owner: string;
}

/** Days before expiry at which a document counts as "due soon". */
const DUE_SOON_DAYS = 30;
/** Most drivers/vehicles looked up to name document owners. */
const OWNER_LOOKUP_LIMIT = 500;

const DOC_TYPE_LABELS: Record<string, string> = {
  driving_licence: 'Driving licence',
  dl_hazmat_endorsement: 'Hazardous-goods endorsement',
  trem_card: 'TREM card',
  driver_training_certificate: 'Driver training certificate',
  vehicle_rc: 'Registration certificate (RC)',
  vehicle_insurance: 'Vehicle insurance',
  vehicle_fitness: 'Fitness certificate',
  vehicle_puc: 'Pollution certificate (PUC)',
  peso_transport_licence: 'PESO transport licence',
  peso_form_f: 'PESO Form F',
  insurance_policy: 'Agency insurance',
};

const OWNER_TYPE_LABELS: Record<string, string> = {
  driver: 'Driver',
  vehicle: 'Vehicle',
  warehouse: 'Godown',
  tenant: 'Agency',
};

/** Whole days from today (local) to an ISO `yyyy-mm-dd` date. */
export function daysUntil(isoDate: string, today: Date = new Date()): number {
  const [y, m, d] = isoDate.split('-').map(Number);
  const due = Date.UTC(y, m - 1, d);
  const now = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate());
  return Math.round((due - now) / 86_400_000);
}

export function expiryUrgency(isoDate: string, today: Date = new Date()): ExpiryUrgency {
  const days = daysUntil(isoDate, today);
  if (days < 0) return 'overdue';
  return days <= DUE_SOON_DAYS ? 'due_soon' : 'upcoming';
}

/**
 * Compliance Calendar (Phase 20, ADR-044). Leads with one upcoming-expiry
 * list — every overdue or soon-due document across warehouses, the agency's
 * insurance, driver licences and vehicle papers, earliest first (DO-33) —
 * then the two registries this page owns: PESO Form F per warehouse and the
 * agency insurance policy, each hosted in `<lpg-compliance-documents-panel>`
 * the same way the driver/vehicle drawers host theirs. Biennial safety
 * inspection and the accident-notification workflow are out of scope (ADR).
 */
@Component({
  selector: 'lpg-feature-compliance-calendar',
  standalone: true,
  imports: [
    HeaderTitlePortalDirective,
    PageHeaderComponent,
    FormsModule,
    Message,
    Select,
    ComplianceDocumentsPanel,
    DataGridComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './feature-compliance-calendar.html',
  styleUrl: './feature-compliance-calendar.css',
})
export class FeatureComplianceCalendar implements OnInit {
  private readonly warehouseService = inject(AdminWarehouseService);
  private readonly documentService = inject(DocumentService);
  private readonly deliveryService = inject(DeliveryService);
  private readonly messageService = inject(MessageService);

  protected readonly warehouseDocTypeOptions = [
    { label: 'PESO Form F (explosive-storage licence)', value: 'peso_form_f' },
  ];
  protected readonly tenantDocTypeOptions = [
    { label: 'Agency insurance policy', value: 'insurance_policy' },
  ];

  private static readonly URGENCY_SEVERITY: Record<ExpiryUrgency, ChipSeverity> = {
    overdue: 'danger',
    due_soon: 'warn',
    upcoming: 'info',
  };

  protected readonly upcomingDocuments = signal<ComplianceDocumentResponse[]>([]);
  protected readonly upcomingLoading = signal(false);
  private readonly driverNames = signal<ReadonlyMap<string, string>>(new Map());
  private readonly vehicleNumbers = signal<ReadonlyMap<string, string>>(new Map());

  protected readonly upcomingRows = computed<UpcomingExpiryRow[]>(() => {
    const warehouseNames = new Map(this.warehouses().map((w) => [w.id, w.name]));
    const drivers = this.driverNames();
    const vehicles = this.vehicleNumbers();
    const ownerName = (doc: ComplianceDocumentResponse): string => {
      const kind = OWNER_TYPE_LABELS[doc.owner_type] ?? doc.owner_type;
      if (doc.owner_type === 'tenant') return kind;
      const name =
        doc.owner_type === 'warehouse'
          ? warehouseNames.get(doc.owner_id)
          : doc.owner_type === 'driver'
            ? drivers.get(doc.owner_id)
            : vehicles.get(doc.owner_id);
      return name ? `${kind} · ${name}` : kind;
    };
    return this.upcomingDocuments()
      .filter((doc): doc is ComplianceDocumentResponse & { expiry_date: string } =>
        Boolean(doc.expiry_date),
      )
      .map((doc) => ({
        id: doc.id,
        expiry_date: doc.expiry_date,
        urgency: expiryUrgency(doc.expiry_date),
        days: daysUntil(doc.expiry_date),
        document: DOC_TYPE_LABELS[doc.doc_type] ?? doc.doc_type,
        document_number: doc.document_number,
        owner: ownerName(doc),
      }));
  });

  protected readonly overdueCount = computed(
    () => this.upcomingRows().filter((r) => r.urgency === 'overdue').length,
  );

  protected readonly upcomingColumns: DataGridColumn<UpcomingExpiryRow>[] = [
    { field: 'expiry_date', header: 'Due', sortable: true, width: 130 },
    {
      field: 'urgency',
      header: 'Status',
      width: 130,
      cellRenderer: StatusChipCell,
      cellRendererParams: {
        severityMap: FeatureComplianceCalendar.URGENCY_SEVERITY,
        labelMap: { overdue: 'Overdue', due_soon: 'Due soon', upcoming: 'Upcoming' },
      },
    },
    {
      field: 'days',
      header: 'Days left',
      numeric: true,
      width: 130,
      valueFormatter: (value) => {
        const days = value as number;
        return days < 0 ? `${-days} overdue` : String(days);
      },
    },
    { field: 'document', header: 'Document', sortable: true, filterable: true, flex: 1 },
    { field: 'owner', header: 'Belongs to', sortable: true, filterable: true, flex: 1 },
    { field: 'document_number', header: 'Number', flex: 1 },
  ];

  protected readonly warehouses = signal<WarehouseResponse[]>([]);
  protected readonly selectedWarehouseId = signal<string | null>(null);
  protected readonly warehouseDocuments = signal<ComplianceDocumentItem[]>([]);
  protected readonly warehouseDocumentsLoading = signal(false);

  protected readonly tenantDocuments = signal<ComplianceDocumentItem[]>([]);
  protected readonly tenantDocumentsLoading = signal(false);

  protected readonly errorMessage = signal<string | null>(null);

  /** Scan upload is owner-agnostic — same endpoint the driver/vehicle
   * panels use. */
  protected readonly uploader = (file: File): Observable<{ blobRef: string }> =>
    this.documentService.uploadAttachment(file).pipe(map((r) => ({ blobRef: r.blob_ref })));

  ngOnInit(): void {
    this.loadWarehouses();
    this.loadTenantDocuments();
    this.loadUpcoming();
    this.loadOwnerNames();
  }

  /** Overdue and due-within-90-days documents across every owner, earliest
   * first — the backend sorts; the grid keeps that order. */
  protected loadUpcoming(): void {
    this.upcomingLoading.set(true);
    this.documentService.listComplianceDocuments({ expiry: 'upcoming', limit: 200 }).subscribe({
      next: (res) => {
        this.upcomingDocuments.set(res.items);
        this.upcomingLoading.set(false);
      },
      error: () => {
        this.upcomingDocuments.set([]);
        this.upcomingLoading.set(false);
      },
    });
  }

  /** Names for driver/vehicle owners. A failed lookup only costs the name —
   * the row still shows "Driver" / "Vehicle". */
  private loadOwnerNames(): void {
    forkJoin({
      drivers: this.deliveryService
        .listDrivers(0, OWNER_LOOKUP_LIMIT)
        .pipe(catchError(() => of({ items: [] }))),
      vehicles: this.deliveryService
        .listVehicles(0, OWNER_LOOKUP_LIMIT)
        .pipe(catchError(() => of({ items: [] }))),
    }).subscribe(({ drivers, vehicles }) => {
      this.driverNames.set(new Map(drivers.items.map((d) => [d.id, d.name ?? d.license_number])));
      this.vehicleNumbers.set(new Map(vehicles.items.map((v) => [v.id, v.registration_number])));
    });
  }

  protected loadWarehouses(): void {
    this.warehouseService.listWarehouses().subscribe({
      next: (warehouses) => {
        this.warehouses.set(warehouses);
        if (warehouses.length > 0 && !this.selectedWarehouseId()) {
          this.selectedWarehouseId.set(warehouses[0].id);
          this.loadWarehouseDocuments(warehouses[0].id);
        }
      },
      error: () => this.errorMessage.set('Failed to load godowns.'),
    });
  }

  protected onWarehouseChange(warehouseId: string): void {
    this.selectedWarehouseId.set(warehouseId);
    this.loadWarehouseDocuments(warehouseId);
  }

  protected loadWarehouseDocuments(warehouseId: string): void {
    this.warehouseDocumentsLoading.set(true);
    this.documentService.listWarehouseDocuments(warehouseId).subscribe({
      next: (res) => {
        this.warehouseDocuments.set(res.items);
        this.warehouseDocumentsLoading.set(false);
      },
      error: () => {
        this.warehouseDocuments.set([]);
        this.warehouseDocumentsLoading.set(false);
      },
    });
  }

  protected loadTenantDocuments(): void {
    this.tenantDocumentsLoading.set(true);
    this.documentService.listTenantDocuments().subscribe({
      next: (res) => {
        this.tenantDocuments.set(res.items);
        this.tenantDocumentsLoading.set(false);
      },
      error: () => {
        this.tenantDocuments.set([]);
        this.tenantDocumentsLoading.set(false);
      },
    });
  }

  /** Bound per-warehouse in the template — `<lpg-compliance-documents-panel>`
   * calls this with the new document's fields once its inline form submits. */
  protected addWarehouseDocument(warehouseId: string) {
    return (cmd: AddComplianceDocumentCmd) =>
      this.documentService.addWarehouseDocument(warehouseId, cmd);
  }

  protected readonly addTenantDocument = (cmd: AddComplianceDocumentCmd) =>
    this.documentService.addTenantDocument(cmd);

  /** Replace/verify are owner-agnostic on the backend — shared by both
   * panels, same as the driver/vehicle pages. */
  protected readonly replaceComplianceDocument = (
    documentId: string,
    cmd: ReplaceComplianceDocumentCmd,
  ) => this.documentService.replace(documentId, cmd);

  protected readonly verifyComplianceDocument = (
    documentId: string,
    cmd: VerifyComplianceDocumentCmd,
  ) => this.documentService.verify(documentId, cmd);

  protected onWarehouseDocumentsChanged(): void {
    const warehouseId = this.selectedWarehouseId();
    if (warehouseId) this.loadWarehouseDocuments(warehouseId);
    this.loadUpcoming();
    this.messageService.add({
      severity: 'success',
      summary: 'Success',
      detail: 'Compliance documents updated.',
    });
  }

  protected onTenantDocumentsChanged(): void {
    this.loadTenantDocuments();
    this.loadUpcoming();
    this.messageService.add({
      severity: 'success',
      summary: 'Success',
      detail: 'Compliance documents updated.',
    });
  }
}
