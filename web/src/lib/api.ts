export type UploadSourceType = "phone_camera" | "screen_share" | "uploaded_video";

export type CaptureSourceType = UploadSourceType | "rtsp_camera";

export type CaptureSource = {
  id: string;
  name: string;
  source_type: CaptureSourceType;
  status: string;
  device_label: string | null;
  metadata: Record<string, unknown>;
  last_seen_at: string | null;
  created_at: string;
  updated_at: string;
};

export type NewCaptureSource = {
  name: string;
  source_type: CaptureSourceType;
  device_label?: string;
  rtsp_url?: string;
  location_id?: string;
  zone_id?: string;
};

export type UploadJobResponse = {
  id: string;
  source_id?: string | null;
  source_type: string;
  status: string;
  progress_percent: number;
  original_filename: string;
  mime_type?: string;
  size_bytes: number;
  created_at: string;
  expires_at?: string;
  message?: string;
};

export type JobStatusResponse = {
  id: string;
  source_id?: string | null;
  source_type: string;
  status: string;
  progress_percent: number;
  original_filename: string;
  mime_type?: string | null;
  size_bytes: number;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  result_summary?: Record<string, unknown>;
  error_code?: string | null;
};

type ApiErrorPayload = { detail?: string | { message?: string; code?: string } };

export function getWimsApiUrl(): string | null {
  const value = process.env.NEXT_PUBLIC_WIMS_API_URL?.trim();
  return value ? value.replace(/\/+$/, "") : null;
}

function captureHeaders(accessCode: string): Record<string, string> {
  return { "X-WIMS-Capture-Key": accessCode.trim() };
}

async function apiErrorMessage(response: Response): Promise<string> {
  const payload = (await response.json().catch(() => ({}))) as ApiErrorPayload;
  const detail = payload.detail;
  return typeof detail === "string"
    ? detail
    : detail?.message || `WIMS API request failed (HTTP ${response.status}).`;
}

export async function listCaptureSources(accessCode: string): Promise<CaptureSource[]> {
  const baseUrl = getWimsApiUrl();
  if (!baseUrl) throw new Error("The WIMS API URL is not configured.");
  const response = await fetch(`${baseUrl}/v1/sources`, {
    headers: { ...captureHeaders(accessCode), Accept: "application/json" },
    cache: "no-store",
  });
  if (!response.ok) throw new Error(await apiErrorMessage(response));
  const payload = (await response.json()) as { sources?: CaptureSource[] };
  return payload.sources ?? [];
}

export async function registerCaptureSource(
  input: NewCaptureSource,
  accessCode: string,
): Promise<CaptureSource> {
  const baseUrl = getWimsApiUrl();
  if (!baseUrl) throw new Error("The WIMS API URL is not configured.");
  const response = await fetch(`${baseUrl}/v1/sources`, {
    method: "POST",
    headers: {
      ...captureHeaders(accessCode),
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(input),
  });
  if (!response.ok) throw new Error(await apiErrorMessage(response));
  return (await response.json()) as CaptureSource;
}

export function uploadVideo(
  file: File,
  sourceType: UploadSourceType,
  sourceId: string,
  accessCode: string,
  onProgress: (percent: number) => void,
  zoneId?: string | null,
): Promise<UploadJobResponse> {
  const baseUrl = getWimsApiUrl();
  if (!baseUrl) {
    return Promise.reject(new Error("The WIMS API URL is not configured. This file has not been uploaded."));
  }

  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", `${baseUrl}/v1/jobs/upload`);
    request.setRequestHeader("X-WIMS-Capture-Key", accessCode.trim());
    request.responseType = "json";
    request.timeout = 5 * 60 * 1000;

    request.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.min(100, Math.round((event.loaded / event.total) * 100)));
    };

    request.onload = () => {
      const payload = request.response as UploadJobResponse | ApiErrorPayload | null;
      if (request.status >= 200 && request.status < 300 && payload && "id" in payload) {
        resolve(payload);
        return;
      }
      const detail = payload && "detail" in payload ? payload.detail : undefined;
      const message = typeof detail === "string"
        ? detail
        : detail?.message || `Upload failed (HTTP ${request.status}).`;
      reject(new Error(message));
    };

    request.onerror = () => reject(new Error("Could not reach the WIMS API. Check its URL and connection."));
    request.ontimeout = () => reject(new Error("Upload timed out. Try a smaller clip or check the server."));
    request.onabort = () => reject(new Error("Upload cancelled."));
    const body = new FormData();
    body.append("file", file, file.name);
    body.append("source_type", sourceType);
    body.append("source_id", sourceId);
    if (zoneId) body.append("zone_id", zoneId);
    request.send(body);
  });
}

