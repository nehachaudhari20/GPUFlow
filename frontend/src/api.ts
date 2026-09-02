export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export async function apiPost<T>(url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data.detail || data.message || res.statusText;
    throw new ApiError(typeof detail === 'string' ? detail : JSON.stringify(detail), res.status);
  }
  return data as T;
}

export interface SchedulingDecisionResponse {
  decision?: {
    job_id: string;
    allocation_success: boolean;
    kept_queued?: boolean;
    selected_node?: string | null;
    reason?: string | null;
  } | null;
  message?: string;
  decisions?: SchedulingDecisionResponse['decision'][];
  count?: number;
}
