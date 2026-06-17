export class AuthError extends Error {}

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api${path}`, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    ...opts,
  });
  if (res.status === 401) throw new AuthError("not authenticated");
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  login: (password: string) =>
    request<{ ok: boolean }>("/login", {
      method: "POST",
      body: JSON.stringify({ password }),
    }),
  logout: () => request<{ ok: boolean }>("/logout", { method: "POST" }),
  checkAuth: () => request<{ ok: boolean }>("/auth/check"),
  start: (name: string) =>
    request(`/services/${encodeURIComponent(name)}/start`, { method: "POST" }),
  stop: (name: string) =>
    request(`/services/${encodeURIComponent(name)}/stop`, { method: "POST" }),
  restart: (name: string) =>
    request(`/services/${encodeURIComponent(name)}/restart`, { method: "POST" }),
  rescan: () => request("/services/rescan", { method: "POST" }),
  logs: (name: string, lines = 200) =>
    request<{ lines: string[] }>(
      `/services/${encodeURIComponent(name)}/logs?lines=${lines}`,
    ),
};
