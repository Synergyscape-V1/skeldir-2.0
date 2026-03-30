import { expect, test, type Page } from "@playwright/test";

const FRONTEND_BASE_URL =
  process.env.B15_P7_FRONTEND_BASE_URL ?? "http://127.0.0.1:5173";
const INVESTIGATIONS_BASE_URL =
  process.env.B15_P7_INVESTIGATIONS_BASE_URL ?? "http://127.0.0.1:4024";
const AUTH_BEARER_TOKEN = process.env.B15_P7_E2E_BEARER_TOKEN;

type RequestProbe = {
  url: string;
  timestampMs: number;
};

function assertBrowserRuntimeConfigAvailable(): asserts AUTH_BEARER_TOKEN is string {
  if (!AUTH_BEARER_TOKEN || AUTH_BEARER_TOKEN.trim().length === 0) {
    throw new Error(
      "B15_P7_E2E_BEARER_TOKEN is required for non-skipped P7 browser closure tests.",
    );
  }
}

async function configureCentaurRuntime(page: Page): Promise<void> {
  assertBrowserRuntimeConfigAvailable();
  await page.addInitScript(
    ({ investigationsBaseUrl, bearerToken }) => {
      // Runtime test hook: drives the same controller boundary used in production.
      (globalThis as { __SKELDIR_RUNTIME_CONFIG__?: Record<string, string> }).__SKELDIR_RUNTIME_CONFIG__ =
        {
          llmInvestigationsBaseUrl: investigationsBaseUrl,
          centaurAuthorization: `Bearer ${bearerToken}`,
        };
    },
    {
      investigationsBaseUrl: INVESTIGATIONS_BASE_URL,
      bearerToken: AUTH_BEARER_TOKEN,
    },
  );
}

async function launchInvestigation(page: Page, question: string): Promise<string> {
  const launchResponsePromise = page.waitForResponse(
    (response) =>
      response.url() === `${INVESTIGATIONS_BASE_URL}/api/investigations` &&
      response.request().method() === "POST" &&
      response.status() === 202,
  );

  await page.getByRole("textbox").first().fill(question);
  await page.getByRole("button", { name: "Submit Investigation" }).click();

  const launchResponse = await launchResponsePromise;
  const launchBody = (await launchResponse.json()) as { investigation_id: string };
  return launchBody.investigation_id;
}

async function waitUntilReadyForReview(page: Page): Promise<void> {
  await expect(page.locator(".llm-state-panel__title")).toHaveText(/Ready For Review/i, {
    timeout: 90_000,
  });
  await expect(page.locator(".llm-state-panel__detail")).toContainText(
    "reviewer decision is required",
  );
}

