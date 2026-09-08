import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  ComplianceDocumentsPanel,
  type AddComplianceDocumentCmd,
  type ComplianceDocumentItem,
  type ReplaceComplianceDocumentCmd,
  type VerifyComplianceDocumentCmd,
} from '@lpg/shared/ui';
import { Message } from 'primeng/message';
import { Select } from 'primeng/select';
import { MessageService } from 'primeng/api';
import { AdminWarehouseService, DocumentService, type WarehouseResponse } from '@lpg/shared/data-access';
import { type Observable, map } from 'rxjs';

/**
 * Compliance Calendar (Phase 20, ADR-044) — a Tier-0 licence registry for
 * PESO Form F (per warehouse) and the tenant's own insurance policy. Reuses
 * `<lpg-compliance-documents-panel>` wholesale, exactly the way the driver/
 * vehicle detail drawers do — this page is just two single-owner-context
 * hosts side by side. Biennial safety inspection and the accident-
 * notification workflow are explicitly out of scope (see the ADR).
 */
@Component({
  selector: 'lpg-feature-compliance-calendar',
  standalone: true,
  imports: [HeaderTitlePortalDirective, FormsModule, Message, Select, ComplianceDocumentsPanel],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './feature-compliance-calendar.html',
  styleUrl: './feature-compliance-calendar.css',
})
export class FeatureComplianceCalendar implements OnInit {
  private readonly warehouseService = inject(AdminWarehouseService);
  private readonly documentService = inject(DocumentService);
  private readonly messageService = inject(MessageService);

  protected readonly warehouseDocTypeOptions = [
    { label: 'PESO Form F (explosive-storage licence)', value: 'peso_form_f' },
  ];
  protected readonly tenantDocTypeOptions = [
    { label: 'Insurance Policy', value: 'insurance_policy' },
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
      error: () => this.errorMessage.set('Failed to load warehouses.'),
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
    this.messageService.add({
      severity: 'success',
      summary: 'Success',
      detail: 'Compliance documents updated.',
    });
  }

  protected onTenantDocumentsChanged(): void {
    this.loadTenantDocuments();
    this.messageService.add({
      severity: 'success',
      summary: 'Success',
      detail: 'Compliance documents updated.',
    });
  }
}
