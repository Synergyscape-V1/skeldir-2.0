import { createContext, useContext, useState, useRef, useEffect, useMemo, ReactNode } from 'react';

export interface JWTPayload { exp: number; sub: string; [key: string]: any; }
export interface TokenValidation { valid: boolean; expiresIn: number; claims: JWTPayload | null; }
export interface TokenContextValue {
  token: string | null; isAuthenticated: boolean; isRefreshing: boolean; expiresAt: Date | null;
  refreshError: Error | null; setToken: (token: string) => void; clearToken: () => void;
  refreshToken: () => Promise<void>; validateToken: () => TokenValidation;
}

const TokenContext = createContext<TokenContextValue | null>(null);

const parseJWT = (t: string) => {
  const p = t.split('.'); if (p.length !== 3) throw new Error('Invalid JWT');
  const d = JSON.parse(atob(p[1])); if (typeof d.exp !== 'number') throw new Error('No exp'); return d;
};

const validate = (t: string | null): TokenValidation => {
  if (!t) return { valid: false, expiresIn: 0, claims: null };
  try { const c = parseJWT(t), e = c.exp * 1000 - Date.now(); return { valid: e > 0, expiresIn: e, claims: c }; }
  catch { return { valid: false, expiresIn: 0, claims: null }; }
};

export function TokenProvider({ children, onTokenExpired }: { children: ReactNode; onTokenExpired?: () => void }) {
  const [token, setT] = useState<string | null>(null);
  const [expiresAt, setE] = useState<Date | null>(null);
  const [isRefreshing, setR] = useState(false);
  const [refreshError, setErr] = useState<Error | null>(null);
  const refP = useRef<Promise<void> | null>(null), timer = useRef<number | null>(null);

  const setToken = (n: string) => { const { exp } = parseJWT(n); setT(n); setE(new Date(exp * 1000)); setErr(null); };
  const clearToken = () => { setT(null); setE(null); setErr(null); if (timer.current) clearTimeout(timer.current); };

  const refreshToken = async () => {
    if (refP.current) return refP.current;
    refP.current = (async () => {
      setR(true);
      for (let i = 0; i <= 3; i++) {
        try {
          const r = await fetch('/api/auth/refresh', { method: 'POST', credentials: 'include' });
          if (!r.ok) throw new Error(`Fail: ${r.status}`);
          const d = await r.json(); setToken(d.token || d.accessToken); return;
        } catch (e) { if (i < 3) await new Promise(res => setTimeout(res, [1000, 2000, 4000][i])); else setErr(e as Error); }
      }
    })();
    try { await refP.current; } finally { setR(false); refP.current = null; }
  };

  useEffect(() => {
    if (!expiresAt) return;
    const d = expiresAt.getTime() - 5 * 60 * 1000 - Date.now();
    if (d > 0) timer.current = window.setTimeout(refreshToken, d);
    else refreshToken();
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, [expiresAt]);

  useEffect(() => { if (token && !validate(token).valid) { onTokenExpired?.(); clearToken(); } }, [token, expiresAt]);

  const isAuth = useMemo(() => token !== null && validate(token).valid, [token, expiresAt]);

  return <TokenContext.Provider value={{ token, isAuthenticated: isAuth, isRefreshing, expiresAt, refreshError,
    setToken, clearToken, refreshToken, validateToken: () => validate(token) }}>{children}</TokenContext.Provider>;
}

export function useTokenManager(): TokenContextValue {
  const ctx = useContext(TokenContext); if (!ctx) throw new Error('Use within TokenProvider'); return ctx;
}
