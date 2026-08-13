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
    // Theme switching now lives in the profile menu (the old standalone
    // `.shell__theme-trigger` was removed as a visual duplicate of it).
    await page.getByRole('button', { name: /Account menu/i }).click();
    await page.getByRole('menuitemradio', { name: 'Dark' }).click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
    await page.keyboard.press('Escape');
    await expect(page.getByRole('menu')).toBeHidden();

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
      .analyze();

    expect(results.violations).toEqual([]);
  });

  test('home page has no WCAG 2.1/2.2 AA violations (high contrast theme)', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /Account menu/i }).click();
    await page.getByRole('menuitemradio', { name: 'High contrast' }).click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'high-contrast');
    await page.keyboard.press('Escape');
    await expect(page.getByRole('menu')).toBeHidden();

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

  test('the open profile menu has no WCAG 2.1/2.2 AA violations (light theme)', async ({
    page,
  }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /Account menu/i }).click();
    await expect(page.getByRole('menu')).toBeVisible();

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
      .analyze();

    expect(results.violations).toEqual([]);
  });

  test('the open profile menu has no WCAG 2.1/2.2 AA violations (dark theme)', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /Account menu/i }).click();
    await expect(page.getByRole('menu')).toBeVisible();

    await page.getByRole('menuitemradio', { name: 'Dark' }).click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
      .analyze();

    expect(results.violations).toEqual([]);
  });
});
