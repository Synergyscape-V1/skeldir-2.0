import { test, expect } from "@playwright/test";

/**
 * H03 validation: Mobile nav menu must open when the hamburger is pressed at 375px viewport.
 * Run with: npx playwright test --project=mobile-375
 */
test.describe("Mobile navigation (375px viewport)", () => {
  test.use({ viewport: { width: 375, height: 667 } });

  test("hamburger opens menu and menu content is visible", async ({ page }) => {
    await page.goto("/");

    const toggle = page.getByRole("button", { name: /toggle menu/i });
    await expect(toggle).toBeVisible();
    await expect(toggle).toHaveAttribute("aria-expanded", "false");

    await toggle.click();

    await expect(toggle).toHaveAttribute("aria-expanded", "true");
    const menu = page.locator(".mobile-menu-open");
    await expect(menu).toBeVisible();
    await expect(menu.getByRole("link", { name: "Product" })).toBeVisible();
    await expect(menu.getByRole("link", { name: "Login" })).toBeVisible();
  });

  test("close button closes menu", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /toggle menu/i }).click();
    await expect(page.locator(".mobile-menu-open")).toBeVisible();

    await page.getByRole("button", { name: /close menu/i }).click();
    await expect(page.locator(".mobile-menu-open")).not.toBeVisible();
  });
});
