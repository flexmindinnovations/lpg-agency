import { ChangeDetectionStrategy, Component, inject, input, output, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import type { Observable } from 'rxjs';
import { ButtonDirective, ButtonIcon, ButtonLabel } from 'primeng/button';
import { DatePicker } from 'primeng/datepicker';
import { InputText } from 'primeng/inputtext';
import { Message } from 'primeng/message';
import { Select } from 'primeng/select';
import { Tag } from 'primeng/tag';
import { DocumentUploadComponent, type DocumentUploaded } from '../document-upload/document-upload.component';
import { FormFieldComponent } from '../form-field/form-field.component';
import { HasPermissionDirective } from '../directives/has-permission.directive';
import { formatReportDate } from '../format/format';
import { type ChipSeverity, toSentenceCase } from '../status-chip-cell/status-chip-cell';

/** Structurally compatible with the generated `ComplianceDocumentResponse` —
 * declared locally rather than imported so this `type:ui` component stays
 * data-access-agnostic (module boundary), same rationale as
 * `DocumentUploadComponent`'s own local result types. */
export interface ComplianceDocumentItem {
  id: string;
  doc_type: string;
  document_number: string;
  issue_date: string | null;
  expiry_date: string | null;
  verification_status: string;
  rejection_reason: string | null;
  file_url: string | null;
}

export interface ComplianceDocTypeOption {
  label: string;
  value: string;
}

export interface AddComplianceDocumentCmd {
  doc_type: string;
  document_number: string;
  file_ref: string;
  issue_date?: string | null;
  expiry_date?: string | null;
}

export interface ReplaceComplianceDocumentCmd {
  document_number: string;
  file_ref: string;
  issue_date?: string | null;
  expiry_date?: string | null;
}

export interface VerifyComplianceDocumentCmd {
  status: 'verified' | 'rejected';
  rejection_reason?: string | null;
}

function formatDateForApi(value: unknown): string | undefined {
  if (!value) return undefined;
  const d = new Date(value as string | number | Date);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(
    d.getDate(),
  ).padStart(2, '0')}`;
}

function errorMessageFor(error: unknown): string {
  if (typeof error === 'object' && error !== null && 'errorCode' in error) {
    const code = (error as { errorCode?: string }).errorCode;
    if (code === 'PERMISSION_DENIED') return "You don't have permission to do that.";
  }
  return 'Something went wrong. Please try again.';
}

const VERIFICATION_SEVERITY: Record<string, ChipSeverity> = {
  verified: 'success',
  pending: 'warn',
  rejected: 'danger',
};

/**
 * The driver/vehicle "statutory documents" table — used identically inside
 * both `feature-drivers` and `feature-vehicles`' detail drawers. Deliberately
 * endpoint-agnostic like `<lpg-document-upload>`: the call site passes
 * `uploader`/`addDocument`/`replaceDocument`/`verifyDocument` functions
 * bound to the right owner id, and this component owns the table, the
 * add/replace inline form, and the verify/reject flow — emitting `changed`
 * once a mutation succeeds so the parent reloads its list and shows a toast.
 */
@Component({
  selector: 'lpg-compliance-documents-panel',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    ButtonDirective,
    ButtonIcon,
    ButtonLabel,
    DatePicker,
    InputText,
    Message,
    Select,
    Tag,
    DocumentUploadComponent,
    FormFieldComponent,
    HasPermissionDirective,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './compliance-documents-panel.html',
  styleUrl: './compliance-documents-panel.css',
})
export class ComplianceDocumentsPanel {
  private readonly fb = inject(NonNullableFormBuilder);

  readonly documents = input<ComplianceDocumentItem[]>([]);
  readonly loading = input(false);
  readonly docTypeOptions = input.required<ComplianceDocTypeOption[]>();
  /** Gates the "Add document" / "Replace" controls — `drivers:manage` or
   * `vehicles:manage` depending on the owner. Verify/Reject are always
   * gated by `compliance:verify` regardless of owner. */
  readonly managePermission = input('drivers:manage');

  readonly uploader = input.required<(file: File) => Observable<{ blobRef: string }>>();
  readonly addDocument = input.required<(cmd: AddComplianceDocumentCmd) => Observable<unknown>>();
  readonly replaceDocument =
    input.required<(documentId: string, cmd: ReplaceComplianceDocumentCmd) => Observable<unknown>>();
  readonly verifyDocument =
    input.required<(documentId: string, cmd: VerifyComplianceDocumentCmd) => Observable<unknown>>();

  /** Emitted once an add/replace/verify/reject call succeeds — the parent
   * reloads its document list (and may show a success toast). */
  readonly changed = output<void>();

  protected readonly formatDate = formatReportDate;
  protected readonly toSentenceCase = toSentenceCase;

  protected readonly mode = signal<'list' | 'form'>('list');
  protected readonly formPurpose = signal<'add' | 'replace'>('add');
  protected readonly replacingDoc = signal<ComplianceDocumentItem | null>(null);
  protected readonly submitting = signal(false);
  protected readonly formError = signal<string | null>(null);

  protected readonly rejectingDoc = signal<ComplianceDocumentItem | null>(null);
  protected readonly rejectReason = signal('');
  protected readonly rejectError = signal<string | null>(null);
  protected readonly verifyingId = signal<string | null>(null);

  protected readonly docForm = this.fb.group({
    doc_type: ['', [Validators.required]],
    document_number: ['', [Validators.required]],
    file_ref: ['', [Validators.required]],
    issue_date: this.fb.control<Date | null>(null),
    expiry_date: this.fb.control<Date | null>(null),
  });

  protected readonly fieldMessages = {
    doc_type: { required: 'Select a document type.' },
    document_number: { required: 'Document number is required.' },
    file_ref: { required: 'Upload a scan of the document.' },
  };

  protected docTypeLabel(docType: string): string {
    return this.docTypeOptions().find((o) => o.value === docType)?.label ?? toSentenceCase(docType);
  }

  protected verificationSeverity(status: string): ChipSeverity {
    return VERIFICATION_SEVERITY[status] ?? 'secondary';
  }

  /** `null` once expiry is more than 30 days out — the date alone is enough. */
  protected expiryBadge(doc: ComplianceDocumentItem): { label: string; severity: ChipSeverity } | null {
    if (!doc.expiry_date) return null;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const expiry = new Date(doc.expiry_date);
    const diffDays = Math.round((expiry.getTime() - today.getTime()) / 86_400_000);
    if (diffDays < 0) return { label: 'Expired', severity: 'danger' };
    if (diffDays <= 30) return { label: `Expires in ${diffDays}d`, severity: 'warn' };
    return null;
  }

  protected openAddForm(): void {
    this.docForm.reset({
      doc_type: '',
      document_number: '',
      file_ref: '',
      issue_date: null,
      expiry_date: null,
    });
    this.docForm.controls.doc_type.enable();
    this.formPurpose.set('add');
    this.replacingDoc.set(null);
    this.formError.set(null);
    this.mode.set('form');
  }

  protected openReplaceForm(doc: ComplianceDocumentItem): void {
    this.docForm.reset({
      doc_type: doc.doc_type,
      document_number: doc.document_number,
      file_ref: '',
      issue_date: doc.issue_date ? new Date(doc.issue_date) : null,
      expiry_date: doc.expiry_date ? new Date(doc.expiry_date) : null,
    });
    this.docForm.controls.doc_type.disable();
    this.formPurpose.set('replace');
    this.replacingDoc.set(doc);
    this.formError.set(null);
    this.mode.set('form');
  }

  protected cancelForm(): void {
    this.mode.set('list');
    this.formError.set(null);
  }

  protected onFileUploaded(event: DocumentUploaded): void {
    this.docForm.controls.file_ref.setValue(event.blobRef);
    this.docForm.controls.file_ref.markAsTouched();
  }

  protected onFileCleared(): void {
    this.docForm.controls.file_ref.setValue('');
  }

  protected submitForm(): void {
    if (this.docForm.invalid) {
      this.docForm.markAllAsTouched();
      return;
    }
    const val = this.docForm.getRawValue();
    const payload: ReplaceComplianceDocumentCmd = {
      document_number: val.document_number,
      file_ref: val.file_ref,
      issue_date: formatDateForApi(val.issue_date) ?? null,
      expiry_date: formatDateForApi(val.expiry_date) ?? null,
    };

    let request$: Observable<unknown>;
    if (this.formPurpose() === 'add') {
      request$ = this.addDocument()({ doc_type: val.doc_type, ...payload });
    } else {
      const replacing = this.replacingDoc();
      if (!replacing) return;
      request$ = this.replaceDocument()(replacing.id, payload);
    }

    this.submitting.set(true);
    this.formError.set(null);

    request$.subscribe({
      next: () => {
        this.submitting.set(false);
        this.mode.set('list');
        this.changed.emit();
      },
      error: (err: unknown) => {
        this.submitting.set(false);
        this.formError.set(errorMessageFor(err));
      },
    });
  }

  protected verifyNow(doc: ComplianceDocumentItem): void {
    this.verifyingId.set(doc.id);
    this.verifyDocument()(doc.id, { status: 'verified' }).subscribe({
      next: () => {
        this.verifyingId.set(null);
        this.changed.emit();
      },
      error: () => this.verifyingId.set(null),
    });
  }

  protected openReject(doc: ComplianceDocumentItem): void {
    this.rejectingDoc.set(doc);
    this.rejectReason.set('');
    this.rejectError.set(null);
  }

  protected cancelReject(): void {
    this.rejectingDoc.set(null);
  }

  protected confirmReject(): void {
    const doc = this.rejectingDoc();
    if (!doc) return;
    if (!this.rejectReason().trim()) {
      this.rejectError.set('A reason is required to reject a document.');
      return;
    }
    this.verifyingId.set(doc.id);
    this.verifyDocument()(doc.id, { status: 'rejected', rejection_reason: this.rejectReason() }).subscribe({
      next: () => {
        this.verifyingId.set(null);
        this.rejectingDoc.set(null);
        this.changed.emit();
      },
      error: () => {
        this.verifyingId.set(null);
        this.rejectError.set('Could not reject the document. Please try again.');
      },
    });
  }
}
