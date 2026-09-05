import { TestBed } from '@angular/core/testing';
import { ThemeService } from './theme.service';

describe('ThemeService', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
    TestBed.configureTestingModule({});
  });

  it('defaults to dark when no preference is stored', () => {
    const service = TestBed.inject(ThemeService);
    expect(service.preference()).toBe('dark');
  });

  it('applies each of the three themes to the document', () => {
    const service = TestBed.inject(ThemeService);

    for (const theme of ['light', 'dark', 'high-contrast'] as const) {
      service.setPreference(theme);
      TestBed.tick();
      expect(document.documentElement.getAttribute('data-theme')).toBe(theme);
      expect(service.activeTheme()).toBe(theme);
    }
  });

  it('removes the attribute for system, so the media query can take over', () => {
    const service = TestBed.inject(ThemeService);
    service.setPreference('dark');
    TestBed.tick();
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');

    service.setPreference('system');
    TestBed.tick();
    expect(document.documentElement.hasAttribute('data-theme')).toBe(false);
  });

  it('persists the choice', () => {
    TestBed.inject(ThemeService).setPreference('high-contrast');
    expect(localStorage.getItem('lpg.theme')).toBe('high-contrast');
  });

  it('ignores an unrecognised stored value and falls back to dark', () => {
    localStorage.setItem('lpg.theme', 'neon');
    expect(TestBed.inject(ThemeService).preference()).toBe('dark');
  });
});
