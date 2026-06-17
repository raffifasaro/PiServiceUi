export type ServiceState =
  | "stopped"
  | "starting"
  | "running"
  | "stopping"
  | "crashed"
  | "error";

export interface ServiceInfo {
  name: string;
  description: string;
  state: ServiceState;
  pid: number | null;
  restart: string | null;
  autostart: boolean;
  uptime_s: number;
  cpu_percent: number | null;
  mem_rss: number | null;
  last_exit_code: number | null;
  error: string | null;
}

export interface HostMetrics {
  cpu_percent: number;
  cpu_count: number;
  mem_used: number;
  mem_total: number;
  mem_percent: number;
  disk_used: number;
  disk_total: number;
  disk_percent: number;
  load: number[];
  temp_c: number | null;
  uptime_s: number;
}

export interface Snapshot {
  host: HostMetrics;
  services: ServiceInfo[];
}
