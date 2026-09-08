import { test, expect } from '@playwright/test';

// End-to-end tenant isolation proof
test.describe('Tenant Isolation', () => {
  const tenantAEmail = process.env.TEST_TENANT_A_EMAIL;
  const tenantAPassword = process.env.TEST_TENANT_A_PASSWORD;
  const tenantBId = process.env.TEST_TENANT_B_ID;
  const baseUrl = process.env.BASE_URL || 'http://localhost:8000';

  // Skip tests if essential environment variables are not set.
  test.skip(!tenantAEmail || !tenantAPassword || !tenantBId, 'Skipping tenant isolation tests: required environment variables (TEST_TENANT_A_EMAIL, TEST_TENANT_A_PASSWORD, TEST_TENANT_B_ID) are not set.');

  test('should prevent access to other tenants resources even with spoofed headers', async ({ request }) => {
    // NOTE: These test credentials must exist in your test fixture database.
    const tenantA = { email: tenantAEmail, password: tenantAPassword };

    // 1) Login as Tenant A (obtain JWT)
    const tokenResp = await request.post(`${baseUrl}/api/v1/auth/access-token`, {
      form: {
        username: tenantA.email,
        password: tenantA.password,
      },
    });

    expect(tokenResp.ok(), 'Login should be successful.').toBe(true);
    const tokenJson = await tokenResp.json();
    const jwt = tokenJson?.access_token;
    expect(jwt, 'JWT should be a non-empty string.').toBeTruthy();

    // 2) Attempt to read a resource that belongs to Tenant B while spoofing X-Org-ID
    const protectedUrl = `${baseUrl}/api/v1/tenants/${tenantBId}/ledger`;

    const spoofResp = await request.get(protectedUrl, {
      headers: {
        Authorization: `Bearer ${jwt}`,
        'X-Org-ID': tenantBId,
        Accept: 'application/json',
      },
    });

    // The system must reject access — verify 401 or 403
    const status = spoofResp.status();
    expect([401, 403], `Request should be rejected with 401 or 403, but got ${status}.`).toContain(status);

    // Optionally assert body contains a clear denial reason
    const contentType = spoofResp.headers()['content-type'];
    if (contentType && contentType.includes('application/json')) {
      const body = await spoofResp.json();
      expect(body, 'Error response body should have a "detail" property.').toHaveProperty('detail');
      expect(typeof body.detail, 'The "detail" property in the error response should be a string.').toBe('string');
    } else {
      const body = await spoofResp.text();
      expect(body.length, 'Error response body should not be empty.').toBeGreaterThan(0);
    }
  });
});
