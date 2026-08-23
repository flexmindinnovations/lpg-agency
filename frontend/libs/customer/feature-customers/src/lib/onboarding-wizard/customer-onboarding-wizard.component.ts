import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, NonNullableFormBuilder, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { tap } from 'rxjs';

import { StepperModule } from 'primeng/stepper';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { SelectModule } from 'primeng/select';
import { CheckboxModule } from 'primeng/checkbox';
import { DatePickerModule } from 'primeng/datepicker';
import { Dialog } from 'primeng/dialog';
import { MessageService } from 'primeng/api';
import { ToastModule } from 'primeng/toast';
import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import {
  CustomerService,
  AdminBranchService,
  type BranchResponse,
  type OnboardingDraftResponse,
  type RecognizeKycDocumentResponse,
} from '@lpg/shared/data-access';

const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;

// Backend validation requires strict E.164 (`domain/customer/customer.py`'s
// `_E164_PHONE_REGEX`) — a `+` and country code are non-negotiable on
// submit. Indian mobile numbers are always 10 digits starting 6-9, so a
// bare local number typed without a country code can be unambiguously
// normalized to +91 on blur rather than forcing every user to type it.
const PHONE_PATTERN = /^\+[1-9]\d{9,14}$/;
const INDIAN_MOBILE_PATTERN = /^[6-9]\d{9}$/;

