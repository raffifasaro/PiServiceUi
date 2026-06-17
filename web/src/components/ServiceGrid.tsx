import type { ServiceInfo } from "../types";
import { ServiceCard } from "./ServiceCard";

export function ServiceGrid({
  services,
  onAction,
  onShowLogs,
}: {
  services: ServiceInfo[];
  onAction: (name: string, action: "start" | "stop" | "restart") => void;
  onShowLogs: (name: string) => void;
}) {
  if (services.length === 0) {
    return (
      <div className="empty">
        <p>No services found.</p>
        <p className="muted">
          Drop a folder with a <code>service.yaml</code> into <code>services/</code> and
          click <strong>Rescan</strong>.
        </p>
      </div>
    );
  }

  return (
    <div className="grid">
      {services.map((svc) => (
        <ServiceCard
          key={svc.name}
          svc={svc}
          onAction={onAction}
          onShowLogs={onShowLogs}
        />
      ))}
    </div>
  );
}
