import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, NonNullableFormBuilder, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { catchError, firstValueFrom, map, of, tap, type Observable } from 'rxjs';

import { StepperModule } from 'primeng/stepper';
import { ButtonDirective } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { SelectModule } from 'primeng/select';
import { CheckboxModule } from 'primeng/checkbox';
import { DatePickerModule } from 'primeng/datepicker';
import { Dialog } from 'primeng/dialog';
import { MessageService } from 'primeng/api';
import { ToastModule } from 'primeng/toast';
import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import { DocumentUploadComponent, FormFieldComponent } from '@lpg/shared/ui';
import {
  CustomerService,
  AdminBranchService,
  errorMessageFor,
  type BranchResponse,
  type OnboardingDraftResponse,
  type RecognizeKycDocumentResponse,
} from '@lpg/shared/data-access';
import {
  DATE_INPUT_FORMAT,
  DATE_INPUT_PLACEHOLDER,
  PINCODE_PATTERN,
  asKycDocType,
  compactIdentifier,
  gstinValidator,
  kycNumberValidator,
  toIsoDate,
  type KycDocType,
} from '../validators/identifier-validators';

// Backend validation requires strict E.164 (`domain/customer/customer.py`'s
// `_E164_PHONE_REGEX`) — a `+` and country code are non-negotiable on
// submit. Indian mobile numbers are always 10 digits starting 6-9, so a
// bare local number typed without a country code can be unambiguously
// normalized to +91 on blur rather than forcing every user to type it.
const PHONE_PATTERN = /^\+[1-9]\d{9,14}$/;
type CustomerType = 'domestic' | 'commercial' | 'industrial' | 'government';
type AddressType = 'delivery' | 'billing' | 'both';
const BUSINESS_TYPES: readonly CustomerType[] = ['commercial', 'industrial', 'government'];
const INDIAN_MOBILE_PATTERN = /^[6-9]\d{9}$/;

