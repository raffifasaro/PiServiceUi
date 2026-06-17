import type { HostMetrics } from "../types";
import { bytes, duration } from "../format";

function Meter({
  label,
  value,
  detail,
}: {
  label: string;
  value: number | null;
  detail: string;
}) {
  const pct = Math.max(0, Math.min(100, value ?? 0));
  const tone = pct > 85 ? "hot" : pct > 60 ? "warm" : "cool";
  return (
    <div className="meter">
      <div className="meter-head">
        <span>{label}</span>
        <span className="muted">{detail}</span>
      </div>
      <div className="bar">
        <div className={`bar-fill ${tone}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export function Sidebar({
  host,
  connected,
}: {
  host: HostMetrics | null;
  connected: boolean;
}) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="logo">◍</span>
        <span>PiServiceUi</span>
      </div>

      <div className="metrics">
        <h2>Host</h2>
        {!host ? (
          <p className="muted">{connected ? "…" : "no data"}</p>
        ) : (
          <>
            <Meter
              label="CPU"
              value={host.cpu_percent}
              detail={`${host.cpu_percent.toFixed(0)}% · ${host.cpu_count} core${
                host.cpu_count > 1 ? "s" : ""
              }`}
            />
            <Meter
              label="Memory"
              value={host.mem_percent}
              detail={`${bytes(host.mem_used)} / ${bytes(host.mem_total)}`}
            />
            <Meter
              label="Disk"
              value={host.disk_percent}
              detail={`${bytes(host.disk_used)} / ${bytes(host.disk_total)}`}
            />

            <div className="stat-list">
              <div className="stat">
                <span>Temp</span>
                <span>{host.temp_c == null ? "—" : `${host.temp_c.toFixed(1)} °C`}</span>
              </div>
              <div className="stat">
                <span>Load</span>
                <span>
                  {host.load.map((l) => l.toFixed(2)).join(" · ") || "—"}
                </span>
              </div>
              <div className="stat">
                <span>Uptime</span>
                <span>{duration(host.uptime_s)}</span>
              </div>
            </div>
          </>
        )}
      </div>
    </aside>
  );
}
