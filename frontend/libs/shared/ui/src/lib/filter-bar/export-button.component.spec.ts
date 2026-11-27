import { TestBed } from '@angular/core/testing';
import { ExportButtonComponent } from './export-button.component';

describe('ExportButtonComponent', () => {
  async function render(inputs: { label?: string; disabled?: boolean } = {}) {
    const fixture = TestBed.createComponent(ExportButtonComponent);
    for (const [name, value] of Object.entries(inputs)) {
      fixture.componentRef.setInput(name, value);
    }
    const exported = jest.fn();
    fixture.componentInstance.export.subscribe(exported);
    await fixture.whenStable();
    const button = fixture.nativeElement.querySelector('button') as HTMLButtonElement;
    return { button, exported };
  }

  it('says what it does, in words', async () => {
    const { button, exported } = await render();

    expect(button.textContent?.trim()).toBe('Export CSV');
    button.click();
    expect(exported).toHaveBeenCalledTimes(1);
  });

  it('shows the wording a list asks for', async () => {
    const { button } = await render({ label: 'Export page as CSV' });

    expect(button.textContent?.trim()).toBe('Export page as CSV');
  });

  it('does nothing while there is nothing to download', async () => {
    const { button, exported } = await render({ disabled: true });

    button.click();

    expect(button.disabled).toBe(true);
    expect(exported).not.toHaveBeenCalled();
  });
});
