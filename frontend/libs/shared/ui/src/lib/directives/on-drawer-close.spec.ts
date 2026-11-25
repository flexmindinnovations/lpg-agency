import { Component, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { Drawer } from 'primeng/drawer';
import { of } from 'rxjs';
import { DocumentUploadComponent } from '../document-upload/document-upload.component';

@Component({
  standalone: true,
  imports: [Drawer, DocumentUploadComponent],
  template: `
    <p-drawer [visible]="open()">
      <lpg-document-upload accept="image/*" [uploader]="uploader" (cleared)="cleared = true" />
    </p-drawer>
  `,
})
class DrawerHost {
  readonly open = signal(false);
  cleared = false;
  readonly uploader = () => of({ blobRef: 'blob-1' });
}

describe('onDrawerClose (through the upload box)', () => {
  it('forgets the chosen file when the surrounding drawer closes', async () => {
    TestBed.configureTestingModule({ providers: [provideNoopAnimations()] });
    const fixture = TestBed.createComponent(DrawerHost);
    const el = fixture.nativeElement as HTMLElement;
    const settle = async () => {
      fixture.detectChanges();
      await fixture.whenStable();
      fixture.detectChanges();
    };

    fixture.componentInstance.open.set(true);
    await settle();
    const input = el.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(['x'], 'licence.png', { type: 'image/png' });
    Object.defineProperty(input, 'files', { value: [file], configurable: true });
    URL.createObjectURL = jest.fn(() => 'blob:preview');
    URL.revokeObjectURL = jest.fn();
    input.dispatchEvent(new Event('change'));
    await settle();
    expect(el.textContent).toContain('licence.png');

    fixture.componentInstance.open.set(false);
    await settle();
    fixture.componentInstance.open.set(true);
    await settle();

    expect(el.textContent).not.toContain('licence.png');
    // Silent: the host resets its own form when it opens the drawer.
    expect(fixture.componentInstance.cleared).toBe(false);
  });
});
