import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import {
  DetailItemComponent,
  DetailListComponent,
  FormFieldComponent,
  PageHeaderComponent,
  SectionCardComponent,
} from '@lpg/shared/ui';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import {
  AbstractControl,
  NonNullableFormBuilder,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from '@angular/forms';
import { ButtonDirective } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Message } from 'primeng/message';
import {
  AuthService,
  MyProfileService,
  NotifyService,
  errorMessageFor,
  isAppError,
} from '@lpg/shared/data-access';
import { roleLabel } from '@lpg/shared/util';

/** Same floor the backend applies to every new password (`Settings.password_min_length`). */
const MIN_PASSWORD_LENGTH = 12;
const PHONE_PATTERN = /^\+?[0-9 ()-]{7,20}$/;

function passwordsMatch(group: AbstractControl): ValidationErrors | null {
  return group.get('newPassword')?.value === group.get('confirmPassword')?.value
    ? null
    : { passwordMismatch: true };
}

/**
 * The signed-in user's own account (DA-30): name and contact phone are
 * editable, the password can be changed (current password required), and
 * the role is shown in words. Email and role stay admin-managed.
 */
@Component({
  selector: 'lpg-profile',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    ButtonDirective,
    InputText,
    Message,
    HeaderTitlePortalDirective,
    PageHeaderComponent,
    SectionCardComponent,
    DetailListComponent,
    DetailItemComponent,
    FormFieldComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="profile-page">
      <div class="page-header">
        <ng-template lpgHeaderTitlePortal>
          <lpg-page-header
            title="My Profile"
            subtitle="Your account details. Ask an administrator to change your email or role."
          />
        </ng-template>
      </div>

      <lpg-section-card class="profile-card" heading="Account">
        <lpg-detail-list>
          <lpg-detail-item label="Email address">{{ email() || 'Not set' }}</lpg-detail-item>
          <lpg-detail-item label="Role">{{ role() }}</lpg-detail-item>
        </lpg-detail-list>
      </lpg-section-card>

      <lpg-section-card class="profile-card" heading="Your details">
        <form [formGroup]="detailsForm" (ngSubmit)="saveDetails()" novalidate class="profile-form">
          <lpg-form-field
            label="Full name"
            for="profile-name"
            [optional]="true"
            [control]="detailsForm.controls.displayName"
            [messages]="{ maxlength: 'Use 120 characters or fewer.' }"
          >
            <input
              pInputText
              id="profile-name"
              formControlName="displayName"
              autocomplete="name"
              [fluid]="true"
            />
          </lpg-form-field>
          <lpg-form-field
            label="Phone number"
            for="profile-phone"
            [optional]="true"
            [control]="detailsForm.controls.contactPhone"
            [messages]="{ pattern: 'Enter a phone number, for example +91 98490 12345.' }"
          >
            <input
              pInputText
              id="profile-phone"
              type="tel"
              formControlName="contactPhone"
              autocomplete="tel"
              [fluid]="true"
            />
          </lpg-form-field>
          <div class="modal-actions profile-form__actions">
            <button pButton type="submit" [disabled]="savingDetails() || detailsForm.pristine">
              {{ savingDetails() ? 'Saving…' : 'Save details' }}
            </button>
          </div>
        </form>
      </lpg-section-card>

      <lpg-section-card class="profile-card" heading="Change password">
        <form
          [formGroup]="passwordForm"
          (ngSubmit)="changePassword()"
          novalidate
          class="profile-form"
        >
          @if (passwordError(); as message) {
            <p-message severity="error">{{ message }}</p-message>
          }
          <lpg-form-field
            label="Current password"
            for="profile-current-password"
            [control]="passwordForm.controls.currentPassword"
            [messages]="{ required: 'Enter your current password.' }"
          >
            <input
              pInputText
              id="profile-current-password"
              type="password"
              formControlName="currentPassword"
              autocomplete="current-password"
              [fluid]="true"
            />
          </lpg-form-field>
          <lpg-form-field
            label="New password"
            for="profile-new-password"
            hint="At least 12 characters."
            [control]="passwordForm.controls.newPassword"
            [messages]="{
              required: 'Choose a new password.',
              minlength: 'Use at least 12 characters.',
            }"
          >
            <input
              pInputText
              id="profile-new-password"
              type="password"
              formControlName="newPassword"
              autocomplete="new-password"
              [fluid]="true"
            />
          </lpg-form-field>
          <lpg-form-field
            label="Confirm new password"
            for="profile-confirm-password"
            [control]="passwordForm.controls.confirmPassword"
            [messages]="{ required: 'Confirm the new password.' }"
          >
            <input
              pInputText
              id="profile-confirm-password"
              type="password"
              formControlName="confirmPassword"
              autocomplete="new-password"
              [fluid]="true"
            />
          </lpg-form-field>
          @if (passwordMismatch()) {
            <p class="profile-form__error" role="alert">Passwords do not match.</p>
          }
          <div class="modal-actions profile-form__actions">
            <button pButton type="submit" [disabled]="changingPassword()">
              {{ changingPassword() ? 'Updating…' : 'Update password' }}
            </button>
          </div>
        </form>
      </lpg-section-card>
    </div>
  `,
  styles: [
    `
      /* No top margin: the title lives in the shell's top bar, so the first
         card lines up with the Settings nav beside it. */
      .profile-page {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-lg);
      }

      .profile-card {
        inline-size: 100%;
        max-inline-size: none;
      }

      .profile-form {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-md);
      }

      .profile-form__actions {
        display: flex;
        justify-content: flex-end;
        gap: var(--spacing-sm);
        margin-inline: calc(-1 * var(--component-card-padding));
        margin-block-end: calc(-1 * var(--component-card-padding));
        padding-inline: var(--component-card-padding);
        padding-block: var(--spacing-md);
        border-block-start: var(--border-width) solid var(--color-border-default);
        border-bottom-left-radius: var(--radius-card);
        border-bottom-right-radius: var(--radius-card);
      }

      .profile-form__error {
        margin: 0;
        font-size: var(--typography-caption-font-size);
        color: var(--color-status-danger);
      }
    `,
  ],
})
export class Profile {
  private readonly authService = inject(AuthService);
  private readonly profileService = inject(MyProfileService);
  private readonly notify = inject(NotifyService);
  private readonly formBuilder = inject(NonNullableFormBuilder);

  protected readonly email = computed(() => this.authService.principal()?.email ?? null);
  protected readonly role = computed(() => {
    const role = this.authService.principal()?.role;
    return role ? roleLabel(role) : 'Not assigned';
  });

  protected readonly savingDetails = signal(false);
  protected readonly changingPassword = signal(false);
  protected readonly passwordError = signal<string | null>(null);

  protected readonly detailsForm = this.formBuilder.group({
    displayName: ['', [Validators.maxLength(120)]],
    contactPhone: ['', [Validators.pattern(PHONE_PATTERN)]],
  });

  protected readonly passwordForm = this.formBuilder.group(
    {
      currentPassword: ['', [Validators.required]],
      newPassword: ['', [Validators.required, Validators.minLength(MIN_PASSWORD_LENGTH)]],
      confirmPassword: ['', [Validators.required]],
    },
    { validators: passwordsMatch },
  );

  constructor() {
    this.profileService.getProfile().subscribe({
      next: (profile) =>
        this.detailsForm.reset({
          displayName: profile.display_name ?? '',
          contactPhone: profile.contact_phone ?? '',
        }),
      error: () => this.notify.error('Could not load your profile details.'),
    });
  }

  protected passwordMismatch(): boolean {
    return (
      this.passwordForm.hasError('passwordMismatch') &&
      this.passwordForm.controls.confirmPassword.touched
    );
  }

  protected saveDetails(): void {
    if (this.savingDetails()) return;
    if (this.detailsForm.invalid) {
      this.detailsForm.markAllAsTouched();
      return;
    }
    const { displayName, contactPhone } = this.detailsForm.getRawValue();
    this.savingDetails.set(true);
    this.profileService
      .updateProfile({
        display_name: displayName.trim() || null,
        contact_phone: contactPhone.trim() || null,
      })
      .subscribe({
        next: (profile) => {
          this.savingDetails.set(false);
          this.detailsForm.reset({
            displayName: profile.display_name ?? '',
            contactPhone: profile.contact_phone ?? '',
          });
          this.notify.success('Your details were saved.');
        },
        error: (error: unknown) => {
          this.savingDetails.set(false);
          this.notify.error(errorMessageFor(error, 'Could not save your details.'));
        },
      });
  }

  protected changePassword(): void {
    if (this.changingPassword()) return;
    if (this.passwordForm.invalid) {
      this.passwordForm.markAllAsTouched();
      return;
    }
    const { currentPassword, newPassword } = this.passwordForm.getRawValue();
    this.changingPassword.set(true);
    this.passwordError.set(null);
    this.profileService.changePassword(currentPassword, newPassword).subscribe({
      next: () => {
        this.changingPassword.set(false);
        this.passwordForm.reset();
        this.notify.success('Your password was updated.');
      },
      error: (error: unknown) => {
        this.changingPassword.set(false);
        const wrongCurrent = isAppError(error) && !!error.fieldErrors?.['current_password'];
        this.passwordError.set(
          wrongCurrent
            ? 'Your current password is not correct.'
            : errorMessageFor(error, 'Could not update your password.'),
        );
      },
    });
  }
}
