/** Same-origin, HttpOnly cookie auth. No tokens in localStorage or URL. */
export interface OwnerSession {
  authenticated: true;
  username: string;
  csrf_token: string;
}

function parseSession(value: unknown): OwnerSession {
  if (!value || typeof value !== "object") throw new Error("로그인 응답 형식이 잘못됐습니다.");
  const body = value as Partial<OwnerSession>;
  if (body.authenticated !== true || typeof body.username !== "string" ||
      typeof body.csrf_token !== "string" || body.csrf_token.length < 32) {
    throw new Error("로그인 응답 검증 실패");
  }
  return body as OwnerSession;
}

export async function getOwnerSession(signal?: AbortSignal): Promise<OwnerSession | null> {
  const response = await fetch("/api/v1/auth/me", {
    method: "GET", credentials: "same-origin", cache: "no-store", signal,
  });
  if (response.status === 401) return null;
  if (!response.ok) throw new Error("인증 서버 연결에 실패했습니다.");
  return parseSession(await response.json() as unknown);
}

export async function loginOwner(username: string, password: string): Promise<OwnerSession> {
  const response = await fetch("/api/v1/auth/login", {
    method: "POST", credentials: "same-origin", cache: "no-store",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (response.status === 401) throw new Error("아이디 또는 비밀번호가 올바르지 않습니다.");
  if (response.status === 429) throw new Error("로그인 시도가 제한됐습니다. 잠시 후 다시 시도하세요.");
  if (response.status === 503) throw new Error("소유자 계정이 준비되지 않았습니다. 서버 관리자 설정을 확인하세요.");
  if (!response.ok) throw new Error("로그인 요청에 실패했습니다.");
  return parseSession(await response.json() as unknown);
}

export async function logoutOwner(csrfToken: string): Promise<void> {
  const response = await fetch("/api/v1/auth/logout", {
    method: "POST", credentials: "same-origin", cache: "no-store",
    headers: { "X-CSRF-Token": csrfToken },
  });
  if (!response.ok) throw new Error("서버 로그아웃에 실패했습니다. 연결 상태를 확인하세요.");
}