export async function getJobStatus(jobId: string, accessCode: string): Promise<JobStatusResponse> {
  const baseUrl = getWimsApiUrl();
  if (!baseUrl) throw new Error("The WIMS API URL is not configured.");

  const response = await fetch(`${baseUrl}/v1/jobs/${encodeURIComponent(jobId)}`, {
    headers: { ...captureHeaders(accessCode), Accept: "application/json" },
    cache: "no-store",
  });
  if (!response.ok) throw new Error(await apiErrorMessage(response));
  return (await response.json()) as JobStatusResponse;
}

export type WimsZone = {
  id: string;
  location_id: string;
  slug: string;
  name: string;
  description: string | null;
  capacity: number;
  polygon: number[][] | null;
  is_active: boolean;
  is_public: boolean;
  created_at: string;
  locations?: { name: string; campus_name?: string | null } | null;
};

export type OccupancyZone = {
  id: string;
  name: string;
  slug: string | null;
  description: string | null;
  capacity: number;
  location_id: string;
  location_name: string | null;
  observed_at: string | null;
  confidence: number | null;
  has_live_data: boolean;
  status: string;
  available_count: number | null;
};

export type OccupancyFeed = {
  generated_at: string;
  zones: OccupancyZone[];
};

export type WimsHealth = {
  status: string;
  service: string;
  supabase_credentials_configured: boolean;
  capture_access_configured: boolean;
  rtsp_encryption_configured: boolean;
  video_processing: string;
};

export type AssistantReply = {
  answer: string;
  provider: "amazon-bedrock" | "local-fallback";
  zones_considered: number;
};

export async function askSpaceAssistant(
  message: string,
  history: { role: "user" | "assistant"; content: string }[] = [],
): Promise<AssistantReply> {
  const baseUrl = getWimsApiUrl();
  if (!baseUrl) throw new Error("The WIMS API URL is not configured.");
  const response = await fetch(`${baseUrl}/v1/assistant`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ message, history: history.slice(-8) }),
  });
  if (!response.ok) throw new Error(await apiErrorMessage(response));
  return (await response.json()) as AssistantReply;
}

export async function fetchHealth(): Promise<WimsHealth> {
  const baseUrl = getWimsApiUrl();
  if (!baseUrl) throw new Error("The WIMS API URL is not configured.");
  const response = await fetch(`${baseUrl}/health`, { cache: "no-store" });
  if (!response.ok) throw new Error(`WIMS API health check failed (HTTP ${response.status}).`);
  return (await response.json()) as WimsHealth;
}

export async function fetchLiveOccupancy(): Promise<OccupancyFeed> {
  const baseUrl = getWimsApiUrl();
  if (!baseUrl) throw new Error("The WIMS API URL is not configured.");
  const response = await fetch(`${baseUrl}/v1/occupancy`, {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  if (!response.ok) throw new Error(await apiErrorMessage(response));
  return (await response.json()) as OccupancyFeed;
}

export async function fetchZones(): Promise<WimsZone[]> {
  const baseUrl = getWimsApiUrl();
  if (!baseUrl) throw new Error("The WIMS API URL is not configured.");
  const response = await fetch(`${baseUrl}/v1/zones`, {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  if (!response.ok) throw new Error(await apiErrorMessage(response));
  const payload = (await response.json()) as { zones?: WimsZone[] };
  return payload.zones ?? [];
}

/** Downloads the annotated AI preview (bounding boxes) as a local object URL. */
export async function fetchJobPreviewUrl(jobId: string, accessCode: string): Promise<string> {
  const baseUrl = getWimsApiUrl();
  if (!baseUrl) throw new Error("The WIMS API URL is not configured.");
  const response = await fetch(`${baseUrl}/v1/jobs/${encodeURIComponent(jobId)}/preview`, {
    headers: captureHeaders(accessCode),
    cache: "no-store",
  });
  if (!response.ok) throw new Error(await apiErrorMessage(response));
  const blob = await response.blob();
  return URL.createObjectURL(blob);
}
