import { test, expect } from '@playwright/test';

test('renders the app shell with the expected heading', async ({ page }) => {
  await page.goto('/');

  await expect(page.locator('h1')).toContainText('Repository foundation');
});

test('sidebar collapse toggle collapses and expands the sidebar', async ({ page }) => {
  await page.goto('/');

  const toggle = page.getByRole('button', { name: /collapse sidebar/i });
  const brandName = page.locator('.shell__brand-name');

  await expect(brandName).toBeVisible();
  await toggle.click();
  await expect(brandName).toBeHidden();
  await page.getByRole('button', { name: /expand sidebar/i }).click();
  await expect(brandName).toBeVisible();
});

test('theme menu switches to dark mode and applies data-theme', async ({ page }) => {
  await page.goto('/');

  await page.locator('.shell__theme-trigger').click();
  await page.getByRole('menuitem', { name: 'Dark' }).click();

  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
});

test('has no unhandled console errors on load', async ({ page }) => {
  const errors: string[] = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') errors.push(msg.text());
  });

  await page.goto('/');
  // `networkidle` is discouraged (playwright/no-networkidle) — flaky for
  // any app with persistent background activity. Wait for actionability
  // (the heading actually rendering) instead of a network-quiescence guess.
  await expect(page.locator('h1')).toBeVisible();

  expect(errors).toEqual([]);
});
