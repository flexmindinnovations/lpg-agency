import { TestBed } from '@angular/core/testing';
import { Subject, of, throwError } from 'rxjs';
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
  const render = async (listModules: jest.Mock, setModules = jest.fn()) => {
    await TestBed.configureTestingModule({
      imports: [AgencyModules],
      providers: [
        { provide: AgencyService, useValue: { listModules, setModules } },
        MessageService,
      ],
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

  describe('saving', () => {
    /** Dispatch needs Orders; nothing needs Scales. */
    const three = () =>
      of([
        moduleOf('orders', false),
        { ...moduleOf('dispatch', false), requires: ['orders'] },
        moduleOf('scales', false),
      ]);

    /** Opens the dialog, with each save held until the test answers it. */
    const open = async (readonly = false) => {
      const requests: Subject<void>[] = [];
      const save = jest.fn(() => {
        const request = new Subject<void>();
        requests.push(request);
        return request;
      });
      const fixture = await render(jest.fn(three), save);
      fixture.componentRef.setInput('readonly', readonly);
      const settle = async () => {
        fixture.detectChanges();
        await fixture.whenStable();
        fixture.detectChanges();
      };
      await settle();
      const openDialog = async () => {
        (fixture.nativeElement as HTMLElement).querySelector('button')?.click();
        await settle();
      };
      await openDialog();

      const summary = () =>
        (fixture.nativeElement as HTMLElement)
          .querySelector('.summary__status')
          ?.textContent?.trim();
      const dialog = () => document.querySelector('.p-dialog');
      const text = () => dialog()?.textContent?.replace(/\s+/g, ' ');
      const switchFor = (name: string) =>
        dialog()?.querySelector<HTMLInputElement>(`input[aria-label="${name}"]`);
      const master = () => dialog()?.querySelector<HTMLInputElement>('#agency-modules-all');
      const button = (label: string) =>
        Array.from(dialog()?.querySelectorAll('button') ?? []).find(
          (b) => b.textContent?.trim() === label,
        );
      const click = async (target: HTMLElement | null | undefined) => {
        expect(target).toBeTruthy();
        target?.click();
        await settle();
      };
      const answer = async (accepted = true) => {
        const request = requests[requests.length - 1];
        if (accepted) {
          request.next();
          request.complete();
        } else {
          request.error(new Error('refused'));
        }
        await settle();
      };
      return {
        save,
        openDialog,
        summary,
        dialog,
        text,
        switchFor,
        master,
        button,
        click,
        answer,
      };
    };

    afterEach(() => document.querySelectorAll('.p-dialog-mask').forEach((el) => el.remove()));

    it('saves nothing until Save is pressed', async () => {
      const { save, summary, text, switchFor, button, click } = await open();
      expect(button('Save changes')?.disabled).toBe(true);

      await click(switchFor('scales'));

      expect(save).not.toHaveBeenCalled();
      expect(text()).toContain('1 unsaved change');
      expect(button('Save changes')?.disabled).toBe(false);
      expect(summary()).toBe('0 of 3 on');
    });

    it('sends every change in one request', async () => {
      const { save, summary, switchFor, button, click, answer } = await open();

      await click(switchFor('orders'));
      await click(switchFor('dispatch'));
      await click(switchFor('scales'));
      await click(button('Save changes'));
      await answer();

      expect(save).toHaveBeenCalledTimes(1);
      expect(save).toHaveBeenCalledWith('t-1', { orders: true, dispatch: true, scales: true });
      expect(summary()).toBe('3 of 3 on');
    });

    it('does not count a switch that was put back', async () => {
      const { text, switchFor, button, click } = await open();

      await click(switchFor('scales'));
      await click(switchFor('scales'));

      expect(text()).not.toContain('unsaved');
      expect(button('Save changes')?.disabled).toBe(true);
    });

    it('drops unsaved changes on Cancel', async () => {
      const { save, openDialog, text, switchFor, button, click } = await open();
      await click(switchFor('scales'));

      await click(button('Cancel'));
      await openDialog();

      expect(save).not.toHaveBeenCalled();
      expect(switchFor('scales')?.checked).toBe(false);
      expect(text()).not.toContain('unsaved');
    });

    it('keeps the changes when the save is refused', async () => {
      const { summary, text, switchFor, button, click, answer } = await open();
      await click(switchFor('scales'));
      await click(button('Save changes'));

      await answer(false);

      expect(switchFor('scales')?.checked).toBe(true);
      expect(text()).toContain('1 unsaved change');
      expect(button('Save changes')?.disabled).toBe(false);
      expect(summary()).toBe('0 of 3 on');
    });

    it('blocks edits while saving without disabling the switches', async () => {
      const { dialog, switchFor, button, click } = await open();
      await click(switchFor('scales'));

      await click(button('Save changes'));

      expect(dialog()?.querySelector('[inert] .grid')).not.toBeNull();
      expect(switchFor('scales')?.disabled).toBe(false);
      expect(button('Cancel')?.disabled).toBe(true);
    });

    it('shows the same dependency notes whatever is switched on', async () => {
      const { dialog, switchFor, master, click } = await open();
      const notes = () =>
        Array.from(dialog()?.querySelectorAll('.module__note') ?? []).map((n) =>
          n.textContent?.trim(),
        );
      const before = notes();
      expect(before).toEqual(['Needed by dispatch.', 'Needs orders.']);

      await click(switchFor('orders'));
      expect(notes()).toEqual(before);
      await click(master());
      expect(notes()).toEqual(before);
    });

    const closeButton = () =>
      document.querySelector<HTMLButtonElement>('.p-dialog .p-dialog-close-button');

    it('keeps the close button while saving', async () => {
      const { switchFor, button, click } = await open();
      await click(switchFor('scales'));

      await click(button('Save changes'));

      expect(closeButton()).toBeTruthy();
    });

    it('still finishes a save when the dialog is closed during it', async () => {
      const { summary, switchFor, button, click, answer } = await open();
      await click(switchFor('scales'));
      await click(button('Save changes'));

      await click(closeButton());
      await answer();

      expect(summary()).toBe('1 of 3 on');
    });

    it('drops the changes if a save is refused after the dialog was closed', async () => {
      const { openDialog, text, switchFor, button, click, answer } = await open();
      await click(switchFor('scales'));
      await click(button('Save changes'));
      await click(closeButton());

      await answer(false);
      await openDialog();

      expect(switchFor('scales')?.checked).toBe(false);
      expect(text()).not.toContain('unsaved');
    });

    it('turns everything on and off from the "All modules" switch', async () => {
      const { save, switchFor, master, button, click } = await open();

      await click(master());
      for (const name of ['orders', 'dispatch', 'scales']) {
        expect(switchFor(name)?.checked).toBe(true);
      }

      await click(master());
      for (const name of ['orders', 'dispatch', 'scales']) {
        expect(switchFor(name)?.checked).toBe(false);
      }
      // Back where it started, so there is nothing to save.
      expect(button('Save changes')?.disabled).toBe(true);
      expect(save).not.toHaveBeenCalled();
    });

    it('offers no way to change a closed agency', async () => {
      const { master, button } = await open(true);

      expect(button('Close')).toBeTruthy();
      expect(button('Save changes')).toBeUndefined();
      expect(master()).toBeNull();
    });
  });
});
