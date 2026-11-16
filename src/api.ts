const BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

function authHeaders(token: string) {
  return { "Content-Type": "application/json", Authorization: `Bearer ${token}` };
}

type ValidationItem = { loc?: (string | number)[]; msg?: string };

async function checkOk(r: Response) {
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    const detail = (body as { detail?: string | ValidationItem[] }).detail;
    // FastAPI validation errors (422) come back as a list — make them readable.
    if (Array.isArray(detail)) {
      const msg = detail
        .map(d => `${d.loc?.[d.loc.length - 1] ?? "field"}: ${d.msg ?? "invalid"}`)
        .join("; ");
      throw new Error(msg || `HTTP ${r.status}`);
    }
    // Expired/invalid JWT on an admin action (login errors keep their own message).
    if (r.status === 401 && detail === "Could not validate credentials") {
      throw new Error("Session expired — please log in again");
    }
    throw new Error(detail ?? `HTTP ${r.status}`);
  }
  return r.json();
}

export const getLatestCounts = () =>
  fetch(`${BASE}/count/latest`).then(checkOk);

export const getRegions = () =>
  fetch(`${BASE}/regions`).then(checkOk);

export const createRegion = (data: object, tok: string) =>
  fetch(`${BASE}/regions`, {
    method: "POST",
    headers: authHeaders(tok),
    body: JSON.stringify(data),
  }).then(checkOk);

export const updateRegion = (id: number, data: object, tok: string) =>
  fetch(`${BASE}/regions/${id}`, {
    method: "PUT",
    headers: authHeaders(tok),
    body: JSON.stringify(data),
  }).then(checkOk);

export const deleteRegion = (id: number, tok: string) =>
  fetch(`${BASE}/regions/${id}`, {
    method: "DELETE",
    headers: authHeaders(tok),
  }).then(checkOk);

export const login = (username: string, password: string) =>
  fetch(`${BASE}/admin/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  }).then(checkOk);
