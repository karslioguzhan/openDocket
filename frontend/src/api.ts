import i18n from "./i18n";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { ...(options.headers as Record<string, string>) };
  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  const resp = await fetch(`/api${path}`, {
    ...options,
    credentials: "include",
    headers,
  });
  if (resp.status === 401) {
    window.dispatchEvent(new CustomEvent("opendocket:unauthorized"));
  }
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* ignore */
    }
    throw new ApiError(resp.status, detail);
  }
  if (resp.status === 204) return undefined as T;
  return resp.json() as Promise<T>;
}

export async function login(email: string, password: string): Promise<void> {
  const form = new URLSearchParams();
  form.append("username", email);
  form.append("password", password);
  const resp = await fetch("/api/auth/login", {
    method: "POST",
    body: form,
    credentials: "include",
  });
  if (resp.status === 204) return;
  throw new ApiError(resp.status, i18n.t("login.failed"));
}

export async function logout(): Promise<void> {
  await api<void>("/auth/logout", { method: "POST" });
}
