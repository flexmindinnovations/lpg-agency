import { ChangeDetectionStrategy, Component, inject, signal, viewChild } from '@angular/core';
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
        <div class="login-card__footer">
          <a class="login-card__forgot" routerLink="/login">Back to sign in</a>
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
              <div class="password-field">
                <p-floatlabel variant="on" class="login-card__float-label">
                  <input
                    #newPasswordInput
                    pInputPassword
                    id="reset-new-password"
                    type="password"
                    formControlName="newPassword"
                    autocomplete="new-password"
                    class="login-card__input password-field__input"
                  />
                  <label for="reset-new-password">New password</label>
                </p-floatlabel>
                <button
                  type="button"
                  class="password-field__toggle"
                  tabindex="-1"
                  (click)="toggleNewPasswordVisibility()"
                  [attr.aria-label]="newPasswordVisible() ? 'Hide password' : 'Show password'"
                >
                  <i
                    class="pi"
                    [class.pi-eye]="!newPasswordVisible()"
                    [class.pi-eye-slash]="newPasswordVisible()"
                  ></i>
                </button>
              </div>
            </div>

            <div class="form-group">
              <div class="password-field">
                <p-floatlabel variant="on" class="login-card__float-label">
                  <input
                    #confirmPasswordInput
                    pInputPassword
                    id="reset-confirm-password"
                    type="password"
                    formControlName="confirmPassword"
                    autocomplete="new-password"
                    class="login-card__input password-field__input"
                  />
                  <label for="reset-confirm-password">Confirm new password</label>
                </p-floatlabel>
                <button
                  type="button"
                  class="password-field__toggle"
                  tabindex="-1"
                  (click)="toggleConfirmPasswordVisibility()"
                  [attr.aria-label]="confirmPasswordVisible() ? 'Hide password' : 'Show password'"
                >
                  <i
                    class="pi"
                    [class.pi-eye]="!confirmPasswordVisible()"
                    [class.pi-eye-slash]="confirmPasswordVisible()"
                  ></i>
                </button>
              </div>
              @if (mismatch()) {
                <span class="field-error">Passwords do not match.</span>
              }
            </div>
          </div>

          <div class="login-card__footer">
            <button pButton type="submit" [disabled]="submitting()" class="login-card__submit">
              {{ submitting() ? 'Saving…' : 'Save new password' }}
            </button>
            <a class="login-card__forgot" routerLink="/login">Back to sign in</a>
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

      p-message {
        display: block;
        margin-block-end: var(--spacing-lg);
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

      .password-field {
        position: relative;
      }

      .password-field__input {
        padding-inline-end: 2.5rem;
      }

      .password-field__toggle {
        position: absolute;
        inset-inline-end: var(--spacing-sm);
        top: 50%;
        transform: translateY(-50%);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background: none;
        border: none;
        padding: 0;
        color: var(--color-text-secondary);
        cursor: pointer;
        z-index: 1;
      }

      .password-field__toggle:hover {
        color: var(--color-text-primary);
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

      .login-card__forgot {
        align-self: center;
        color: var(--color-action-primary);
        font-size: var(--typography-body-small-font-size);
        text-decoration: none;
        font-weight: var(--typography-label-font-weight);
      }

      .login-card__forgot:hover {
        text-decoration: underline;
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

  // `pInputPassword` is a bare directive with no `exportAs`, so a template
  // reference variable (`#ref`) resolves to the native element —
  // `read: InputPassword` is what actually gets the directive instance
  // (and its `mask`/`toggleMask()` state) off that same element.
  private readonly newPasswordInput = viewChild('newPasswordInput', { read: InputPassword });
  private readonly confirmPasswordInput = viewChild('confirmPasswordInput', { read: InputPassword });

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

  protected newPasswordVisible(): boolean {
    return this.newPasswordInput()?.mask() === false;
  }

  protected toggleNewPasswordVisibility(): void {
    this.newPasswordInput()?.toggleMask();
  }

  protected confirmPasswordVisible(): boolean {
    return this.confirmPasswordInput()?.mask() === false;
  }

  protected toggleConfirmPasswordVisibility(): void {
    this.confirmPasswordInput()?.toggleMask();
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
