import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, NonNullableFormBuilder, Validators } from '@angular/forms';
import { Router } from '@angular/router';

import { StepperModule } from 'primeng/stepper';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { SelectModule } from 'primeng/select';
import { CheckboxModule } from 'primeng/checkbox';
import { DatePickerModule } from 'primeng/datepicker';
import { MessageService } from 'primeng/api';
import { ToastModule } from 'primeng/toast';
import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import { CustomerService, AdminBranchService, type BranchResponse } from '@lpg/shared/data-access';

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

  protected readonly currentStep = signal(1);
  protected readonly isSubmitting = signal(false);
  protected readonly branches = signal<BranchResponse[]>([]);

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
    phone_number: ['', [Validators.required, Validators.pattern(/^\+[1-9]\d{9,14}$/)]],
    branch_id: ['', Validators.required],
    consumer_category: ['domestic', Validators.required],
    is_commercial: [false],
    contact_person: [''],
    alternate_mobile: [''],
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
    issue_date: [null as Date | null, Validators.required],
    expiry_date: [null as Date | null, Validators.required],
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
  }

  protected isInvalid(form: import('@angular/forms').FormGroup, controlName: string): boolean {
    const control = form.get(controlName);
    return control ? control.invalid && control.touched : false;
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
        consumer_number: `CN-${Date.now()}`, // fallback since consumer number is required
        phone_number: regData.phone_number,
        branch_id: regData.branch_id,
        address_line: `${addrData.line_1}, ${addrData.area}, ${addrData.city}, ${addrData.state} - ${addrData.pincode}`,
      };

      const customer = await this.customerService.register(registerPayload).toPromise();

      if (customer) {
        // 2. Add full Address
        await this.customerService
          .addAddress(
            customer.id,
            `${addrData.line_1} ${addrData.line_2}, ${addrData.landmark}, ${addrData.area}, ${addrData.city}, ${addrData.district}, ${addrData.state}, ${addrData.pincode}`,
          )
          .toPromise();

        // 3. Submit KYC
        await this.customerService
          .submitKyc(customer.id, kycData.doc_type, kycData.document_number)
          .toPromise();
      }

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
