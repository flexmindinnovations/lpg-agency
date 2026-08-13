import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ButtonDirective } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { AuthService } from '@lpg/shared/data-access';

/**
 * Requests a password-reset email. Always shows the same success state
 * regardless of whether the address matches an account
 * (`RequestPasswordResetUseCase`'s module docstring: no user-enumeration
 * through response shape) — so this page has no error state of its own to
 * render, only pending vs. submitted.
 */
@Component({
  selector: 'lpg-forgot-password-page',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink, ButtonDirective, InputText],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="login-page">
      <div class="login-card">
        @if (submitted()) {
          <div class="login-card__header">
            <h1 class="login-card__title">Check your email</h1>
            <p class="login-card__lede">
              If an account exists for that address, we've sent a link to reset the password.
            </p>
          </div>
        } @else {
          <form [formGroup]="form" (ngSubmit)="submit()" novalidate>
            <div class="login-card__header">
              <h1 class="login-card__title">Reset your password</h1>
              <p class="login-card__lede">
                Enter your email and we'll send you a link to reset your password.
              </p>
            </div>

            <div class="login-card__body">
              <div class="form-group">
                <label for="forgot-email">Email</label>
                <input
                  pInputText
                  id="forgot-email"
                  type="email"
                  formControlName="email"
                  autocomplete="username"
                  [attr.aria-invalid]="emailInvalid()"
                />
                @if (emailInvalid()) {
                  <span class="field-error">Enter a valid email address.</span>
                }
              </div>
            </div>

            <div class="login-card__footer">
              <button pButton type="submit" [disabled]="submitting()" class="login-card__submit">
                {{ submitting() ? 'Sending…' : 'Send reset link' }}
              </button>
            </div>
          </form>
        }

        <a class="login-card__forgot" routerLink="/login">Back to sign in</a>
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
        background: var(--color-surface-sunken);
      }

      .login-card {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-lg);
        inline-size: 100%;
        max-inline-size: 26rem;
        padding: var(--spacing-xl);
        background: var(--color-surface-base);
        border: var(--border-width) solid var(--color-border-default);
        border-radius: var(--radius-xl);
        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
      }

      .login-card__header {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-xs);
        text-align: center;
      }

      .login-card__title {
        margin: 0;
        font-size: var(--typography-heading1-font-size);
        font-weight: var(--typography-heading1-font-weight);
        letter-spacing: -0.025em;
      }

      .login-card__lede {
        margin: 0;
        color: var(--color-text-secondary);
        font-size: var(--typography-body-small-font-size);
      }

      .login-card__body {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-md);
        margin-block-start: var(--spacing-lg);
      }

      .login-card__footer {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-md);
        margin-block-start: var(--spacing-lg);
      }

      .login-card__submit {
        width: 100%;
      }

      .login-card__forgot {
        align-self: center;
        color: var(--color-action-primary);
        font-size: var(--typography-body-small-font-size);
        text-decoration: none;
        font-weight: var(--typography-label-font-weight);
        margin-block-start: var(--spacing-md);
      }

      .login-card__forgot:hover {
        text-decoration: underline;
      }
    `,
  ],
})
export class ForgotPasswordPage {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly authService = inject(AuthService);

  protected readonly submitting = signal(false);
  protected readonly submitted = signal(false);

  protected readonly form = this.formBuilder.group({
    email: ['', [Validators.required, Validators.email]],
  });

  protected emailInvalid(): boolean {
    const control = this.form.controls.email;
    return control.invalid && (control.dirty || control.touched);
  }

  protected submit(): void {
    if (this.submitting()) {
      return;
    }
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    this.submitting.set(true);
    const { email } = this.form.getRawValue();

    this.authService.requestPasswordReset(email).subscribe({
      next: () => {
        this.submitting.set(false);
        this.submitted.set(true);
      },
      error: () => {
        // Request-reset never surfaces a distinguishing error (no
        // enumeration) — treat any transport failure as "try again" by
        // simply resetting the pending state.
        this.submitting.set(false);
      },
    });
  }
}
