import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: { timeout: 15_000 },
  // Os specs dividem a Empresa Alfa e o mesmo compose; na CI rodam um de cada vez.
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    ...devices["Desktop Chrome"],
    baseURL: "http://localhost:5173",
    trace: process.env.CI ? "retain-on-failure" : "on-first-retry",
  },
});
