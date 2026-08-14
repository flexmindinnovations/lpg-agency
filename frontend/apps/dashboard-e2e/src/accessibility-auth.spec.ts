import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test.describe('Accessibility - Authenticated Pages', () => {

  // A helper to mock auth and navigate to a route
  async function mockAuthAndNavigate(page: any, url: string) {
    // Mock the auth endpoints to simulate a logged-in state
    await page.route('**/api/v1/auth/me', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: '12345',
          email: 'admin@example.com',
          tenant_id: 'tenant1'
        })
      });
    });

    // Mock WebSocket connection
    await page.route('**/api/v1/ws**', route => {
       route.abort(); // Prevent hanging WebSocket connections in tests
    });

    await page.goto(url);
    await page.waitForLoadState('domcontentloaded');
    // Wait an extra second for UI to settle
    await page.waitForTimeout(1000);
  }

  test('Customer Management should not have accessibility issues', async ({ page }) => {
    await mockAuthAndNavigate(page, '/dashboard/customers');
    const accessibilityScanResults = await new AxeBuilder({ page })
      .withTags(['wcag2aa'])
      .analyze();
      
    expect(accessibilityScanResults.violations).toEqual([]);
  });
  
  test('Order Queue should not have accessibility issues', async ({ page }) => {
    await mockAuthAndNavigate(page, '/dashboard/orders');
    const accessibilityScanResults = await new AxeBuilder({ page })
      .withTags(['wcag2aa'])
      .analyze();
      
    expect(accessibilityScanResults.violations).toEqual([]);
  });

  test('Reporting Daily Sales should not have accessibility issues', async ({ page }) => {
    await mockAuthAndNavigate(page, '/dashboard/reporting/daily-sales');
    const accessibilityScanResults = await new AxeBuilder({ page })
      .withTags(['wcag2aa'])
      .analyze();
      
    expect(accessibilityScanResults.violations).toEqual([]);
  });
});
