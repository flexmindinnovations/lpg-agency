import { HeaderPortalDirective , HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  OnInit,
  computed,
  inject,
  signal,
  viewChild,
  DestroyRef,
} from '@angular/core';
import { FormsModule, NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { Location } from '@angular/common';

import { DomSanitizer, type SafeResourceUrl } from '@angular/platform-browser';
import { KeyboardShortcutsService } from '@lpg/shared/util';
import { ButtonDirective, ButtonIcon, ButtonLabel } from 'primeng/button';
import { Dialog } from 'primeng/dialog';
import { Drawer } from 'primeng/drawer';
import { IconField } from 'primeng/iconfield';
import { InputIcon } from 'primeng/inputicon';
import { InputText } from 'primeng/inputtext';
import { Popover } from 'primeng/popover';
import { Select } from 'primeng/select';
import { Tag } from 'primeng/tag';
import { Badge } from 'primeng/badge';
import { Tabs, TabList, Tab, TabPanels, TabPanel } from 'primeng/tabs';
import { MessageService } from 'primeng/api';
import {
  CustomerService,
  AdminBranchService,
  type AppError,
  type BranchResponse,
  type CustomerResponse,
  type KycDocumentResponse,
} from '@lpg/shared/data-access';
import {
  DataGridComponent,
  type DataGridColumn,
  HasPermissionDirective,
  PageHeaderComponent,
  StatusChipCell,
} from '@lpg/shared/ui';

const MAX_KYC_UPLOAD_BYTES = 10 * 1024 * 1024;

function isAppError(value: unknown): value is AppError {
  return typeof value === 'object' && value !== null && 'errorCode' in value;
}

function errorMessageFor(error: unknown): string {
  switch (isAppError(error) ? error.errorCode : null) {
    case 'DUPLICATE_PHONE':
      return 'A customer with this phone number already exists.';
    case 'DUPLICATE_CONSUMER_NUMBER':
      return 'This Consumer Number is already assigned.';
    case 'DUPLICATE_LPG_SUBSIDY_ID':
      return 'This LPG ID is already linked to another customer.';
    case 'PERMISSION_DENIED':
      return "You don't have permission to do that.";
    default:
      return 'Something went wrong. Please try again.';
  }
}

import { RouterLink } from '@angular/router';
import { TitleCasePipe } from '@angular/common';

@Component({
  selector: 'lpg-feature-customers',
  standalone: true,
  imports: [PageHeaderComponent, HeaderTitlePortalDirective, HeaderPortalDirective,
    ReactiveFormsModule,
    FormsModule,
    ButtonDirective,
    ButtonIcon,
    ButtonLabel,
    InputText,
    Drawer,
    Dialog,
    IconField,
    InputIcon,
    Popover,
    Select,
    Tag,
    Badge,
    Tabs,
    TabList,
    Tab,
    TabPanels,
    TabPanel,
    DataGridComponent,
    RouterLink,
    TitleCasePipe,
    HasPermissionDirective,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './feature-customers.html',
  styleUrl: './feature-customers.css',
})
export class FeatureCustomers implements OnInit {
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly customerService = inject(CustomerService);
  private readonly branchService = inject(AdminBranchService);
  private readonly messageService = inject(MessageService);
  private readonly keyboardShortcuts = inject(KeyboardShortcutsService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly sanitizer = inject(DomSanitizer);
  private readonly route = inject(ActivatedRoute);
  private readonly location = inject(Location);

  protected readonly customers = signal<CustomerResponse[]>([]);
  protected readonly branches = signal<BranchResponse[]>([]);
  protected readonly selectedCustomer = signal<CustomerResponse | null>(null);
  protected readonly kycDocuments = signal<KycDocumentResponse[]>([]);
  protected readonly loading = signal(false);
  protected readonly searchQuery = signal('');

  // Document preview — an in-app modal rather than `target="_blank"`, so
  // there is always a visible close control regardless of what browser
  // chrome is (or isn't) available in the surrounding environment.
  protected readonly viewingDocumentUrl = signal<string | null>(null);
  protected readonly viewingDocumentIsPdf = computed(() =>
    /\.pdf(\?|$)/i.test(this.viewingDocumentUrl() ?? ''),
  );
  protected readonly viewingDocumentSafeUrl = computed<SafeResourceUrl | null>(() => {
    const url = this.viewingDocumentUrl();
    return url ? this.sanitizer.bypassSecurityTrustResourceUrl(url) : null;
  });

  // Client-side filters — the backend's GET /customers only accepts
  // skip/limit/search (no type/status/kyc_status params), and the whole
  // list is already loaded on one page, so filtering it in memory is the
  // real functionality here rather than a bigger backend project.
  protected readonly filterCustomerType = signal<string | null>(null);
  protected readonly filterKycStatus = signal<string | null>(null);
  protected readonly filterAccountStatus = signal<string | null>(null);

  protected readonly activeFilterCount = computed(
    () =>
      [this.filterCustomerType(), this.filterKycStatus(), this.filterAccountStatus()].filter(
        (v) => v !== null,
      ).length,
  );

  protected readonly filteredCustomers = computed(() => {
    const type = this.filterCustomerType();
    const kyc = this.filterKycStatus();
    const status = this.filterAccountStatus();
    return this.customers().filter(
      (c) =>
        (!type || c.customer_type === type) &&
        (!kyc || c.kyc_status === kyc) &&
        (!status || c.status === status),
    );
  });

  // Modals Visibility Signals
  protected readonly showDetailDrawer = signal(false);
  protected readonly showAddAddressModal = signal(false);
  protected readonly showSubmitKycModal = signal(false);
  protected readonly submitKycFile = signal<File | null>(null);
  protected readonly submitKycFilePreviewUrl = signal<string | null>(null);
  protected readonly submitKycFileError = signal<string | null>(null);
  protected readonly submitKycDragging = signal(false);
  protected readonly submitKycUploading = signal(false);

  // PrimeNG's Dialog has no built-in "return focus to trigger" behaviour —
  // matches `apps/dashboard/src/app/home/home.ts`'s documented pattern.
  // matches `apps/dashboard/src/app/home/home.ts`'s documented pattern.
  protected readonly addAddressTrigger =
    viewChild<ElementRef<HTMLButtonElement>>('addAddressTriggerEl');
  protected readonly submitKycTrigger =
    viewChild<ElementRef<HTMLButtonElement>>('submitKycTriggerEl');

  protected readonly customerTypeOptions = [
    { label: 'Domestic', value: 'domestic' },
    { label: 'Commercial', value: 'commercial' },
    { label: 'Industrial', value: 'industrial' },
    { label: 'Government', value: 'government' },
  ];

  protected readonly kycStatusFilterOptions = [
    { label: 'Pending', value: 'pending' },
    { label: 'Verified', value: 'verified' },
    { label: 'Rejected', value: 'rejected' },
    { label: 'Expired', value: 'expired' },
  ];

  protected readonly accountStatusFilterOptions = [
    { label: 'Onboarding', value: 'onboarding' },
    { label: 'Pending approval', value: 'pending_approval' },
    { label: 'Active', value: 'active' },
    { label: 'Inactive', value: 'inactive' },
    { label: 'Blocked', value: 'blocked' },
    { label: 'Closed', value: 'closed' },
  ];

  protected readonly kycDocTypeOptions = [
    { label: 'Aadhaar Card', value: 'aadhaar' },
    { label: 'PAN Card', value: 'pan' },
    { label: 'Voter ID', value: 'voter_id' },
    { label: 'Passport', value: 'passport' },
    { label: 'GSTIN', value: 'gstin' },
    { label: 'Utility Bill (Address Proof)', value: 'utility_bill' },
  ];

  // Column definitions for customer list data grid
  protected readonly columns: DataGridColumn<CustomerResponse>[] = [
    { field: 'consumer_number', header: 'Consumer No.', sortable: true },
    {
      field: 'full_name',
      header: 'Name',
      sortable: true,
      filterable: true,
      onLinkClick: (row) => this.viewCustomer(row),
    },
    { field: 'phone_number', header: 'Phone', sortable: true },
    { field: 'customer_type', header: 'Type', sortable: true, cellRenderer: StatusChipCell },
    { field: 'kyc_status', header: 'KYC Status', sortable: true, cellRenderer: StatusChipCell },
    {
      field: 'status',
      header: 'Account Status',
      sortable: true,
      cellRenderer: StatusChipCell,
      cellRendererParams: {
        severityMap: {
          onboarding: 'warn',
          pending_approval: 'warn',
          active: 'success',
          inactive: 'secondary',
          blocked: 'danger',
          closed: 'danger',
        },
      },
    },
  ];

  // Forms

  protected readonly addressForm = this.fb.group({
    address_line: ['', [Validators.required]],
  });

  protected readonly kycForm = this.fb.group({
    doc_type: ['aadhaar', [Validators.required]],
    doc_reference: ['', [Validators.required]],
  });

  // p-dialog/p-drawer's [(visible)] two-way-binds to a plain property, not a signal
  // directly — thin getter/setter bridges keep the rest of the component
  // signal-first (ADR-019), matching `apps/dashboard/src/app/home/home.ts`.

  protected get addAddressModalVisible(): boolean {
    return this.showAddAddressModal();
  }
  protected set addAddressModalVisible(value: boolean) {
    this.showAddAddressModal.set(value);
  }

  protected get submitKycModalVisible(): boolean {
    return this.showSubmitKycModal();
  }
  protected set submitKycModalVisible(value: boolean) {
    this.showSubmitKycModal.set(value);
  }

  ngOnInit(): void {
    this.reloadList();
    this.loadBranches();
    this.openCustomerFromQueryParam();


    const unregisterNew = this.keyboardShortcuts.register({
      key: 'c',
      alt: true,
      description: 'Register new customer',
      handler: () => {
        // Navigate or do nothing
      }
    });
    
    const unregisterSearch = this.keyboardShortcuts.register({
      key: '/',
      description: 'Focus customer search',
      handler: () => {
        const searchInput = document.getElementById('customer-search-input');
        if (searchInput) {
          searchInput.focus();
        }
      }
    });

    this.destroyRef.onDestroy(() => {
      unregisterNew();
      unregisterSearch();
    });
  }

  private reloadList(): void {
    this.loading.set(true);
    this.customerService.list(0, 100, this.searchQuery() || undefined).subscribe({
      next: (res) => {
        this.customers.set(res.items);
        this.loading.set(false);

        // Keep detail panel updated if a customer was selected
        const selected = this.selectedCustomer();
        if (selected) {
          const updated = res.items.find((c) => c.id === selected.id);
          this.selectedCustomer.set(updated ?? null);
        }
      },
      error: () => {
        this.loading.set(false);
        this.messageService.add({ severity: 'error', summary: 'Error', detail: 'Failed to load customers.' });
      }
    });
  }

  /** Deep-link support for "Customer" links elsewhere in the app (e.g. the
   * invoice detail drawer) — `?id=<uuid>` opens that customer's detail
   * drawer directly, fetched by id rather than relying on it being present
   * in the (paginated/searched) list already loaded on this page. The query
   * param is then stripped via `Location.replaceState` (not `Router.navigate`,
   * which re-enters the router pipeline and was found to reset component
   * state) so a refresh/back-navigation doesn't re-trigger it. */
  private openCustomerFromQueryParam(): void {
    const customerId = this.route.snapshot.queryParamMap.get('id');
    if (!customerId) return;

    this.customerService.get(customerId).subscribe({
      next: (customer) => {
        this.viewCustomer(customer);
        this.location.replaceState(this.location.path().split('?')[0]);
      },
      error: () => {
        this.messageService.add({
          severity: 'error',
          summary: 'Error',
          detail: 'That customer could not be found.',
        });
      },
    });
  }

  private loadBranches(): void {
    this.branchService.listBranches().subscribe({
      next: (branches) => this.branches.set(branches),
      error: () => {
        this.messageService.add({ severity: 'error', summary: 'Error', detail: 'Failed to load branches.' });
      }
    });
  }

  private loadKycDocuments(customerId: string): void {
    this.customerService.listKyc(customerId).subscribe({
      next: (res) => this.kycDocuments.set(res.items),
      // A viewer without `kyc:read` still sees the customer profile — just
      // not the KYC section. Fail quietly rather than blocking the page.
      error: () => this.kycDocuments.set([]),
    });
  }

  protected onSearch(event: Event): void {
    const value = (event.target as HTMLInputElement).value;
    this.searchQuery.set(value);
    this.reloadList();
  }

  protected clearFilters(): void {
    this.filterCustomerType.set(null);
    this.filterKycStatus.set(null);
    this.filterAccountStatus.set(null);
  }

  protected async viewCustomer(customer: CustomerResponse) {
    this.selectedCustomer.set(customer);
    this.loadKycDocuments(customer.id);
    this.showDetailDrawer.set(true);
  }



  // Address Actions
  protected openAddAddressModal(): void {
    this.addressForm.reset();
    this.showAddAddressModal.set(true);
  }

  protected closeAddAddressModal(): void {
    this.showAddAddressModal.set(false);
  }

  protected submitAddAddress(): void {
    const customer = this.selectedCustomer();
    if (!customer || this.addressForm.invalid) return;

    const { address_line } = this.addressForm.getRawValue();
    this.customerService.addAddress(customer.id, { line_1: address_line }).subscribe({
      next: () => {
        this.messageService.add({ severity: 'success', summary: 'Success', detail: 'Address added successfully.' });
        this.closeAddAddressModal();
        this.reloadList();
      },
      error: (error: unknown) => {
        this.messageService.add({ severity: 'error', summary: 'Error', detail: errorMessageFor(error) });
      },
    });
  }

  protected makeAddressPrimary(addressId: string): void {
    const customer = this.selectedCustomer();
    if (!customer) return;

    this.customerService.setPrimaryAddress(customer.id, addressId).subscribe({
      next: () => {
        this.messageService.add({ severity: 'success', summary: 'Success', detail: 'Primary address updated.' });
        this.reloadList();
      },
      error: (error: unknown) => {
        this.messageService.add({ severity: 'error', summary: 'Error', detail: errorMessageFor(error) });
      },
    });
  }

  // KYC Actions
  protected openSubmitKycModal(): void {
    this.kycForm.reset({
      doc_type: 'aadhaar',
    });
    this.clearSubmitKycFile();
    this.showSubmitKycModal.set(true);
  }

  protected closeSubmitKycModal(): void {
    this.showSubmitKycModal.set(false);
    this.clearSubmitKycFile();
  }

  /** True when the selected doc_type already has a document on file —
   * submitting will replace it, not add a duplicate (see `Customer.submit_kyc`
   * on the backend). Surfaced in the dialog so that isn't a surprise. */
  protected isReplacingExistingKycDoc(): boolean {
    const docType = this.kycForm.controls.doc_type.value;
    return this.kycDocuments().some((doc) => doc.doc_type === docType);
  }

  protected selectedKycDocTypeLabel(): string {
    const docType = this.kycForm.controls.doc_type.value;
    return this.kycDocTypeOptions.find((opt) => opt.value === docType)?.label ?? docType;
  }

  // Same drag-and-drop dropzone pattern as the onboarding wizard
  // (customer-onboarding-wizard.component.ts) — visual and behavioral
  // parity, so KYC upload doesn't look like two different features
  // depending on which screen it's done from.
  protected onKycFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = '';
    if (file) this.processSubmitKycFile(file);
  }

  protected onKycDragOver(event: DragEvent): void {
    event.preventDefault();
    this.submitKycDragging.set(true);
  }

  protected onKycDragLeave(event: DragEvent): void {
    event.preventDefault();
    this.submitKycDragging.set(false);
  }

  protected onKycDrop(event: DragEvent): void {
    event.preventDefault();
    this.submitKycDragging.set(false);
    const file = event.dataTransfer?.files?.[0];
    if (file) this.processSubmitKycFile(file);
  }

  protected removeSubmitKycFile(): void {
    this.clearSubmitKycFile();
  }

  protected formatFileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  private processSubmitKycFile(file: File): void {
    if (!file.type.startsWith('image/') && file.type !== 'application/pdf') {
      this.submitKycFileError.set('Unsupported file type. Please upload a JPG, PNG, or PDF.');
      return;
    }
    if (file.size > MAX_KYC_UPLOAD_BYTES) {
      this.submitKycFileError.set('File is too large. Please upload a file under 10 MB.');
      return;
    }

    this.submitKycFileError.set(null);
    const existingPreviewUrl = this.submitKycFilePreviewUrl();
    if (existingPreviewUrl) URL.revokeObjectURL(existingPreviewUrl);
    this.submitKycFile.set(file);
    this.submitKycFilePreviewUrl.set(file.type.startsWith('image/') ? URL.createObjectURL(file) : null);
  }

  private clearSubmitKycFile(): void {
    this.submitKycFile.set(null);
    this.submitKycFileError.set(null);
    const existingPreviewUrl = this.submitKycFilePreviewUrl();
    if (existingPreviewUrl) URL.revokeObjectURL(existingPreviewUrl);
    this.submitKycFilePreviewUrl.set(null);
  }

  protected submitKyc(): void {
    const customer = this.selectedCustomer();
    if (!customer || this.kycForm.invalid) return;

    const file = this.submitKycFile();
    if (!file) {
      // Guards against Enter-key form submission, which fires (ngSubmit)
      // regardless of the submit button's [disabled] state.
      this.submitKycFileError.set('A document photo or scan is required.');
      return;
    }

    const { doc_type, doc_reference } = this.kycForm.getRawValue();
    this.submitKycUploading.set(true);
    this.customerService.uploadKycAttachment(file).subscribe({
      next: (res) => this.finishSubmitKyc(customer.id, doc_type, doc_reference, res.blob_ref),
      error: () => {
        this.submitKycUploading.set(false);
        this.messageService.add({
          severity: 'error',
          summary: 'Error',
          detail: 'Failed to upload the document. Please try again.',
        });
      },
    });
  }

  private finishSubmitKyc(
    customerId: string,
    docType: string,
    docReference: string,
    fileUrl: string | null,
  ): void {
    this.customerService.submitKyc(customerId, docType, docReference, fileUrl).subscribe({
      next: () => {
        this.submitKycUploading.set(false);
        this.messageService.add({ severity: 'success', summary: 'Success', detail: 'KYC Document submitted.' });
        this.closeSubmitKycModal();
        this.loadKycDocuments(customerId);
        this.reloadList();
      },
      error: (error: unknown) => {
        this.submitKycUploading.set(false);
        this.messageService.add({ severity: 'error', summary: 'Error', detail: errorMessageFor(error) });
      },
    });
  }

  protected viewDocument(url: string): void {
    this.viewingDocumentUrl.set(url);
  }

  protected closeDocumentPreview(): void {
    this.viewingDocumentUrl.set(null);
  }

  protected verifyKycDoc(docId: string, status: 'verified' | 'rejected'): void {
    const customer = this.selectedCustomer();
    if (!customer) return;

    this.customerService.verifyKyc(customer.id, docId, status).subscribe({
      next: () => {
        this.messageService.add({ severity: 'success', summary: 'Success', detail: `KYC Document ${status}.` });
        this.loadKycDocuments(customer.id);
        this.reloadList();
      },
      error: (error: unknown) => {
        this.messageService.add({ severity: 'error', summary: 'Error', detail: errorMessageFor(error) });
      },
    });
  }
}
