import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { ButtonDirective } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Password } from 'primeng/password';
import { Message } from 'primeng/message';
import { AuthService, type AppError } from '@lpg/shared/data-access';

function isAppError(value: unknown): value is AppError {
  return typeof value === 'object' && value !== null && 'errorCode' in value;
}

function errorMessageFor(error: unknown): string {
  switch (isAppError(error) ? error.errorCode : null) {
    case 'INVALID_CREDENTIALS':
      return 'Incorrect email or password.';
    case 'ACCOUNT_LOCKED':
      return 'This account is temporarily locked after too many failed attempts. Try again later.';
    default:
      return 'Something went wrong signing in. Please try again.';
  }
}

/**
 * Staff password login — Dashboard users primarily authenticate this way
 * (OTP login is the Customer/Driver mobile path, `mobile/packages/auth`).
 *
 * First use of Reactive Forms in this codebase (`06-authentication-
 * authorization` PLAN, Frontend Patterns): validated, submit-disabled-while-
 * pending, server errors surfaced via `p-message` rather than a raw
 * `AppError` dump.
 */
@Component({
  selector: 'lpg-login-page',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink, ButtonDirective, InputText, Password, Message],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="login-page">
      <form class="login-card" [formGroup]="form" (ngSubmit)="submit()" novalidate>
        <div class="login-card__header">
          <h1 class="login-card__title">Sign in</h1>
          <p class="login-card__lede">LPG Agency Management Platform</p>
        </div>

        @if (errorMessage(); as message) {
          <p-message severity="error">{{ message }}</p-message>
        }

        <div class="login-card__body">
          <div class="form-group">
            <label for="login-email">Email</label>
            <input
              pInputText
              id="login-email"
              type="email"
              formControlName="email"
              autocomplete="username"
              [attr.aria-invalid]="emailInvalid()"
            />
            @if (emailInvalid()) {
              <span class="field-error">Enter a valid email address.</span>
            }
          </div>

          <div class="form-group">
            <label for="login-password">Password</label>
            <p-password
              inputId="login-password"
              formControlName="password"
              [toggleMask]="true"
              [feedback]="false"
              autocomplete="current-password"
              [inputStyle]="{ width: '100%' }"
              [attr.aria-invalid]="passwordInvalid()"
            />
            @if (passwordInvalid()) {
              <span class="field-error">Password is required.</span>
            }
          </div>
        </div>

        <div class="login-card__footer">
          <button pButton type="submit" [disabled]="submitting()" class="login-card__submit">
            {{ submitting() ? 'Signing in…' : 'Sign in' }}
          </button>
          <a class="login-card__forgot" routerLink="/login/forgot-password">Forgot your password?</a>
        </div>
      </form>
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
      }

      .login-card__footer {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-md);
        margin-block-start: var(--spacing-sm);
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
      }

      .login-card__forgot:hover {
        text-decoration: underline;
      }
    `,
  ],
})
export class LoginPage {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  protected readonly submitting = signal(false);
  protected readonly errorMessage = signal<string | null>(null);

  protected readonly form = this.formBuilder.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(12)]],
  });

  protected emailInvalid(): boolean {
    const control = this.form.controls.email;
    return control.invalid && (control.dirty || control.touched);
  }

  protected passwordInvalid(): boolean {
    const control = this.form.controls.password;
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
    this.errorMessage.set(null);
    const { email, password } = this.form.getRawValue();

    this.authService.login(email, password).subscribe({
      next: () => {
        const redirectTo = this.route.snapshot.queryParamMap.get('redirectTo') ?? '/';
        void this.router.navigateByUrl(redirectTo);
      },
      error: (error: unknown) => {
        this.submitting.set(false);
        this.errorMessage.set(errorMessageFor(error));
      },
    });
  }
}