@Component({
  selector: 'lpg-customer-onboarding-wizard',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    StepperModule,
    ButtonDirective,
    InputTextModule,
    SelectModule,
    CheckboxModule,
    DatePickerModule,
    Dialog,
    ToastModule,
    HeaderTitlePortalDirective,
    FormFieldComponent,
    DocumentUploadComponent,
  ],
  templateUrl: './customer-onboarding-wizard.component.html',
  styleUrl: './customer-onboarding-wizard.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CustomerOnboardingWizardComponent implements OnInit {
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly customerService = inject(CustomerService);
  private readonly branchService = inject(AdminBranchService);
  private readonly messageService = inject(MessageService);
  private readonly router = inject(Router);

  protected readonly currentStep = signal(1);
  protected readonly isSubmitting = signal(false);
  protected readonly branches = signal<BranchResponse[]>([]);

  protected readonly entryModeOptions = [
    { label: 'Auto-fill from Document', value: 'auto' as const },
    { label: 'Manual Entry', value: 'manual' as const },
  ];
  protected readonly entryMode = signal<'auto' | 'manual'>('manual');
  /** Set only when server-side recognition succeeded but returned no usable
   *  document type/number — the `<lpg-document-upload>` control surfaces its
   *  own upload/read errors. */
  protected readonly ocrError = signal<string | null>(null);
  protected readonly extractedSummary = signal<string | null>(null);

  /** Stores the KYC image and normalises the response to the shape
   *  `<lpg-document-upload>` expects. */
  protected readonly kycUploader = (file: File): Observable<{ blobRef: string }> =>
    this.customerService.uploadKycAttachment(file).pipe(map((r) => ({ blobRef: r.blob_ref })));
  protected readonly kycRecognizer = (blobRef: string): Observable<RecognizeKycDocumentResponse> =>
    this.customerService.recognizeKycDocument(blobRef);

  protected readonly draftId = signal<string | null>(null);
  protected readonly savingDraft = signal(false);
  protected readonly showLeaveDialog = signal(false);
  private leaveDialogResolver: ((result: boolean) => void) | null = null;

  protected readonly showResumeBanner = signal(false);
  protected readonly latestDraft = signal<OnboardingDraftResponse | null>(null);

  protected readonly customerCategoryOptions: { label: string; value: CustomerType }[] = [
    { label: 'Domestic (household)', value: 'domestic' },
    { label: 'Commercial (shop, hotel, restaurant)', value: 'commercial' },
    { label: 'Industrial', value: 'industrial' },
    { label: 'Government / institution', value: 'government' },
  ];
  protected readonly dateInputFormat = DATE_INPUT_FORMAT;
  protected readonly dateInputPlaceholder = DATE_INPUT_PLACEHOLDER;
  protected readonly today = new Date();
  /** Business connections are billed to the business (name + GSTIN on B2B
   *  invoices); the person's name becomes the contact person (DO-02). */
  protected readonly isBusiness = signal(false);
  /** Shown after a successful Submit & Approve. */
  protected readonly createdConsumerNumber = signal<string | null>(null);

  protected readonly addressTypeOptions: { label: string; value: AddressType }[] = [
    { label: 'Delivery', value: 'delivery' },
    { label: 'Billing', value: 'billing' },
    { label: 'Both', value: 'both' },
  ];

  protected readonly kycDocTypeOptions: { label: string; value: KycDocType }[] = [
    { label: 'Aadhaar card', value: 'aadhaar' },
    { label: 'PAN card', value: 'pan' },
    { label: 'Voter ID (EPIC)', value: 'voter_id' },
    { label: 'Driving licence', value: 'driving_license' },
    { label: 'Passport', value: 'passport' },
  ];

  protected docTypeLabel(value: string | undefined): string {
    return this.kycDocTypeOptions.find((o) => o.value === value)?.label ?? '—';
  }

  protected categoryLabel(value: string | undefined): string {
    return this.customerCategoryOptions.find((o) => o.value === value)?.label ?? '—';
  }

  protected readonly registrationForm = this.fb.group({
    first_name: ['', Validators.required],
    last_name: ['', Validators.required],
    phone_number: ['', [Validators.required, Validators.pattern(PHONE_PATTERN)]],
    branch_id: ['', Validators.required],
    consumer_category: ['domestic' as CustomerType, Validators.required],
    business_name: [''],
    gstin: ['', gstinValidator],
    // Optional — Validators.pattern only runs against a non-empty value, so
    // this doesn't make the field required.
    alternate_mobile: ['', Validators.pattern(PHONE_PATTERN)],
    date_of_birth: [null as Date | null, Validators.required],
  });

  protected readonly addressForm = this.fb.group({
    address_type: ['delivery' as AddressType, Validators.required],
    line_1: ['', Validators.required],
    line_2: [''],
    landmark: [''],
    area: ['', Validators.required],
    city: ['', Validators.required],
    district: ['', Validators.required],
    state: ['', Validators.required],
    pincode: ['', [Validators.required, Validators.pattern(PINCODE_PATTERN)]],
  });

  protected readonly kycForm = this.fb.group({
    doc_type: ['aadhaar' as KycDocType, Validators.required],
    document_number: ['', Validators.required],
    // Aadhaar/PAN cards carry neither an issue nor an expiry date — only
    // required when the selected document type actually has one (Passport).
    issue_date: [null as Date | null],
    expiry_date: [null as Date | null],
    document_file_ref: [null as string | null],
  });

  /** Validator-key → message for the wizard's step forms. */
  private static readonly PHONE_MSG =
    'Enter a valid 10-digit mobile number, or a full number with country code (e.g. +919876543210).';
  protected readonly fieldMessages = {
    first_name: { required: 'First name is required.' },
    last_name: { required: 'Last name is required.' },
    phone_number: {
      required: 'A primary phone number is required.',
      pattern: CustomerOnboardingWizardComponent.PHONE_MSG,
    },
    alternate_mobile: { pattern: CustomerOnboardingWizardComponent.PHONE_MSG },
    branch_id: { required: 'Select an operating branch.' },
    consumer_category: { required: 'Select a consumer category.' },
    business_name: { required: 'Enter the business or institution name.' },
    gstin: { gstin: 'Enter a valid 15-character GSTIN, like 27AAPFU0939F1ZV.' },
    date_of_birth: { required: 'Date of birth is required.' },
    address_type: { required: 'Select an address type.' },
    line_1: { required: 'Address line 1 is required.' },
    area: { required: 'Area / locality is required.' },
    city: { required: 'City is required.' },
    district: { required: 'District is required.' },
    state: { required: 'State is required.' },
    pincode: {
      required: 'A PIN code is required.',
      pattern: 'Enter a valid 6-digit PIN code (it cannot start with 0).',
    },
    doc_type: { required: 'Select a document type.' },
    document_number: {
      required: 'Document number is required.',
      kycNumber: 'Check the document number.',
    },
    issue_date: { required: 'Issue date is required.' },
    expiry_date: { required: 'Expiry date is required.' },
  };

  constructor() {
    this.kycForm.controls.document_number.addValidators(
      kycNumberValidator(() => this.kycForm.controls.doc_type.value),
    );
    this.registrationForm.controls.consumer_category.valueChanges.subscribe((category) => {
      const business = BUSINESS_TYPES.includes(category);
      this.isBusiness.set(business);
      const { business_name, date_of_birth } = this.registrationForm.controls;
      business_name.setValidators(business ? Validators.required : null);
      // A business has no date of birth; a household's account holder does.
      date_of_birth.setValidators(business ? null : Validators.required);
      business_name.updateValueAndValidity();
      date_of_birth.updateValueAndValidity();
    });

    this.kycForm.controls.doc_type.valueChanges.subscribe((docType) => {
      const issueDateCtrl = this.kycForm.controls.issue_date;
      const expiryDateCtrl = this.kycForm.controls.expiry_date;
      if (docType === 'passport') {
        issueDateCtrl.setValidators(Validators.required);
        expiryDateCtrl.setValidators(Validators.required);
      } else {
        issueDateCtrl.clearValidators();
        expiryDateCtrl.clearValidators();
      }
      issueDateCtrl.updateValueAndValidity();
      expiryDateCtrl.updateValueAndValidity();
      this.kycForm.controls.document_number.updateValueAndValidity();
    });
  }

  ngOnInit() {
    this.branchService.listBranches().subscribe({
      next: (branches) => this.branches.set(branches),
      error: () =>
        this.messageService.add({
          severity: 'error',
          summary: 'Error',
          detail: 'Failed to load branches.',
        }),
    });

    this.customerService.listMyOnboardingDrafts().subscribe({
      next: (page) => {
        const [mostRecent] = page.items;
        if (mostRecent) {
          this.latestDraft.set(mostRecent);
          this.showResumeBanner.set(true);
        }
      },
      error: () => {
        // No drafts to resume is not an error state worth surfacing.
      },
    });
  }

  /** Auto-prefixes a bare 10-digit Indian mobile number with +91 on blur. */
  protected normalizePhoneField(controlName: 'phone_number' | 'alternate_mobile'): void {
    const control = this.registrationForm.controls[controlName];
    const raw = control.value.trim();
    if (INDIAN_MOBILE_PATTERN.test(raw)) {
      control.setValue(`+91${raw}`);
    }
  }

  protected nextStep(formGroup: import('@angular/forms').FormGroup, nextStepNum: number) {
    if (formGroup.invalid) {
      formGroup.markAllAsTouched();
      return;
    }
    this.currentStep.set(nextStepNum);
  }

  protected prevStep(prevStepNum: number) {
    this.currentStep.set(prevStepNum);
  }

  protected setEntryMode(mode: 'auto' | 'manual') {
    this.entryMode.set(mode);
    this.ocrError.set(null);
  }

  /** `<lpg-document-upload>` (uploaded) — the image is stored, keep its ref. */
  protected onKycDocUploaded(event: { blobRef: string }): void {
    this.kycForm.patchValue({ document_file_ref: event.blobRef });
  }

  /** `<lpg-document-upload>` (recognized) — the server-side OCR "second pass". */
  protected onKycRecognized(result: unknown): void {
    this.applyExtractedData(result as RecognizeKycDocumentResponse);
  }

  /** `<lpg-document-upload>` (cleared) — drop the ref and any extraction. */
  protected onKycDocCleared(): void {
    this.ocrError.set(null);
    this.extractedSummary.set(null);
    this.kycForm.patchValue({ document_file_ref: null });
  }

  private applyExtractedData(result: RecognizeKycDocumentResponse) {
    if (!result.doc_type || !result.document_number) {
      this.ocrError.set(
        'Could not recognize a supported document (Aadhaar or PAN) in this image. ' +
          'Please upload a clearer photo or switch to manual entry.',
      );
      return;
    }

    this.kycForm.patchValue({
      doc_type: asKycDocType(result.doc_type),
      document_number: result.document_number,
    });
    this.kycForm.controls.document_number.markAsTouched();

    const docLabel = result.doc_type === 'aadhaar' ? 'Aadhaar' : 'PAN';
    const extracted: string[] = [`${docLabel} number`];

    // Name/DOB/address come from regex heuristics over free-form OCR text,
    // not structurally validated the way the document number is — on a
    // low-confidence read (real card photos: small print, mixed
    // Hindi/English, glare) that heuristic is more likely to latch onto
    // noise. Below this threshold, leave those fields for the user to type
    // rather than pre-fill something that merely looks right-shaped.
    const RELIABLE_CONFIDENCE = 0.65;
    const canTrustOcrFields = result.confidence >= RELIABLE_CONFIDENCE;

    if (canTrustOcrFields && result.full_name) {
      const [firstName, ...rest] = result.full_name.split(' ');
      this.registrationForm.patchValue({
        first_name: firstName,
        last_name: rest.join(' ') || firstName,
      });
      extracted.push('name');
    }
    if (canTrustOcrFields && result.date_of_birth) {
      this.registrationForm.patchValue({ date_of_birth: new Date(result.date_of_birth) });
      extracted.push('date of birth');
    }

    // The Aadhaar address block is freeform, unlabeled text with no fixed
    // structure — meaningfully less reliable than the fields above even at
    // the same OCR confidence, since a correctly-read line can still get
    // split into the wrong field (e.g. a locality name landing in "area"
    // instead of "city"). Every field patched here stays required and
    // editable on the Address step, so this is a head start, not a
    // silent write.
    if (canTrustOcrFields) {
      this.addressForm.patchValue({
        ...(result.address_line_1 ? { line_1: result.address_line_1 } : {}),
        ...(result.address_line_2 ? { line_2: result.address_line_2 } : {}),
        ...(result.address_landmark ? { landmark: result.address_landmark } : {}),
        ...(result.address_area ? { area: result.address_area } : {}),
        ...(result.address_city ? { city: result.address_city } : {}),
        ...(result.address_district ? { district: result.address_district } : {}),
        ...(result.address_state ? { state: result.address_state } : {}),
        ...(result.address_pincode ? { pincode: result.address_pincode } : {}),
      });
      if (result.address_line_1 || result.address_city || result.address_pincode) {
        extracted.push('address');
      }
    }

    if (canTrustOcrFields) {
      this.extractedSummary.set(
        `Pre-filled ${extracted.join(', ')} from the document. Please review before continuing — ` +
          'OCR can misread details.',
      );
    } else {
      this.extractedSummary.set(
        `Pre-filled the ${docLabel} number. Image quality was too low to reliably read the rest ` +
          'of the details — please fill those in manually.',
      );
    }
  }

  /** Point-in-time check — reactive forms' `dirty` needs no signal plumbing. */
  protected hasUnsavedChanges(): boolean {
    return this.registrationForm.dirty || this.addressForm.dirty || this.kycForm.dirty;
  }

  /** `CanDeactivate` guard entrypoint. */
  confirmLeave(): boolean | Promise<boolean> {
    if (!this.hasUnsavedChanges()) return true;
    this.showLeaveDialog.set(true);
    return new Promise<boolean>((resolve) => {
      this.leaveDialogResolver = resolve;
    });
  }

  protected onCancelLeave() {
    this.showLeaveDialog.set(false);
    this.leaveDialogResolver?.(false);
    this.leaveDialogResolver = null;
  }

  protected onDiscardAndLeave() {
    this.showLeaveDialog.set(false);
    this.leaveDialogResolver?.(true);
    this.leaveDialogResolver = null;
  }

  protected onSaveAndLeave() {
    this.saveDraftNow().subscribe({
      next: () => {
        this.showLeaveDialog.set(false);
        this.leaveDialogResolver?.(true);
        this.leaveDialogResolver = null;
      },
      error: () => {
        this.messageService.add({
          severity: 'error',
          summary: 'Save failed',
          detail: 'Could not save your draft. Try again, or discard and leave.',
        });
      },
    });
  }

  protected onSaveAndExit() {
    this.saveDraftNow().subscribe({
      next: () => {
        // Already saved — don't make the unsaved-changes guard ask again.
        this.registrationForm.markAsPristine();
        this.addressForm.markAsPristine();
        this.kycForm.markAsPristine();
        this.messageService.add({
          severity: 'success',
          summary: 'Draft saved',
          detail: 'Resume this registration any time from this page.',
        });
        this.router.navigate(['/customers']);
      },
      error: () =>
        this.messageService.add({
          severity: 'error',
          summary: 'Save failed',
          detail: 'Could not save your draft.',
        }),
    });
  }

  private saveDraftNow() {
    this.savingDraft.set(true);
    const regData = this.registrationForm.getRawValue();
    const addrData = this.addressForm.getRawValue();
    const kycData = this.kycForm.getRawValue();

    return this.customerService
      .saveOnboardingDraft({
        draft_id: this.draftId(),
        branch_id: regData.branch_id || null,
        current_step: this.currentStep(),
        registration_data: regData,
        address_data: addrData,
        kyc_data: kycData,
        kyc_document_blob_ref: kycData.document_file_ref,
      })
      .pipe(
        tap({
          next: (draft) => {
            this.draftId.set(draft.id);
            this.savingDraft.set(false);
          },
          error: () => this.savingDraft.set(false),
        }),
      );
  }

  protected resumeDraft() {
    const draft = this.latestDraft();
    if (!draft) return;

    const reg = draft.registration_data as Record<string, unknown>;
    const addr = draft.address_data as Record<string, unknown>;
    const kyc = draft.kyc_data as Record<string, unknown>;

    this.registrationForm.patchValue({
      first_name: (reg['first_name'] as string) ?? '',
      last_name: (reg['last_name'] as string) ?? '',
      phone_number: (reg['phone_number'] as string) ?? '',
      branch_id: (reg['branch_id'] as string) ?? '',
      consumer_category: (reg['consumer_category'] as CustomerType) ?? 'domestic',
      business_name: (reg['business_name'] as string) ?? '',
      gstin: (reg['gstin'] as string) ?? '',
      alternate_mobile: (reg['alternate_mobile'] as string) ?? '',
      date_of_birth: reg['date_of_birth'] ? new Date(reg['date_of_birth'] as string) : null,
    });
    this.addressForm.patchValue({
      address_type: (addr['address_type'] as AddressType) ?? 'delivery',
      line_1: (addr['line_1'] as string) ?? '',
      line_2: (addr['line_2'] as string) ?? '',
      landmark: (addr['landmark'] as string) ?? '',
      area: (addr['area'] as string) ?? '',
      city: (addr['city'] as string) ?? '',
      district: (addr['district'] as string) ?? '',
      state: (addr['state'] as string) ?? '',
      pincode: (addr['pincode'] as string) ?? '',
    });
    this.kycForm.patchValue({
      doc_type: asKycDocType(kyc['doc_type']),
      document_number: (kyc['document_number'] as string) ?? '',
      issue_date: kyc['issue_date'] ? new Date(kyc['issue_date'] as string) : null,
      expiry_date: kyc['expiry_date'] ? new Date(kyc['expiry_date'] as string) : null,
      document_file_ref: draft.kyc_document_blob_ref,
    });

    this.draftId.set(draft.id);
    this.currentStep.set(draft.current_step);
    this.showResumeBanner.set(false);
  }

  protected discardBannerDraft() {
    const draft = this.latestDraft();
    this.showResumeBanner.set(false);
    if (!draft) return;
    this.customerService.deleteOnboardingDraft(draft.id).subscribe();
  }

  protected async submitWizard() {
    if (this.registrationForm.invalid || this.addressForm.invalid || this.kycForm.invalid) {
      this.messageService.add({
        severity: 'error',
        summary: 'Error',
        detail: 'Please complete all steps correctly.',
      });
      return;
    }
    this.isSubmitting.set(true);

    const regData = this.registrationForm.getRawValue();
    const addrData = this.addressForm.getRawValue();
    const kycData = this.kycForm.getRawValue();

    try {
      // One request registers the customer with their address, so a failed
      // address never leaves a customer behind without one.
      const personName = `${regData.first_name} ${regData.last_name}`.trim();
      const business = BUSINESS_TYPES.includes(regData.consumer_category);
      const customer = await firstValueFrom(
        this.customerService.register({
          full_name: business ? regData.business_name.trim() : personName,
          contact_person: business ? personName : null,
          customer_type: regData.consumer_category,
          gstin: business && regData.gstin.trim() ? compactIdentifier(regData.gstin) : null,
          phone_number: regData.phone_number,
          alternate_mobile: regData.alternate_mobile || null,
          date_of_birth:
            !business && regData.date_of_birth ? toIsoDate(regData.date_of_birth) : null,
          branch_id: regData.branch_id,
          address_type: addrData.address_type,
          line_1: addrData.line_1,
          line_2: addrData.line_2 || null,
          landmark: addrData.landmark || null,
          area: addrData.area,
          city: addrData.city,
          district: addrData.district,
          state: addrData.state,
          pincode: addrData.pincode,
        }),
      );

      const docId = await firstValueFrom(
        this.customerService.submitKyc(
          customer.id,
          kycData.doc_type,
          compactIdentifier(kycData.document_number),
          kycData.document_file_ref,
        ),
      );
      // "Submit & Approve": verifying the document activates the connection
      // and assigns the consumer number. Staff without KYC rights leave it
      // pending for someone who has them.
      const approved = await firstValueFrom(
        this.customerService.verifyKyc(customer.id, docId, 'verified').pipe(
          map(() => true),
          catchError(() => of(false)),
        ),
      );
      const refreshed = approved
        ? await firstValueFrom(
            this.customerService.get(customer.id).pipe(catchError(() => of(customer))),
          )
        : customer;
      this.createdConsumerNumber.set(refreshed.consumer_number ?? null);

      const draftId = this.draftId();
      if (draftId) {
        this.customerService.deleteOnboardingDraft(draftId).subscribe();
      }

      // A successful submit shouldn't re-trigger the unsaved-changes guard.
      this.registrationForm.markAsPristine();
      this.addressForm.markAsPristine();
      this.kycForm.markAsPristine();

      const consumerNumber = this.createdConsumerNumber();
      this.messageService.add({
        severity: 'success',
        summary: consumerNumber ? 'Connection approved' : 'Customer registered',
        detail: consumerNumber
          ? `Consumer number ${consumerNumber}. The customer can book now.`
          : 'KYC is waiting for verification before the customer can book.',
        life: 8000,
      });
      this.router.navigate(['/customers']);
    } catch (err) {
      this.messageService.add({
        severity: 'error',
        summary: 'Could not register the customer',
        detail: errorMessageFor(err),
      });
    } finally {
      this.isSubmitting.set(false);
    }
  }
}
