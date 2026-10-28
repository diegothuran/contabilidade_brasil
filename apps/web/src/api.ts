import { accessToken } from "./auth";

const apiUrl = import.meta.env.VITE_API_URL ?? "";
export const TENANT_KEY = "contabil.tenant";

function tenantHeaders(): Record<string, string> {
  const tenantId = sessionStorage.getItem(TENANT_KEY);
  return tenantId ? { "X-Tenant-Id": tenantId } : {};
}

export class ApiError extends Error {
  status: number;
  title: string;

  constructor(status: number, title: string, detail: string) {
    super(detail);
    this.status = status;
    this.title = title;
  }
}

export async function api<T>(path: string, options: { method?: string; body?: unknown } = {}): Promise<T> {
  const headers: Record<string, string> = {
    Authorization: `Bearer ${await accessToken()}`,
    "X-Correlation-Id": crypto.randomUUID(),
    ...tenantHeaders(),
  };
  let body: string | undefined;
  if (options.body !== undefined) {
    body = JSON.stringify(options.body);
    headers["Content-Type"] = "application/json";
    headers["Idempotency-Key"] = crypto.randomUUID();
  }
  const response = await fetch(`${apiUrl}${path}`, {
    method: options.method ?? (body ? "POST" : "GET"),
    headers,
    body,
  });
  const payload = await response.json().catch(() => ({}));
  if (response.status === 401) {
    throw new ApiError(response.status, payload.title ?? "Não autenticado", payload.detail ?? "A sessão expirou.");
  }
  if (!response.ok) {
    throw new ApiError(response.status, payload.title ?? "Erro", payload.detail ?? "A operação falhou.");
  }
  return payload as T;
}

async function authorizedHeaders(): Promise<Record<string, string>> {
  return {
    Authorization: `Bearer ${await accessToken()}`,
    "X-Correlation-Id": crypto.randomUUID(),
    "Idempotency-Key": crypto.randomUUID(),
    ...tenantHeaders(),
  };
}

async function readPayload(response: Response): Promise<unknown> {
  const payload = await response.json().catch(() => ({}));
  if (response.status === 401) {
    const problem = payload as { title?: string; detail?: string };
    throw new ApiError(response.status, problem.title ?? "Não autenticado", problem.detail ?? "A sessão expirou.");
  }
  if (!response.ok) {
    const problem = payload as { title?: string; detail?: string };
    throw new ApiError(response.status, problem.title ?? "Erro", problem.detail ?? "A operação falhou.");
  }
  return payload;
}

export async function uploadDocument(file: File, fields: Record<string, string>): Promise<{ document_id: string }> {
  const body = new FormData();
  body.set("file", file);
  for (const [key, value] of Object.entries(fields)) {
    if (value) {
      body.set(key, value);
    }
  }
  const response = await fetch(`${apiUrl}/v1/documents`, { method: "POST", headers: await authorizedHeaders(), body });
  return (await readPayload(response)) as { document_id: string };
}

export async function uploadRequestFile(requestId: string, file: File): Promise<void> {
  const body = new FormData();
  body.set("file", file);
  const response = await fetch(`${apiUrl}/v1/document-requests/${requestId}/content`, {
    method: "POST",
    headers: await authorizedHeaders(),
    body,
  });
  await readPayload(response);
}

export async function uploadPortalFile(requestId: string, file: File): Promise<void> {
  const body = new FormData();
  body.set("file", file);
  const response = await fetch(`${apiUrl}/v1/portal/document-requests/${requestId}/content`, {
    method: "POST",
    headers: await authorizedHeaders(),
    body,
  });
  await readPayload(response);
}

export async function downloadPortalDocument(documentId: string, fileName: string): Promise<void> {
  const response = await fetch(`${apiUrl}/v1/portal/documents/${documentId}/content`, {
    headers: { Authorization: `Bearer ${await accessToken()}`, ...tenantHeaders() },
  });
  if (!response.ok) {
    await readPayload(response);
    return;
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  anchor.click();
  URL.revokeObjectURL(url);
}

export async function downloadDocument(documentId: string, fileName: string): Promise<void> {
  const response = await fetch(`${apiUrl}/v1/documents/${documentId}/content`, {
    headers: { Authorization: `Bearer ${await accessToken()}`, ...tenantHeaders() },
  });
  if (!response.ok) {
    await readPayload(response);
    return;
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  anchor.click();
  URL.revokeObjectURL(url);
}
