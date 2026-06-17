import { useState } from "react";
import type { ServiceInfo } from "../types";
import { bytes, duration, pct } from "../format";

const STATE_LABEL: Record<string, string> = {
  stopped: "Stopped",
  starting: "Starting",
  running: "Running",
  stopping: "Stopping",
  crashed: "Crashed",
  error: "Manifest error",
};

export function ServiceCard({
  svc,
  onAction,
  onShowLogs,
}: {
  svc: ServiceInfo;
  onAction: (name: string, action: "start" | "stop" | "restart") => void;
  onShowLogs: (name: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const isError = svc.state === "error";
  const running = svc.state === "running" || svc.state === "starting";

  async function act(action: "start" | "stop" | "restart") {
    setBusy(true);
    try {
      await onAction(svc.name, action);
    } finally {
      // Snapshot stream will reflect the real state; clear local busy shortly.
      setTimeout(() => setBusy(false), 400);
    }
  }

  return (
    <div className={`card state-${svc.state}`}>
      <div className="card-head">
        <span className="card-title">{svc.name}</span>
        <span className={`badge ${svc.state}`}>{STATE_LABEL[svc.state] ?? svc.state}</span>
      </div>

      {svc.description && <p className="card-desc">{svc.description}</p>}
      {svc.error && <p className="card-error">{svc.error}</p>}

      {!isError && (
        <div className="card-stats">
          <div>
            <span className="k">CPU</span>
            <span className="v">{running ? pct(svc.cpu_percent) : "—"}</span>
          </div>
          <div>
            <span className="k">RAM</span>
            <span className="v">{running ? bytes(svc.mem_rss) : "—"}</span>
          </div>
          <div>
            <span className="k">Uptime</span>
            <span className="v">{running ? duration(svc.uptime_s) : "—"}</span>
          </div>
        </div>
      )}

      {!isError && (
        <div className="card-actions">
          {running ? (
            <button disabled={busy} onClick={() => act("stop")}>
              Stop
            </button>
          ) : (
            <button className="primary" disabled={busy} onClick={() => act("start")}>
              Start
            </button>
          )}
          <button disabled={busy} onClick={() => act("restart")}>
            Restart
          </button>
          <button className="ghost" onClick={() => onShowLogs(svc.name)}>
            Logs
          </button>
        </div>
      )}

      {svc.last_exit_code != null && !running && !isError && (
        <div className="card-foot muted">last exit code: {svc.last_exit_code}</div>
      )}
    </div>
  );
}
