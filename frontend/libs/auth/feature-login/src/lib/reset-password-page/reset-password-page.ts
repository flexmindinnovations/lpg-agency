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
import { FloatLabel } from 'primeng/floatlabel';
import { InputPassword } from 'primeng/inputpassword';
import { Message } from 'primeng/message';
import { AuthService, type AppError } from '@lpg/shared/data-access';
import { AuthShell } from '../auth-shell/auth-shell';

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
  imports: [
    ReactiveFormsModule,
    RouterLink,
    ButtonDirective,
    FloatLabel,
    InputPassword,
    Message,
    AuthShell,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <lpg-auth-shell>
      @if (!resetToken()) {
        <div class="login-card__header">
          <h1 class="login-card__title">Invalid link</h1>
          <p class="login-card__lede">
            This password reset link is missing its token. Request a new one.
          </p>
        </div>
      } @else if (succeeded()) {
        <div class="login-card__header">
          <h1 class="login-card__title">Password updated</h1>
          <p class="login-card__lede">Your password has been reset.</p>
        </div>
        <div class="login-card__footer">
          <a class="login-card__submit-link" routerLink="/login">Continue to sign in</a>
        </div>
      } @else {
        <form [formGroup]="form" (ngSubmit)="submit()" novalidate>
          <div class="login-card__header">
            <h1 class="login-card__title">Choose a new password</h1>
            <p class="login-card__lede">Use at least 12 characters.</p>
          </div>

          @if (errorMessage(); as message) {
            <p-message severity="error">{{ message }}</p-message>
          }

          <div class="login-card__body">
            <div class="form-group">
              <p-floatlabel variant="on" class="login-card__float-label">
                <input
                  pInputPassword
                  id="reset-new-password"
                  type="password"
                  formControlName="newPassword"
                  autocomplete="new-password"
                  class="login-card__input"
                />
                <label for="reset-new-password">New password</label>
              </p-floatlabel>
            </div>

            <div class="form-group">
              <p-floatlabel variant="on" class="login-card__float-label">
                <input
                  pInputPassword
                  id="reset-confirm-password"
                  type="password"
                  formControlName="confirmPassword"
                  autocomplete="new-password"
                  class="login-card__input"
                />
                <label for="reset-confirm-password">Confirm new password</label>
              </p-floatlabel>
              @if (mismatch()) {
                <span class="field-error">Passwords do not match.</span>
              }
            </div>
          </div>

          <div class="login-card__footer">
            <button pButton type="submit" [disabled]="submitting()" class="login-card__submit">
              {{ submitting() ? 'Saving…' : 'Save new password' }}
            </button>
          </div>
        </form>
      }
    </lpg-auth-shell>
  `,
  styles: [
    `
      .login-card__header {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-xs);
        margin-block-end: var(--spacing-xl);
      }

      .login-card__title {
        margin: 0;
        font-size: var(--typography-display-font-size);
        font-weight: var(--typography-display-font-weight);
        letter-spacing: -0.02em;
        color: var(--color-text-primary);
      }

      .login-card__lede {
        margin: 0;
        color: var(--color-text-secondary);
        font-size: var(--typography-body-font-size);
      }

      .login-card__body {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-md);
      }

      .login-card__float-label {
        display: block;
        inline-size: 100%;
      }

      .login-card__input {
        width: 100%;
      }

      .login-card__footer {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-md);
        margin-block-start: var(--spacing-xl);
      }

      .login-card__submit {
        width: 100%;
        transition: transform var(--motion-duration-micro) var(--motion-easing-standard);
      }

      .login-card__submit:active:not(:disabled) {
        transform: translateY(1px);
      }

      .login-card__submit-link {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 100%;
        padding: 0.625rem 1rem;
        background: var(--color-action-primary);
        color: var(--color-action-primary-text);
        border-radius: var(--component-button-radius);
        text-decoration: none;
        font-size: var(--typography-body-small-font-size);
        font-weight: var(--typography-label-font-weight);
        transition: background-color var(--motion-duration-small) var(--motion-easing-standard);
      }
      .login-card__submit-link:hover {
        background: var(--color-action-primary-hover);
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
