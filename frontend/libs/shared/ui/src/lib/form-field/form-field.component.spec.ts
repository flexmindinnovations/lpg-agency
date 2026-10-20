import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { FormFieldComponent, validateForSubmit } from './form-field.component';

@Component({
  standalone: true,
  imports: [FormFieldComponent, ReactiveFormsModule],
  template: `
    <form [formGroup]="form" (ngSubmit)="submitted = true">
      <lpg-form-field label="Code" for="code" [control]="form.controls.code">
        <input id="code" formControlName="code" />
      </lpg-form-field>
      <button type="submit">Save</button>
    </form>
  `,
})
class FormHostComponent {
  form = new FormGroup({ code: new FormControl('', { validators: [Validators.required] }) });
  submitted = false;
}

@Component({
  standalone: true,
  imports: [FormFieldComponent, ReactiveFormsModule],
  template: `
    <lpg-form-field
      label="First name"
      for="fn"
      [control]="ctrl"
      hint="As on their ID"
      [messages]="{ required: 'First name is required' }"
    >
      <input id="fn" [formControl]="ctrl" />
    </lpg-form-field>
  `,
})
class HostComponent {
  ctrl = new FormControl('', { validators: [Validators.required] });
}

describe('FormFieldComponent', () => {
  function render() {
    const fixture = TestBed.createComponent(HostComponent);
    fixture.detectChanges();
    return fixture;
  }

  it('renders the label, an asterisk for a required control, and the hint', () => {
    const el = render().nativeElement as HTMLElement;
    expect(el.querySelector('label')?.textContent).toContain('First name');
    expect(el.querySelector('.lpg-field__req')).not.toBeNull();
    expect(el.querySelector('.lpg-field__hint')?.textContent).toContain('As on their ID');
  });

  it('hides the error until the control is touched, then shows message + icon', () => {
    const fixture = render();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.lpg-field__error')).toBeNull();

    fixture.componentInstance.ctrl.markAsTouched();
    fixture.detectChanges();

    const err = el.querySelector('.lpg-field__error');
    expect(err?.textContent).toContain('First name is required');
    expect(err?.querySelector('i.pi-exclamation-circle')).not.toBeNull();
    expect(el.querySelector('.lpg-field__hint')).toBeNull();
  });

  it('links the label to the control via `for`', () => {
    const el = render().nativeElement as HTMLElement;
    expect(el.querySelector('label')?.getAttribute('for')).toBe('fn');
  });

  it('falls back to a generic message for an unmapped validator key', () => {
    const fixture = render();
    fixture.componentInstance.ctrl.setValidators([Validators.minLength(5)]);
    fixture.componentInstance.ctrl.setValue('ab');
    fixture.componentInstance.ctrl.markAsDirty();
    fixture.detectChanges();
    expect(
      (fixture.nativeElement as HTMLElement).querySelector('.lpg-field__error')?.textContent,
    ).toContain('too short');
  });

  it('shows every message once the form is submitted, and marks the control invalid', () => {
    const fixture = TestBed.createComponent(FormHostComponent);
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.lpg-field__error')).toBeNull();

    (el.querySelector('button') as HTMLButtonElement).click();
    fixture.detectChanges();
    TestBed.tick();

    expect(el.querySelector('.lpg-field__error')?.textContent).toContain('required');
    const input = el.querySelector('#code') as HTMLInputElement;
    expect(input.getAttribute('aria-invalid')).toBe('true');
    expect(input.getAttribute('aria-describedby')).toBe('code-error');
  });

  it('validateForSubmit marks an invalid form touched and reports it', () => {
    const form = new FormGroup({ a: new FormControl('', { validators: [Validators.required] }) });
    expect(validateForSubmit(form)).toBe(false);
    expect(form.controls.a.touched).toBe(true);
    form.controls.a.setValue('x');
    expect(validateForSubmit(form)).toBe(true);
  });
});
