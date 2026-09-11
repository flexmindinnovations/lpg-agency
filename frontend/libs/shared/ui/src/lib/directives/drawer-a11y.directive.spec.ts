/* eslint-disable @angular-eslint/component-selector, @angular-eslint/no-output-on-prefix --
   the stub deliberately mirrors PrimeNG's `<p-drawer>` selector and its
   `onShow` / `onHide` output names so the directive's `@HostListener`
   bindings resolve against it. */
import { Component, EventEmitter, Output } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { DrawerA11yDirective } from './drawer-a11y.directive';

/**
 * Stands in for PrimeNG's `Drawer` — same selector, the two `@Output`s the
 * directive listens for, and the DOM shape it reads (`.p-drawer` panel with a
 * heading, a close button and `.p-drawer-content`).
 */
@Component({
  selector: 'p-drawer',
  standalone: true,
  template: `
    <div class="p-drawer" tabindex="0">
      <div class="p-drawer-header">
        <h2>Create Booking</h2>
        <button class="p-drawer-close-button" type="button">Close</button>
      </div>
      <div class="p-drawer-content"><ng-content /></div>
    </div>
  `,
})
class StubDrawerComponent {
  @Output() onShow = new EventEmitter<void>();
  @Output() onHide = new EventEmitter<void>();
  @Output() visibleChange = new EventEmitter<boolean>();
}

@Component({
  selector: 'p-dialog',
  standalone: true,
  template: '<ng-content />',
})
class StubDialogComponent {}

@Component({
  standalone: true,
  imports: [StubDrawerComponent, StubDialogComponent, DrawerA11yDirective],
  template: `
    <button id="trigger" type="button">Open</button>
    <div class="page-body"><a id="bg-link" href="#">background link</a></div>
    <p-drawer>
      <input id="first-field" />
      <button id="save" type="button">Save</button>
    </p-drawer>
    <p-dialog id="sibling-dialog"><button type="button">Action</button></p-dialog>
  `,
})
class HostComponent {}

describe('DrawerA11yDirective', () => {
  let rafSpy: ReturnType<typeof jest.spyOn>;
  const mounted: HTMLElement[] = [];

  beforeEach(() => {
    // Run the directive's rAF callback synchronously.
    rafSpy = jest
      .spyOn(window, 'requestAnimationFrame')
      .mockImplementation((cb: FrameRequestCallback) => {
        cb(0);
        return 0;
      });
  });

  afterEach(() => {
    rafSpy.mockRestore();
    while (mounted.length) mounted.pop()?.remove();
  });

  function setup() {
    const fixture = TestBed.createComponent(HostComponent);
    const root = fixture.nativeElement as HTMLElement;
    document.body.appendChild(root);
    mounted.push(root);
    fixture.detectChanges();
    const drawer = fixture.debugElement.children.find(
      (d) => d.componentInstance instanceof StubDrawerComponent,
    )?.componentInstance as StubDrawerComponent;
    const q = <T extends Element = HTMLElement>(sel: string): T => {
      const el = root.querySelector<T>(sel);
      if (!el) throw new Error(`missing element: ${sel}`);
      return el;
    };
    const isInert = (sel: string) => q(sel).hasAttribute('inert');
    return { fixture, root, drawer, q, isInert };
  }

  it('marks the panel as a modal dialog and labels it from the heading on open', () => {
    const { drawer, q } = setup();

    drawer.onShow.emit();

    const panel = q('.p-drawer');
    expect(panel.getAttribute('role')).toBe('dialog');
    expect(panel.getAttribute('aria-modal')).toBe('true');
    const headingId = q('.p-drawer h2').id;
    expect(headingId).toMatch(/^lpg-drawer-title-/);
    expect(panel.getAttribute('aria-labelledby')).toBe(headingId);
  });

  it('moves focus into the panel and inerts the background on open', () => {
    const { drawer, q, isInert } = setup();
    q('#trigger').focus();

    drawer.onShow.emit();

    expect(document.activeElement).toBe(q('#first-field'));
    expect(isInert('#trigger')).toBe(true);
    expect(isInert('.page-body')).toBe(true);
    expect(isInert('p-drawer')).toBe(false);
    expect(isInert('#sibling-dialog')).toBe(false);
  });

  it('clears inert and restores focus to the opener on close', () => {
    const { drawer, q, isInert } = setup();
    const trigger = q('#trigger');
    trigger.focus();
    drawer.onShow.emit();

    drawer.onHide.emit();

    expect(isInert('#trigger')).toBe(false);
    expect(isInert('.page-body')).toBe(false);
    expect(document.activeElement).toBe(trigger);
  });

  it('clears inert and restores focus when visibleChange emits false', () => {
    const { drawer, q, isInert } = setup();
    const trigger = q('#trigger');
    trigger.focus();
    drawer.onShow.emit();

    drawer.visibleChange.emit(false);

    expect(isInert('#trigger')).toBe(false);
    expect(isInert('.page-body')).toBe(false);
    expect(document.activeElement).toBe(trigger);
  });

  it('clears inert if the drawer is destroyed while open', () => {
    const { fixture, drawer, isInert } = setup();
    drawer.onShow.emit();
    expect(isInert('.page-body')).toBe(true);

    fixture.destroy();

    expect(isInert('.page-body')).toBe(false);
  });
});
