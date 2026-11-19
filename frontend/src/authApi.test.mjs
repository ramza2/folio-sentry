import test from "node:test";
import assert from "node:assert/strict";
import { getOwnerSession, loginOwner, logoutOwner } from "./authApi.ts";

const session = {
  authenticated: true, username: "owner",
  csrf_token: "an-example-csrf-token-with-sufficient-length",
};

test("unauthenticated session returns null instead of demo data", async () => {
  const previous = globalThis.fetch;
  globalThis.fetch = async () => ({ status: 401, ok: false });
  try { assert.equal(await getOwnerSession(), null); } finally { globalThis.fetch = previous; }
});

test("login sends credentials only in POST JSON body and validates response", async () => {
  const previous = globalThis.fetch;
  globalThis.fetch = async (url, options) => {
    assert.equal(url, "/api/v1/auth/login");
    assert.equal(options.method, "POST");
    assert.equal(options.credentials, "same-origin");
    assert.deepEqual(JSON.parse(options.body), { username: "owner", password: "test-passphrase" });
    return { status: 200, ok: true, json: async () => session };
  };
  try { assert.deepEqual(await loginOwner("owner", "test-passphrase"), session); }
  finally { globalThis.fetch = previous; }
});

test("login rejects malformed identity and server authentication errors", async () => {
  const previous = globalThis.fetch;
  globalThis.fetch = async () => ({ status: 200, ok: true, json: async () => ({ authenticated: true }) });
  try { await assert.rejects(loginOwner("x", "y"), /검증 실패/); }
  finally { globalThis.fetch = previous; }
});

test("logout uses CSRF header and same-origin cookie request", async () => {
  const previous = globalThis.fetch;
  globalThis.fetch = async (url, options) => {
    assert.equal(url, "/api/v1/auth/logout");
    assert.equal(options.method, "POST");
    assert.equal(options.headers["X-CSRF-Token"], session.csrf_token);
    assert.equal(options.credentials, "same-origin");
    return { status: 200, ok: true };
  };
  try { await logoutOwner(session.csrf_token); }
  finally { globalThis.fetch = previous; }
});
