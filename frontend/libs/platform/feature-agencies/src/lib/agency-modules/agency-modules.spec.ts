import { TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { MessageService } from 'primeng/api';
import { AgencyService, type ModuleResponse } from '@lpg/shared/data-access';
import { AgencyModules } from './agency-modules';

const moduleOf = (key: string, enabled: boolean): ModuleResponse => ({
  key,
  label: key,
  description: `${key} description`,
  group: 'Operations',
  requires: [],
  enabled,
});

describe('AgencyModules', () => {
  const render = async (listModules: jest.Mock) => {
    await TestBed.configureTestingModule({
      imports: [AgencyModules],
      providers: [{ provide: AgencyService, useValue: { listModules } }, MessageService],
    }).compileComponents();

    const fixture = TestBed.createComponent(AgencyModules);
    fixture.componentRef.setInput('tenantId', 't-1');
    fixture.componentRef.setInput('agencyName', 'Orient LPG Agency');
    fixture.detectChanges();
    return fixture;
  };

  const modules = jest.fn(() => of([moduleOf('orders', true), moduleOf('scales', false)]));

  it('shows only a summary until the dialog is opened', async () => {
    const fixture = await render(modules);
    const element = fixture.nativeElement as HTMLElement;

    expect(element.textContent).toContain('1 of 2 on');
    expect(element.textContent).toContain('Manage modules');
    expect(document.querySelector('.p-dialog')).toBeNull();
  });

  it('opens a dialog listing every module', async () => {
    const fixture = await render(modules);

    (fixture.nativeElement as HTMLElement).querySelector('button')?.click();
    fixture.detectChanges();
    await fixture.whenStable();

    const dialog = document.querySelector('.p-dialog');
    expect(dialog?.textContent).toContain('Modules · Orient LPG Agency');
    expect(dialog?.querySelectorAll('.module')).toHaveLength(2);
  });

  it('says so and keeps the button disabled when the modules cannot be loaded', async () => {
    const fixture = await render(jest.fn(() => throwError(() => new Error('boom'))));
    const element = fixture.nativeElement as HTMLElement;

    expect(element.textContent).toContain('Modules could not be loaded.');
    expect(element.querySelector('button')?.disabled).toBe(true);
  });
});