test.describe("B1.5-P7 Browser Closure Proofs", () => {
  test.beforeAll(() => {
    assertBrowserRuntimeConfigAvailable();
  });

  // Marker for P7 static enforcer.
  test("test_b15_p7_browser_launch_poll_review_terminalized_state", async ({
    page,
  }) => {
    test.setTimeout(180_000);
    await configureCentaurRuntime(page);

    const statusRequests: RequestProbe[] = [];
    page.on("request", (request) => {
      if (
        request.method() === "GET" &&
        request.url().includes("/api/investigations/") &&
        request.url().includes("/status")
      ) {
        statusRequests.push({ url: request.url(), timestampMs: Date.now() });
      }
    });

    await page.goto(`${FRONTEND_BASE_URL}/investigations`);
    await expect(page.getByText("Investigation Request")).toBeVisible();

    const investigationId = await launchInvestigation(
      page,
      "Why did deterministic ROAS decline week-over-week in paid channels?",
    );
    const statusPath = `/api/investigations/${investigationId}/status`;

    await expect(page.getByText(`Active Investigation ID: ${investigationId}`)).toBeVisible({
      timeout: 15_000,
    });

    await waitUntilReadyForReview(page);

    await expect
      .poll(
        () => statusRequests.filter((event) => event.url.includes(statusPath)).length,
        { timeout: 90_000 },
      )
      .toBeGreaterThanOrEqual(3);

    const matchingPolls = statusRequests
      .filter((event) => event.url.includes(statusPath))
      .slice(0, 3);
    const pollDeltas = [
      matchingPolls[1].timestampMs - matchingPolls[0].timestampMs,
      matchingPolls[2].timestampMs - matchingPolls[1].timestampMs,
    ];
    for (const deltaMs of pollDeltas) {
      expect(deltaMs).toBeGreaterThanOrEqual(3_000);
      expect(deltaMs).toBeLessThanOrEqual(7_000);
    }

    const approveResponsePromise = page.waitForResponse(
      (response) =>
        response.url() === `${INVESTIGATIONS_BASE_URL}/api/investigations/${investigationId}/approve` &&
        response.request().method() === "POST",
    );
    await page.locator("button[data-action='approve']").click();
    const approveResponse = await approveResponsePromise;
    expect(approveResponse.status()).toBe(200);

    await expect(page.locator(".llm-state-panel__title")).toHaveText(/Approved/i, {
      timeout: 15_000,
    });
    await expect(page.getByText("Action: approve | Status: approved")).toBeVisible();
  });

  // Marker for P7 static enforcer.
  test("test_b15_p7_browser_conflict_response_surfaces_ui_issue_and_reconciliation", async ({
    page,
  }) => {
    test.setTimeout(180_000);
    await configureCentaurRuntime(page);
    await page.goto(`${FRONTEND_BASE_URL}/investigations`);

    const investigationId = await launchInvestigation(
      page,
      "Why did deterministic conversion quality shift in the last seven days?",
    );
    const statusPath = `/api/investigations/${investigationId}/status`;
    const approvePath = `${INVESTIGATIONS_BASE_URL}/api/investigations/${investigationId}/approve`;

    await waitUntilReadyForReview(page);

    let backendSeeded = false;
    await page.route(approvePath, async (route) => {
      if (backendSeeded) {
        await route.continue();
        return;
      }

      backendSeeded = true;
      const request = route.request();
      const requestHeaders = request.headers();
      const idempotencyKey = requestHeaders["x-idempotency-key"];
      const authorization = requestHeaders["authorization"];

      expect(idempotencyKey).toBeTruthy();
      expect(authorization).toBeTruthy();

      const seedResponse = await page.request.post(approvePath, {
        headers: {
          Authorization: String(authorization),
          "X-Correlation-ID": "00000000-0000-4000-8000-000000000410",
          "X-Idempotency-Key": String(idempotencyKey),
          "Content-Type": "application/json",
        },
        data: {
          reason: "seed_backend_conflict_path",
          note: "seed_backend_conflict_path",
        },
      });
      expect(seedResponse.status()).toBe(200);
      await route.continue();
    });

    const conflictResponsePromise = page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        response.url() === approvePath &&
        response.status() === 409,
    );

    const reconcileResponsePromise = page.waitForResponse(
      (response) =>
        response.request().method() === "GET" &&
        response.url().includes(statusPath) &&
        response.status() === 200,
    );
    await page.locator("button[data-action='approve']").click();
    const conflictResponse = await conflictResponsePromise;
    const conflictBody = (await conflictResponse.json()) as {
      code?: string;
      status?: number;
      detail?: string;
    };
    expect(conflictBody.code).toBe("IDEMPOTENCY_KEY_CONFLICT");
    expect(conflictBody.status).toBe(409);
    await reconcileResponsePromise;

    const issueSurface = page.locator(
      "[data-mutation-issue-kind='idempotency_conflict']",
    );
    await expect(issueSurface).toBeVisible({ timeout: 15_000 });
    await expect(issueSurface).toContainText("Idempotency Conflict");
    await expect(issueSurface).toContainText(
      "idempotency key was reused with a different authority-boundary payload",
    );
    await expect(page.locator(".llm-state-panel__title")).toHaveText(/Approved/i, {
      timeout: 15_000,
    });
    await expect(page.locator("button[data-action='approve']")).toHaveCount(0);
  });
});
