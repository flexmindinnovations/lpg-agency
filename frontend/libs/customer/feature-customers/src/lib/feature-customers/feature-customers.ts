import { HeaderPortalDirective , HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  OnInit,
  inject,
  signal,
  viewChild,
  DestroyRef,
} from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { KeyboardShortcutsService } from '@lpg/shared/util';
import { ButtonDirective, ButtonIcon, ButtonLabel } from 'primeng/button';
import { Drawer } from 'primeng/drawer';
import { IconField } from 'primeng/iconfield';
import { InputIcon } from 'primeng/inputicon';
import { InputText } from 'primeng/inputtext';
import { Select } from 'primeng/select';
import { Tag } from 'primeng/tag';
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
import { DataGridComponent, type DataGridColumn } from '@lpg/shared/ui';

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
  imports: [HeaderTitlePortalDirective, HeaderPortalDirective, 
    ReactiveFormsModule,
    ButtonDirective,
    ButtonIcon,
    ButtonLabel,
    InputText,
    Drawer,
    IconField,
    InputIcon,
    Select,
    Tag,
    Tabs,
    TabList,
    Tab,
    TabPanels,
    TabPanel,
    DataGridComponent,
    RouterLink,
    TitleCasePipe,
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

  protected readonly customers = signal<CustomerResponse[]>([]);
  protected readonly branches = signal<BranchResponse[]>([]);
  protected readonly selectedCustomer = signal<CustomerResponse | null>(null);
  protected readonly kycDocuments = signal<KycDocumentResponse[]>([]);
  protected readonly loading = signal(false);
  protected readonly searchQuery = signal('');

  // Modals Visibility Signals
  protected readonly showDetailDrawer = signal(false);
  protected readonly showAddAddressModal = signal(false);
  protected readonly showSubmitKycModal = signal(false);

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
    { field: 'customer_type', header: 'Type', sortable: true },
    { field: 'kyc_status', header: 'KYC Status', sortable: true },
    { field: 'status', header: 'Account Status', sortable: true },
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
    this.customerService.addAddress(customer.id, address_line).subscribe({
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
    this.showSubmitKycModal.set(true);
  }

  protected closeSubmitKycModal(): void {
    this.showSubmitKycModal.set(false);
  }

  protected submitKyc(): void {
    const customer = this.selectedCustomer();
    if (!customer || this.kycForm.invalid) return;

    const { doc_type, doc_reference } = this.kycForm.getRawValue();
    this.customerService.submitKyc(customer.id, doc_type, doc_reference).subscribe({
      next: () => {
        this.messageService.add({ severity: 'success', summary: 'Success', detail: 'KYC Document submitted.' });
        this.closeSubmitKycModal();
        this.loadKycDocuments(customer.id);
        this.reloadList();
      },
      error: (error: unknown) => {
        this.messageService.add({ severity: 'error', summary: 'Error', detail: errorMessageFor(error) });
      },
    });
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
