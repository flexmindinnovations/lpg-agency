import { test, expect } from '@playwright/test';

/**
 * Keyboard-behaviour assertions for the profile menu, complementing the
 * axe scans in `accessibility.spec.ts` — axe cannot verify focus movement
 * or keyboard operability (see that file's own doc comment).
 */
test.describe('Profile menu', () => {
  test('opens via click and closes on Escape, returning focus to the trigger', async ({ page }) => {
    await page.goto('/');
    const trigger = page.getByRole('button', { name: /Account menu/i });

    await trigger.click();
    await expect(page.getByRole('menu')).toBeVisible();

    await page.keyboard.press('Escape');
    await expect(page.getByRole('menu')).toBeHidden();
    await expect(trigger).toBeFocused();
  });

  test('opens via keyboard (Tab + Enter) and lists the expected items', async ({ page }) => {
    await page.goto('/');
    const trigger = page.getByRole('button', { name: /Account menu/i });

    await trigger.focus();
    await page.keyboard.press('Enter');
    const menu = page.getByRole('menu');
    await expect(menu).toBeVisible();

    await expect(menu.getByRole('menuitem', { name: 'My Profile' })).toBeVisible();
    await expect(menu.getByRole('menuitem', { name: 'Account Settings' })).toBeVisible();
    await expect(menu.getByRole('menuitem', { name: 'Sign Out' })).toBeVisible();
  });

  test('Arrow keys move focus between menu items', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /Account menu/i }).click();
    const menu = page.getByRole('menu');
    await expect(menu).toBeVisible();

    const myProfile = menu.getByRole('menuitem', { name: 'My Profile' });
    await myProfile.focus();
    await page.keyboard.press('ArrowDown');
    await expect(menu.getByRole('menuitem', { name: 'Account Settings' })).toBeFocused();

    await page.keyboard.press('ArrowUp');
    await expect(myProfile).toBeFocused();
  });

  test('selecting a theme switches it without closing the menu', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /Account menu/i }).click();
    const menu = page.getByRole('menu');
    await expect(menu).toBeVisible();

    await menu.getByRole('menuitemradio', { name: 'Dark' }).click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
    await expect(menu).toBeVisible();
    await expect(menu.getByRole('menuitemradio', { name: 'Dark' })).toHaveAttribute(
      'aria-checked',
      'true',
    );
  });
});