@Component({
  selector: 'lpg-customer-onboarding-wizard',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    StepperModule,
    ButtonModule,
    InputTextModule,
    SelectModule,
    CheckboxModule,
    DatePickerModule,
    Dialog,
    ToastModule,
    HeaderTitlePortalDirective,
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
  private readonly destroyRef = inject(DestroyRef);

  protected readonly currentStep = signal(1);
  protected readonly isSubmitting = signal(false);
  protected readonly branches = signal<BranchResponse[]>([]);

  protected readonly entryModeOptions = [
    { label: 'Auto-fill from Document', value: 'auto' as const },
    { label: 'Manual Entry', value: 'manual' as const },
  ];
  protected readonly entryMode = signal<'auto' | 'manual'>('manual');
  protected readonly ocrStage = signal<'uploading' | 'analyzing' | null>(null);
  protected readonly ocrError = signal<string | null>(null);
  protected readonly uploadedFileName = signal<string | null>(null);
  protected readonly uploadedFileSize = signal<number | null>(null);
  protected readonly filePreviewUrl = signal<string | null>(null);
  protected readonly isDragging = signal(false);
  protected readonly extractedSummary = signal<string | null>(null);

  protected readonly draftId = signal<string | null>(null);
  protected readonly savingDraft = signal(false);
  protected readonly showLeaveDialog = signal(false);
  private leaveDialogResolver: ((result: boolean) => void) | null = null;

  protected readonly showResumeBanner = signal(false);
  protected readonly latestDraft = signal<OnboardingDraftResponse | null>(null);

  protected readonly customerCategoryOptions = [
    { label: 'Domestic', value: 'domestic' },
    { label: 'Commercial', value: 'commercial' },
    { label: 'Industrial', value: 'industrial' },
  ];

  protected readonly addressTypeOptions = [
    { label: 'Delivery', value: 'delivery' },
    { label: 'Billing', value: 'billing' },
    { label: 'Both', value: 'both' },
  ];

  protected readonly kycDocTypeOptions = [
    { label: 'Aadhaar Card', value: 'aadhaar' },
    { label: 'PAN Card', value: 'pan' },
    { label: 'Passport', value: 'passport' },
  ];

  protected readonly registrationForm = this.fb.group({
    first_name: ['', Validators.required],
    last_name: ['', Validators.required],
    phone_number: ['', [Validators.required, Validators.pattern(PHONE_PATTERN)]],
    branch_id: ['', Validators.required],
    consumer_category: ['domestic', Validators.required],
    is_commercial: [false],
    contact_person: [''],
    // Optional — Validators.pattern only runs against a non-empty value, so
    // this doesn't make the field required.
    alternate_mobile: ['', Validators.pattern(PHONE_PATTERN)],
    date_of_birth: [null as Date | null, Validators.required],
  });

  protected readonly addressForm = this.fb.group({
    address_type: ['delivery', Validators.required],
    line_1: ['', Validators.required],
    line_2: [''],
    landmark: [''],
    area: ['', Validators.required],
    city: ['', Validators.required],
    district: ['', Validators.required],
    state: ['', Validators.required],
    pincode: ['', [Validators.required, Validators.pattern(/^[0-9]{6}$/)]],
  });

  protected readonly kycForm = this.fb.group({
    doc_type: ['aadhaar', Validators.required],
    document_number: ['', Validators.required],
    // Aadhaar/PAN cards carry neither an issue nor an expiry date — only
    // required when the selected document type actually has one (Passport).
    issue_date: [null as Date | null],
    expiry_date: [null as Date | null],
    document_file_ref: [null as string | null],
  });

  constructor() {
    this.registrationForm.controls.is_commercial.valueChanges.subscribe((isCommercial) => {
      const contactPersonCtrl = this.registrationForm.controls.contact_person;
      if (isCommercial) {
        contactPersonCtrl.setValidators(Validators.required);
      } else {
        contactPersonCtrl.clearValidators();
      }
      contactPersonCtrl.updateValueAndValidity();
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
    });

    this.destroyRef.onDestroy(() => {
      const existingPreviewUrl = this.filePreviewUrl();
      if (existingPreviewUrl) URL.revokeObjectURL(existingPreviewUrl);
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

  protected isInvalid(form: import('@angular/forms').FormGroup, controlName: string): boolean {
    const control = form.get(controlName);
    return control ? control.invalid && control.touched : false;
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

  protected onFileSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = '';
    if (file) this.processFile(file);
  }

  protected onDragOver(event: DragEvent) {
    event.preventDefault();
    this.isDragging.set(true);
  }

  protected onDragLeave(event: DragEvent) {
    event.preventDefault();
    this.isDragging.set(false);
  }

  protected onDrop(event: DragEvent) {
    event.preventDefault();
    this.isDragging.set(false);
    const file = event.dataTransfer?.files?.[0];
    if (file) this.processFile(file);
  }

  protected removeFile() {
    this.uploadedFileName.set(null);
    const existingPreviewUrl = this.filePreviewUrl();
    if (existingPreviewUrl) URL.revokeObjectURL(existingPreviewUrl);
    this.filePreviewUrl.set(null);
    this.ocrError.set(null);
    this.extractedSummary.set(null);
    this.ocrStage.set(null);
    this.kycForm.patchValue({ document_file_ref: null });
  }

  protected formatFileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  private processFile(file: File) {
    if (!file.type.startsWith('image/')) {
      this.ocrError.set('Unsupported file type. Please upload a JPG or PNG image.');
      return;
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      this.ocrError.set('File is too large. Please upload an image under 10 MB.');
      return;
    }

    this.ocrError.set(null);
    this.extractedSummary.set(null);
    this.uploadedFileName.set(file.name);
    this.uploadedFileSize.set(file.size);
    const existingPreviewUrl = this.filePreviewUrl();
    if (existingPreviewUrl) URL.revokeObjectURL(existingPreviewUrl);
    this.filePreviewUrl.set(URL.createObjectURL(file));
    this.ocrStage.set('uploading');

    this.customerService.uploadKycAttachment(file).subscribe({
      next: (res) => {
        this.kycForm.patchValue({ document_file_ref: res.blob_ref });
        this.recognizeDocument(res.blob_ref);
      },
      error: () => {
        this.ocrStage.set(null);
        this.messageService.add({
          severity: 'error',
          summary: 'Upload failed',
          detail: 'Could not upload the document image. You can still fill details manually.',
        });
      },
    });
  }

  /**
   * OCR runs entirely server-side (a heavier, more accurate model than is
   * practical to ship to every browser — see
   * `RecognizeKycDocumentUseCase`'s docstring on the backend). The uploaded
   * image never needs a client-side OCR pass of its own.
   */
  private recognizeDocument(blobRef: string) {
    this.ocrStage.set('analyzing');
    this.customerService.recognizeKycDocument(blobRef).subscribe({
      next: (res) => {
        this.ocrStage.set(null);
        // The dropzone may have been cleared (file removed) before this
        // call returned — don't resurrect a stale result.
        if (!this.uploadedFileName()) return;
        this.applyExtractedData(res);
      },
      error: () => {
        this.ocrStage.set(null);
        this.ocrError.set('Failed to read the document. Please try again or fill details manually.');
      },
    });
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
      doc_type: result.doc_type,
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
      consumer_category: (reg['consumer_category'] as string) ?? 'domestic',
      is_commercial: Boolean(reg['is_commercial']),
      contact_person: (reg['contact_person'] as string) ?? '',
      alternate_mobile: (reg['alternate_mobile'] as string) ?? '',
      date_of_birth: reg['date_of_birth'] ? new Date(reg['date_of_birth'] as string) : null,
    });
    this.addressForm.patchValue({
      address_type: (addr['address_type'] as string) ?? 'delivery',
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
      doc_type: (kyc['doc_type'] as string) ?? 'aadhaar',
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
      // 1. Register Customer (Map to RegisterCustomerRequest)
      const registerPayload = {
        full_name: `${regData.first_name} ${regData.last_name}`,
        customer_type: regData.consumer_category,
        // Deliberately omitted, not defaulted — `RegisterCustomerRequest.
        // consumer_number` is genuinely optional on the backend (`str |
        // None = None`), and stays null through "onboarding"/
        // "pending_approval" by domain design (Customer.__init__'s own
        // invariant only requires it once status is active+). The real,
        // properly-sequenced number is assigned once the account is
        // approved (see VerifyKycDocumentUseCase's auto-approve-on-fully-
        // verified-KYC path). A client-side `Date.now()` placeholder was
        // sent here before, producing consumer numbers like
        // "CN-1787232609075" that never got corrected.
        phone_number: regData.phone_number,
        branch_id: regData.branch_id,
        // No address here. `RegisterCustomerRequest` carries `line_1`/`area`/
        // `city`/… since `de17b27d462e`; the `address_line` key this used to
        // send has not existed on that schema since, and Pydantic silently
        // dropped it — so this looked like it registered an address and never
        // did. The address is created by the `addAddress` call below, which is
        // where it actually happened all along.
      };

      const customer = await this.customerService.register(registerPayload).toPromise();

      if (customer) {
        // 2. Add full Address
        await this.customerService
          .addAddress(customer.id, {
            address_type: addrData.address_type,
            line_1: addrData.line_1,
            line_2: addrData.line_2 || undefined,
            landmark: addrData.landmark || undefined,
            area: addrData.area,
            city: addrData.city,
            district: addrData.district,
            state: addrData.state,
            pincode: addrData.pincode,
          })
          .toPromise();

        // 3. Submit KYC
        await this.customerService
          .submitKyc(
            customer.id,
            kycData.doc_type,
            kycData.document_number,
            kycData.document_file_ref,
          )
          .toPromise();
      }

      const draftId = this.draftId();
      if (draftId) {
        this.customerService.deleteOnboardingDraft(draftId).subscribe();
      }

      // A successful submit shouldn't re-trigger the unsaved-changes guard.
      this.registrationForm.markAsPristine();
      this.addressForm.markAsPristine();
      this.kycForm.markAsPristine();

      this.messageService.add({
        severity: 'success',
        summary: 'Success',
        detail: 'Customer onboarded successfully.',
      });
      this.router.navigate(['/customers']);
    } catch (_error) {
      this.messageService.add({
        severity: 'error',
        summary: 'Error',
        detail: 'Failed to onboard customer.',
      });
    } finally {
      this.isSubmitting.set(false);
    }
  }
}
