import {
  createContext, useCallback, useContext, useEffect, useRef, useState,
  type FormEvent, type ReactNode,
} from "react";
import { getOwnerSession, loginOwner, logoutOwner, type OwnerSession } from "./authApi";

type AuthState =
  | { status: "checking" }
  | { status: "unauthenticated"; error?: string }
  | { status: "authenticated"; session: OwnerSession }
  | { status: "error"; message: string };

interface OwnerAuthContextValue {
  username: string;
  logout: () => Promise<void>;
}
const OwnerAuthContext = createContext<OwnerAuthContextValue | null>(null);

export function useOwnerAuth(): OwnerAuthContextValue {
  const value = useContext(OwnerAuthContext);
  if (!value) throw new Error("OwnerAuthContext is not initialized");
  return value;
}

function LoginView({ onLogin, error }: {
  onLogin: (username: string, password: string) => Promise<void>;
  error?: string;
}) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setLocalError(null);
    try {
      await onLogin(username.trim(), password);
      setPassword("");
    } catch (failure: unknown) {
      setLocalError(failure instanceof Error ? failure.message : "로그인에 실패했습니다.");
    } finally {
      setBusy(false);
    }
  };
  return (
    <main className="auth-screen">
      <form className="auth-card" onSubmit={submit}>
        <span className="auth-brand">FS</span>
        <h1>FolioSentry</h1>
        <p>개인 포트폴리오 모니터링</p>
        <div className="auth-security-note">본인 계정으로 로그인한 후에만 종목과 분석 정보를 볼 수 있습니다.</div>
        <label htmlFor="auth-username">아이디</label>
        <input id="auth-username" type="text" value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="username" required maxLength={64} disabled={busy} />
        <label htmlFor="auth-password">비밀번호</label>
        <input id="auth-password" type="password" value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password" required disabled={busy} />
        {(error || localError) && <div className="auth-error" role="alert">{localError || error}</div>}
        <button className="auth-submit" type="submit" disabled={busy}>
          {busy ? "인증 중…" : "로그인"}
        </button>
        <small>회원가입은 제공하지 않습니다. 관리자 계정은 MiniPC에서 직접 생성합니다.</small>
      </form>
    </main>
  );
}

export default function AuthGate({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "checking" });
  const requestEpoch = useRef(0);
  const mutating = useRef(false);

  const validate = useCallback(async (signal?: AbortSignal) => {
    if (mutating.current) return;
    const epoch = ++requestEpoch.current;
    try {
      const session = await getOwnerSession(signal);
      if (signal?.aborted || epoch !== requestEpoch.current || mutating.current) return;
      setState(session ? { status: "authenticated", session } : { status: "unauthenticated" });
    } catch {
      if (!signal?.aborted && epoch === requestEpoch.current && !mutating.current) {
        setState({ status: "error", message: "인증 서버 상태를 확인할 수 없습니다." });
      }
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void validate(controller.signal);
    // Recheck on tab focus and periodically, so expired sessions hide cached UI.
    const onVisible = () => {
      if (!document.hidden) void validate(controller.signal);
    };
    document.addEventListener("visibilitychange", onVisible);
    const interval = window.setInterval(() => {
      if (!document.hidden) void validate(controller.signal);
    }, 60_000);
    return () => {
      controller.abort();
      document.removeEventListener("visibilitychange", onVisible);
      window.clearInterval(interval);
    };
  }, [validate]);

  const login = async (username: string, password: string) => {
    mutating.current = true;
    requestEpoch.current++;
    try {
      const session = await loginOwner(username, password);
      setState({ status: "authenticated", session });
    } finally {
      mutating.current = false;
    }
  };

  const logout = async () => {
    if (state.status !== "authenticated") return;
    const token = state.session.csrf_token;
    mutating.current = true;
    requestEpoch.current++;
    // Hide financial information immediately while invalidating the server session.
    setState({ status: "checking" });
    try {
      await logoutOwner(token);
      setState({ status: "unauthenticated" });
    } catch {
      setState({ status: "error", message: "로그아웃을 확인하지 못했습니다. 서버 상태를 확인하고 재시도하세요." });
    } finally {
      mutating.current = false;
    }
  };

  if (state.status === "checking") {
    return <main className="auth-screen" role="status"><div className="auth-card"><h1>FolioSentry</h1><p>세션 확인 중…</p></div></main>;
  }
  if (state.status === "error") {
    return <main className="auth-screen"><div className="auth-card" role="alert">
      <h1>인증 서버 연결 오류</h1><p>{state.message}</p>
      <button className="auth-submit" onClick={() => void validate()}>다시 시도</button>
    </div></main>;
  }
  if (state.status === "unauthenticated") return <LoginView onLogin={login} error={state.error} />;
  return (
    <OwnerAuthContext.Provider value={{ username: state.session.username, logout }}>
      {children}
    </OwnerAuthContext.Provider>
  );
}
