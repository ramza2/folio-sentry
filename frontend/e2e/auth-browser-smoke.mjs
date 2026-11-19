/**
 * AUTH-01 full-browser acceptance smoke, running only in isolated CI with
 * synthetic credentials and fictional stock data. Never targets a home server.
 */
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { chromium, request } from "playwright";

const origin = process.env.FOLIOSENTRY_E2E_ORIGIN ?? "http://127.0.0.1:18902";
const username = process.env.FOLIOSENTRY_E2E_USERNAME ?? "ci-owner";
const password = process.env.FOLIOSENTRY_E2E_PASSWORD;
if (!password) throw new Error("CI synthetic E2E password was not provided");

await mkdir("e2e/screenshots", { recursive: true });
const browser = await chromium.launch({ headless: true, channel: "chrome" });
const api = await request.newContext({ baseURL: origin });
const pageErrors = [];
const check = (label) => console.log("PASS:", label);

async function login(page) {
  await page.getByLabel("아이디").fill(username);
  await page.getByLabel("비밀번호").fill(password);
  await page.getByRole("button", { name: "로그인", exact: true }).click();
  await page.getByRole("heading", { name: "대시보드", exact: true }).waitFor();
  await page.getByText("화면 시연용 가상 데이터입니다.", { exact: false }).first().waitFor();
}

try {
  // A fresh request context has no authentication cookies.
  assert.equal((await api.get("/api/v1/demo/overview")).status(), 401);
  assert.equal((await api.get("/api/v1/demo/instruments")).status(), 401);
  assert.equal((await api.get("/api/v1/auth/me")).status(), 401);
  check("anonymous API requests fail closed");

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 }, locale: "ko-KR",
  });
  const page = await context.newPage();
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await page.goto(origin, { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: "FolioSentry", exact: true }).waitFor();
  await page.getByRole("button", { name: "로그인", exact: true }).waitFor();
  assert.equal(await page.getByText("내 포트폴리오").count(), 0);
  check("unauthenticated UI contains no portfolio");

  await page.getByLabel("아이디").fill(username);
  await page.getByLabel("비밀번호").fill("incorrect-test-value");
  await page.getByRole("button", { name: "로그인", exact: true }).click();
  await page.getByRole("alert").filter({ hasText: "아이디 또는 비밀번호" }).waitFor();
  assert.equal(await page.getByText("내 포트폴리오").count(), 0);
  check("invalid credentials rejected without data exposure");

  await login(page);
  await page.getByText("내 포트폴리오").waitFor();
  assert.equal(await page.getByText("실제 시세·뉴스·매매 신호가 아닙니다.", { exact: false }).count() > 0, true);
  await page.screenshot({ path: "e2e/screenshots/desktop-authenticated.png", fullPage: true });
  check("desktop login, DEMO banner and dashboard");

  const nav = page.locator("nav");
  await nav.getByRole("button", { name: "내 종목" }).click();
  await page.getByRole("heading", { name: "내 종목", exact: true }).waitFor();
  await page.locator(".table-row[role='button']").first().click();
  await page.getByRole("heading", { name: "삼성전자", exact: true }).waitFor();
  await nav.getByRole("button", { name: "뉴스" }).click();
  await page.getByRole("heading", { name: "뉴스", exact: true }).waitFor();
  await nav.getByRole("button", { name: /신호 · 알림/ }).click();
  await page.getByRole("heading", { name: "신호 · 알림 이력" }).waitFor();
  await nav.getByRole("button", { name: "설정" }).click();
  await page.getByRole("heading", { name: "설정", exact: true }).waitFor();
  await nav.getByRole("button", { name: "대시보드" }).click();
  check("six Figma UI screens and stock detail navigation");

  await page.reload({ waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: "대시보드", exact: true }).waitFor();
  check("authenticated session survives browser reload");

  // A deliberate API outage must show an error, not stale fabricated quotes.
  await page.route("**/api/v1/demo/overview", (route) => route.fulfill({
    status: 503, contentType: "application/json", body: '{"error":"synthetic outage"}',
  }));
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: "DEMO 데이터 연결 실패" }).waitFor();
  assert.equal(await page.getByText("내 포트폴리오").count(), 0);
  await page.unroute("**/api/v1/demo/overview");
  await page.getByRole("button", { name: "다시 시도" }).click();
  await page.getByText("내 포트폴리오").waitFor();
  check("API outage fail-closed and retry");

  // A protected mutation without CSRF token must not reach an endpoint.
  const cookies = await context.cookies(origin);
  const authCookie = cookies.find((item) => item.name === "foliosentry_session_local");
  assert.ok(authCookie, "expected test-only HttpOnly session cookie");
  assert.equal(authCookie.httpOnly, true);
  assert.equal(authCookie.sameSite, "Strict");
  const missingCsrf = await api.post("/api/v1/auth/logout", {
    headers: {
      Cookie: `${authCookie.name}=${authCookie.value}`,
      Origin: origin,
    },
  });
  assert.equal(missingCsrf.status(), 403);
  const maliciousOrigin = await api.post("/api/v1/auth/logout", {
    headers: {
      Cookie: `${authCookie.name}=${authCookie.value}`,
      Origin: "https://malicious.example",
    },
  });
  assert.equal(maliciousOrigin.status(), 403);
  check("CSRF and foreign Origin blocked");

  await page.getByRole("button", { name: "로그아웃" }).click();
  await page.getByRole("button", { name: "로그인", exact: true }).waitFor();
  assert.equal(await page.getByText("내 포트폴리오").count(), 0);
  assert.equal((await page.request.get(origin + "/api/v1/demo/overview")).status(), 401);
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "로그인", exact: true }).waitFor();
  check("logout clears server session and browser portfolio");

  // Mobile layout: no bypass of authentication, same DEMO-only data.
  const mobileContext = await browser.newContext({
    viewport: { width: 390, height: 844 }, isMobile: true,
    deviceScaleFactor: 1, hasTouch: true, locale: "ko-KR",
  });
  const mobile = await mobileContext.newPage();
  mobile.on("pageerror", (error) => pageErrors.push(error.message));
  await mobile.goto(origin, { waitUntil: "domcontentloaded" });
  await mobile.getByRole("button", { name: "로그인", exact: true }).waitFor();
  await mobile.screenshot({ path: "e2e/screenshots/mobile-login.png", fullPage: true });
  await login(mobile);
  await mobile.getByText("내 포트폴리오").waitFor();
  await mobile.screenshot({ path: "e2e/screenshots/mobile-authenticated.png", fullPage: true });
  check("mobile login and dashboard");

  assert.deepEqual(pageErrors, []);
  check("no unhandled browser JavaScript errors");
  await mobileContext.close();
  await context.close();
} finally {
  await api.dispose();
  await browser.close();
}
