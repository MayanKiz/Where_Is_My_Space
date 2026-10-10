export type UploadJobResponse = {
  id: string;
  status: "received" | "queued" | "processing" | "completed" | "failed" | "expired" | string;
  progress_percent: number;
  original_filename: string;
  size_bytes: number;
  created_at: string;
  expires_at?: string;
  message?: string;
};

export type JobStatusResponse = {
  id: string;
  status: string;
  progress_percent: number;
  original_filename: string;
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

export function uploadVideo(
  file: File,
  onProgress: (percent: number) => void,
): Promise<UploadJobResponse> {
  const baseUrl = getWimsApiUrl();
  if (!baseUrl) {
    return Promise.reject(
      new Error("The WIMS API URL is not configured. This file has not been uploaded."),
    );
  }

  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", `${baseUrl}/v1/jobs/upload`);
    request.responseType = "json";
    request.timeout = 5 * 60 * 1000;

    request.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        onProgress(Math.min(100, Math.round((event.loaded / event.total) * 100)));
      }
    };

    request.onload = () => {
      const payload = request.response as UploadJobResponse | ApiErrorPayload | null;
      if (request.status >= 200 && request.status < 300 && payload && "id" in payload) {
        resolve(payload);
        return;
      }
      const detail = payload && "detail" in payload ? payload.detail : undefined;
      const message =
        typeof detail === "string"
          ? detail
          : detail?.message || `Upload failed (HTTP ${request.status}).`;
      reject(new Error(message));
    };

    request.onerror = () => reject(new Error("Could not reach the WIMS API. Check the server URL and connection."));
    request.ontimeout = () => reject(new Error("Upload timed out. Try a smaller MP4 or check the server."));
    request.onabort = () => reject(new Error("Upload cancelled."));
    const body = new FormData();
    body.append("file", file, file.name);
    request.send(body);
  });
}

export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  const baseUrl = getWimsApiUrl();
  if (!baseUrl) throw new Error("The WIMS API URL is not configured.");

  const response = await fetch(`${baseUrl}/v1/jobs/${encodeURIComponent(jobId)}`, {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  const payload = (await response.json().catch(() => ({}))) as JobStatusResponse | ApiErrorPayload;
  if (!response.ok || !("id" in payload)) {
    const detail = "detail" in payload ? payload.detail : undefined;
    throw new Error(typeof detail === "string" ? detail : "Could not retrieve the processing status.");
  }
  return payload;
}
