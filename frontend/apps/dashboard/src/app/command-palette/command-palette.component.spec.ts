import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { of } from 'rxjs';
import { CustomerService } from '@lpg/shared/data-access';
import { CommandPaletteComponent, fuzzyScore } from './command-palette.component';
import { CommandPaletteService } from './command-palette.service';

describe('fuzzyScore', () => {
  it('scores a contiguous substring above a scattered subsequence', () => {
    expect(fuzzyScore('Dispatch', 'disp')).toBeGreaterThan(fuzzyScore('Driver Performance', 'disp'));
  });

  it('is 0 when a query character is missing', () => {
    expect(fuzzyScore('Orders', 'xyz')).toBe(0);
  });

  it('matches a scattered subsequence (dsp -> Dispatch)', () => {
    expect(fuzzyScore('Dispatch', 'dsp')).toBeGreaterThan(0);
  });

  it('returns a positive score for an empty query', () => {
    expect(fuzzyScore('anything', '')).toBeGreaterThan(0);
  });
});

describe('CommandPaletteService', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({});
  });

  it('captures the trigger and restores focus to it on close', () => {
    const svc = TestBed.inject(CommandPaletteService);
    const btn = document.createElement('button');
    document.body.appendChild(btn);
    btn.focus();
    expect(document.activeElement).toBe(btn);

    svc.open();
    expect(svc.isOpen()).toBe(true);
    (document.activeElement as HTMLElement)?.blur();

    svc.close();
    return Promise.resolve().then(() => {
      expect(svc.isOpen()).toBe(false);
      expect(document.activeElement).toBe(btn);
      btn.remove();
    });
  });
});

describe('CommandPaletteComponent', () => {
  const NAV = [
    { label: 'Dashboard', icon: 'pi pi-home', route: '/' },
    { label: 'Orders', icon: 'pi pi-shopping-cart', route: '/orders' },
    { label: 'Dispatch', icon: 'pi pi-truck', route: '/dispatch' },
  ];

  function setup() {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        { provide: CustomerService, useValue: { list: () => of({ items: [], total: 0 }) } },
      ],
    });
    const fixture = TestBed.createComponent(CommandPaletteComponent);
    fixture.componentRef.setInput('navItems', NAV);
    const svc = TestBed.inject(CommandPaletteService);
    svc.open();
    fixture.detectChanges();
    return { fixture, svc };
  }

  it('lists all nav items when the query is empty and filters as you type', () => {
    const { fixture } = setup();
    const proto = fixture.componentInstance as unknown as {
      query: { set: (v: string) => void };
      flat: () => { label: string }[];
    };
    expect(proto.flat().map((i) => i.label)).toEqual(
      expect.arrayContaining(['Dashboard', 'Orders', 'Dispatch']),
    );

    proto.query.set('disp');
    fixture.detectChanges();
    const labels = proto.flat().map((i) => i.label);
    expect(labels).toContain('Dispatch');
    expect(labels).not.toContain('Dashboard');
  });

  it('moves the active row with ArrowDown and activates it on Enter', () => {
    const { fixture } = setup();
    const router = TestBed.inject(Router);
    const navSpy = jest.spyOn(router, 'navigateByUrl').mockResolvedValue(true);
    const el = fixture.nativeElement as HTMLElement;
    const panel = el.querySelector('.cmdk__panel') as HTMLElement;

    const first = (fixture.componentInstance as unknown as { activeId: () => string }).activeId();
    panel.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    fixture.detectChanges();
    const second = (fixture.componentInstance as unknown as { activeId: () => string }).activeId();
    expect(second).not.toBe(first);

    panel.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    expect(navSpy).toHaveBeenCalled();
  });

  it('closes on Escape', () => {
    const { fixture, svc } = setup();
    const panel = (fixture.nativeElement as HTMLElement).querySelector('.cmdk__panel') as HTMLElement;
    panel.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(svc.isOpen()).toBe(false);
  });
});
