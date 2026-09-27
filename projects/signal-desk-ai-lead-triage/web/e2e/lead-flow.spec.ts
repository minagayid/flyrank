import path from "node:path";
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("reviews a synthetic lead and gets a streamed qualification", async ({ page, browserName }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Lead review" })).toBeVisible();
  await page.getByRole("link", { name: /Open Northline Objects request/ }).click();
  await expect(page).toHaveURL(/\/leads\/northline$/);
  await expect(page.getByRole("heading", { name: "Della Kim" })).toBeVisible();
  await expect(page.getByText("ORIGINAL REQUEST · SYNTHETIC EXAMPLE")).toBeVisible();

  await page.getByRole("button", { name: "What should I ask next?" }).click();
  await page.getByRole("button", { name: "Analyze" }).click();
  await expect(page.getByText("Qualification result ready")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("heading", { name: "Fit signal" })).toBeVisible();
  await expect(page.getByText(/The model gives this request a \d+\/100 fit signal/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Stop" })).toHaveCount(0);
  await expect(page.getByText(/check the original request before deciding what to do/)).toBeVisible();

  if (browserName === "chromium") {
    await page.screenshot({
      path: path.resolve(process.cwd(), "../outputs/signal-desk-lead-review.png"),
      fullPage: true,
    });
  }
});

test("health page renders data fetched from the health endpoint", async ({ page }) => {
  await page.goto("/health");
  await expect(page.getByRole("heading", { name: "Health check" })).toBeVisible();
  await expect(page.getByText("local-logistic-regression")).toBeVisible();
  await expect(page.getByText("synthetic")).toBeVisible();
});

test("primary pages have no automated WCAG A/AA violations", async ({ page }) => {
  const issues: Array<{ route: string; id: string; target: string[]; message: string }> = [];
  for (const route of ["/", "/leads/northline", "/playground/accessibility", "/playground/motion", "/playground/3d", "/playground/shader"]) {
    await page.goto(route);
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    issues.push(...results.violations.flatMap((violation) => violation.nodes.map((node) => ({
      route,
      id: violation.id,
      target: node.target.map((selector) => String(selector)),
      message: node.any[0]?.message ?? violation.help,
    }))));
  }
  expect(issues, JSON.stringify(issues, null, 2)).toEqual([]);
});

test("dialog supports keyboard open, focus containment, Escape, and focus return", async ({ page }) => {
  await page.goto("/playground/accessibility");
  const trigger = page.getByRole("button", { name: "Open sample dialog" });
  await trigger.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog")).toBeVisible();

  await page.keyboard.press("Shift+Tab");
  await expect(page.getByRole("button", { name: "Confirm sample" })).toBeFocused();
  await page.keyboard.press("Escape");

  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(trigger).toBeFocused();
});

test("key pages fit a 320px viewport and honor reduced motion", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 800 });
  for (const route of ["/", "/leads/northline", "/playground/accessibility"]) {
    await page.goto(route);
    const overflows = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    expect(overflows, `${route} should not overflow horizontally at 320px`).toBe(false);
  }

  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/playground/motion");
  const send = page.getByRole("button", { name: "Send response" });
  const transitionDuration = await send.evaluate((element) => getComputedStyle(element).transitionDuration);
  expect(transitionDuration.split(",").every((duration) => Number.parseFloat(duration) <= 0.001)).toBe(true);
  await send.click();
  const spinner = page.locator(".animate-spin");
  await expect(spinner).toHaveCSS("animation-name", "none");
});
