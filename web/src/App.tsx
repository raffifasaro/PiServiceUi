import { useCallback, useEffect, useRef, useState } from "react";
import { api, AuthError } from "./api";
import type { ServiceInfo, Snapshot } from "./types";
import { Login } from "./components/Login";
import { Sidebar } from "./components/Sidebar";
import { ServiceGrid } from "./components/ServiceGrid";
import { LogDrawer } from "./components/LogDrawer";

type AuthState = "loading" | "anon" | "authed";

export function App() {
  const [auth, setAuth] = useState<AuthState>("loading");
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [connected, setConnected] = useState(false);
  const [logName, setLogName] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    api
      .checkAuth()
      .then(() => setAuth("authed"))
      .catch(() => setAuth("anon"));
  }, []);

  // Live snapshot stream (metrics + service status) once authenticated.
  useEffect(() => {
    if (auth !== "authed") return;
    const es = new EventSource("/api/stream", { withCredentials: true });
    esRef.current = es;
    es.addEventListener("snapshot", (ev) => {
      setConnected(true);
      try {
        setSnapshot(JSON.parse((ev as MessageEvent).data));
      } catch {
        /* ignore malformed frame */
      }
    });
    es.onerror = () => {
      setConnected(false);
      // The stream is auth-gated; a drop may mean the session expired.
      api.checkAuth().catch(() => {
        es.close();
        setAuth("anon");
      });
    };
    return () => {
      es.close();
      esRef.current = null;
    };
  }, [auth]);

  const guard = useCallback(async (p: Promise<unknown>) => {
    try {
      await p;
    } catch (err) {
      if (err instanceof AuthError) setAuth("anon");
      else alert((err as Error).message);
    }
  }, []);

  const onAction = useCallback(
    (name: string, action: "start" | "stop" | "restart") =>
      guard(api[action](name)),
    [guard],
  );

  const onRescan = useCallback(() => guard(api.rescan()), [guard]);
  const onLogout = useCallback(async () => {
    await api.logout().catch(() => undefined);
    esRef.current?.close();
    setAuth("anon");
    setSnapshot(null);
  }, []);

  if (auth === "loading") {
    return <div className="splash">Loading…</div>;
  }
  if (auth === "anon") {
    return <Login onSuccess={() => setAuth("authed")} />;
  }

  const services: ServiceInfo[] = snapshot?.services ?? [];

  return (
    <div className="layout">
      <Sidebar host={snapshot?.host ?? null} connected={connected} />
      <main className="content">
        <header className="topbar">
          <h1>Services</h1>
          <div className="topbar-actions">
            <span className={`conn ${connected ? "ok" : "bad"}`}>
              {connected ? "live" : "reconnecting…"}
            </span>
            <button onClick={onRescan}>Rescan</button>
            <button onClick={onLogout}>Log out</button>
          </div>
        </header>
        <ServiceGrid
          services={services}
          onAction={onAction}
          onShowLogs={setLogName}
        />
      </main>
      {logName && (
        <LogDrawer name={logName} onClose={() => setLogName(null)} guard={guard} />
      )}
    </div>
  );
}
