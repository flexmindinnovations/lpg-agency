import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import {
  AbstractControl,
  NonNullableFormBuilder,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { ButtonDirective } from 'primeng/button';
import { Password } from 'primeng/password';
import { Message } from 'primeng/message';
import { AuthService, type AppError } from '@lpg/shared/data-access';

function isAppError(value: unknown): value is AppError {
  return typeof value === 'object' && value !== null && 'errorCode' in value;
}

function errorMessageFor(error: unknown): string {
  switch (isAppError(error) ? error.errorCode : null) {
    case 'RESET_TOKEN_EXPIRED':
      return 'This reset link has expired or was already used. Request a new one.';
    case 'WEAK_PASSWORD':
      return 'Choose a longer password (at least 12 characters).';
    default:
      return 'Something went wrong resetting your password. Please try again.';
  }
}

function passwordsMatchValidator(group: AbstractControl): ValidationErrors | null {
  const password = group.get('newPassword')?.value;
  const confirmation = group.get('confirmPassword')?.value;
  return password === confirmation ? null : { passwordMismatch: true };
}

/**
 * Confirms a password reset — `reset_token` arrives as a query param on the
 * link `RequestPasswordResetUseCase` emails
 * (`application/identity/password_reset.py`'s `body` string).
 */
@Component({
  selector: 'lpg-reset-password-page',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink, ButtonDirective, Password, Message],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="login-page">
      <div class="login-card">
        @if (!resetToken()) {
          <h1 class="login-card__title">Invalid link</h1>
          <p class="login-card__lede">
            This password reset link is missing its token. Request a new one.
          </p>
        } @else if (succeeded()) {
          <h1 class="login-card__title">Password updated</h1>
          <p class="login-card__lede">Your password has been reset.</p>
          <a class="login-card__submit-link" routerLink="/login">Continue to sign in</a>
        } @else {
          <form [formGroup]="form" (ngSubmit)="submit()" novalidate>
            <h1 class="login-card__title">Choose a new password</h1>

            @if (errorMessage(); as message) {
              <p-message severity="error">{{ message }}</p-message>
            }

            <div class="login-field">
              <label for="reset-new-password">New password</label>
              <p-password
                inputId="reset-new-password"
                formControlName="newPassword"
                [toggleMask]="true"
                autocomplete="new-password"
                [inputStyle]="{ width: '100%' }"
              />
            </div>

            <div class="login-field">
              <label for="reset-confirm-password">Confirm new password</label>
              <p-password
                inputId="reset-confirm-password"
                formControlName="confirmPassword"
                [toggleMask]="true"
                [feedback]="false"
                autocomplete="new-password"
                [inputStyle]="{ width: '100%' }"
              />
              @if (mismatch()) {
                <span class="login-field__error">Passwords do not match.</span>
              }
            </div>

            <button pButton type="submit" [disabled]="submitting()" class="login-card__submit">
              {{ submitting() ? 'Saving…' : 'Save new password' }}
            </button>
          </form>
        }
      </div>
    </div>
  `,
  styles: [
    `
      .login-page {
        display: flex;
        align-items: center;
        justify-content: center;
        min-block-size: 100vh;
        padding: var(--spacing-lg);
        background: var(--color-surface-base);
      }

      .login-card {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-md);
        inline-size: 100%;
        max-inline-size: 24rem;
        padding: var(--spacing-xl);
        background: var(--color-surface-raised);
        border: var(--border-width) solid var(--color-border-default);
        border-radius: var(--radius-md);
      }

      .login-card__title {
        margin: 0;
        font-size: var(--typography-heading1-font-size);
        font-weight: var(--typography-heading1-font-weight);
      }

      .login-card__lede {
        margin: 0;
        color: var(--color-text-secondary);
      }

      .login-field {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-xs);
        margin-bottom: var(--spacing-md);
      }

      .login-field label {
        font-weight: var(--typography-label-font-weight);
      }

      .login-field__error {
        color: var(--color-status-danger-text, var(--color-text-danger, #b91c1c));
        font-size: var(--typography-caption-font-size);
      }

      .login-card__submit {
        margin-top: var(--spacing-sm);
      }

      .login-card__submit-link {
        align-self: center;
        color: var(--color-action-primary);
      }
    `,
  ],
})
export class ResetPasswordPage {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly authService = inject(AuthService);
  private readonly route = inject(ActivatedRoute);

  protected readonly submitting = signal(false);
  protected readonly succeeded = signal(false);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly resetToken = signal(this.route.snapshot.queryParamMap.get('token'));

  protected readonly form = this.formBuilder.group(
    {
      newPassword: ['', [Validators.required, Validators.minLength(12)]],
      confirmPassword: ['', [Validators.required]],
    },
    { validators: passwordsMatchValidator },
  );

  protected mismatch(): boolean {
    return this.form.hasError('passwordMismatch') && this.form.controls.confirmPassword.touched;
  }

  protected submit(): void {
    const token = this.resetToken();
    if (this.submitting() || !token) {
      return;
    }
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    this.submitting.set(true);
    this.errorMessage.set(null);
    const { newPassword } = this.form.getRawValue();

    this.authService.confirmPasswordReset(token, newPassword).subscribe({
      next: () => {
        this.submitting.set(false);
        this.succeeded.set(true);
      },
      error: (error: unknown) => {
        this.submitting.set(false);
        this.errorMessage.set(errorMessageFor(error));
      },
    });
  }
}
