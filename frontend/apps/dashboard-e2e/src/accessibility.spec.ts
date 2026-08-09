import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

/**
 * WCAG 2.2 AA automated gate (D-35, roadmap Phase 4). Automated scanning
 * catches only a subset of accessibility requirements — contrast, missing
 * labels, invalid ARIA, landmark structure — never keyboard-operability or
 * screen-reader UX quality. It is a floor, not a substitute for the manual
 * verification already done for the PrimeNG integration and this shell.
 */
test.describe('Accessibility', () => {
  test('home page has no WCAG 2.1/2.2 AA violations (light theme)', async ({ page }) => {
    await page.goto('/');

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
      .analyze();

    expect(results.violations).toEqual([]);
  });

  test('home page has no WCAG 2.1/2.2 AA violations (dark theme)', async ({ page }) => {
    await page.goto('/');
    await page.locator('.shell__theme-trigger').click();
    await page.getByRole('menuitem', { name: 'Dark' }).click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
    // The theme menu's own close transition must finish before scanning —
    // axe caught it mid-fade once, evaluating genuinely transient
    // (transition-blended) colours that never appear in the settled DOM.
    await expect(page.locator('.p-menu-item-label').first()).toBeHidden();

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
      .analyze();

    expect(results.violations).toEqual([]);
  });

  test('home page has no WCAG 2.1/2.2 AA violations (high contrast theme)', async ({ page }) => {
    await page.goto('/');
    await page.locator('.shell__theme-trigger').click();
    await page.getByRole('menuitem', { name: 'High contrast' }).click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'high-contrast');
    await expect(page.locator('.p-menu-item-label').first()).toBeHidden();

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
      .analyze();

    expect(results.violations).toEqual([]);
  });

  test('the collapsed sidebar has no WCAG 2.1/2.2 AA violations', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /collapse sidebar/i }).click();

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
      .analyze();

    expect(results.violations).toEqual([]);
  });

  test('the open dialog has no WCAG 2.1/2.2 AA violations', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Open dialog' }).click();
    await expect(page.getByRole('dialog')).toBeVisible();

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
      .analyze();

    expect(results.violations).toEqual([]);
  });
});
