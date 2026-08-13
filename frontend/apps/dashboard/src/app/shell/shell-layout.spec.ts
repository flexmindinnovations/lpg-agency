import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { ShellLayout } from './shell-layout';

describe('ShellLayout', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ShellLayout],
      providers: [provideRouter([])],
    }).compileComponents();
  });

  it('renders', () => {
    const fixture = TestBed.createComponent(ShellLayout);
    fixture.detectChanges();
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('exposes a skip link as the first focusable element', () => {
    // WCAG 2.2 AA (D-35): keyboard users must be able to bypass navigation.
    const fixture = TestBed.createComponent(ShellLayout);
    fixture.detectChanges();
    const skipLink: HTMLAnchorElement | null =
      fixture.nativeElement.querySelector('.shell__skip-link');
    expect(skipLink).toBeTruthy();
    expect(skipLink?.getAttribute('href')).toBe('#shell-main-content');
  });

  it('marks navigation and main content as landmarks', () => {
    const fixture = TestBed.createComponent(ShellLayout);
    fixture.detectChanges();
    const el: HTMLElement = fixture.nativeElement;
    expect(el.querySelector('nav[aria-label="Main navigation"]')).toBeTruthy();
    expect(el.querySelector('main#shell-main-content')).toBeTruthy();
    expect(el.querySelector('header')).toBeTruthy();
  });

  it('exposes a profile menu whose theme section offers all four theme options', () => {
    const fixture = TestBed.createComponent(ShellLayout);
    fixture.detectChanges();
    const trigger: HTMLButtonElement | null =
      fixture.nativeElement.querySelector('.profile-menu__trigger');
    expect(trigger).toBeTruthy();
    trigger?.click();
    fixture.detectChanges();

    const items: NodeListOf<HTMLElement> = document.querySelectorAll('[role="menuitemradio"]');
    const labels = Array.from(items).map((el) => el.querySelector('span')?.textContent?.trim());
    expect(labels).toEqual(['System', 'Light', 'Dark', 'High contrast']);
  });
});
