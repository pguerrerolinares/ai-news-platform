import { Page } from '@playwright/test';

// JWT mock con exp=9999999999 (año ~2286)
export const MOCK_JWT =
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9' +
  '.eyJzdWIiOiIxIiwiZXhwIjo5OTk5OTk5OTk5fQ' +
  '.mockSignature';

/** Inyecta el JWT en localStorage para bypasear el login UI */
export async function authenticate(page: Page): Promise<void> {
  await page.goto('/');
  await page.evaluate((token) => {
    localStorage.setItem('ainews_token', token);
  }, MOCK_JWT);
}
