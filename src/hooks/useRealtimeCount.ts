import { useState, useEffect } from "react";

const WS_URL = import.meta.env.VITE_WS_URL ?? "ws://localhost:8000";

export interface RegionOut {
  id: number;
  name: string;
  camera_id: string;
  capacity: number;
  current_count: number;
  reserved_count: number;
  occupancy_pct: number;
  status: "free" | "moderate" | "full" | "offline";
  camera_online: boolean;
  last_updated: string | null;
  description: string | null;
  section: string;
}

export function useRealtimeCount() {
  const [regions, setRegions] = useState<RegionOut[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    let ws: WebSocket;
    let retryTimeout: ReturnType<typeof setTimeout>;

    const connect = () => {
      try {
        ws = new WebSocket(`${WS_URL}/ws/dashboard`);
        ws.onopen = () => setConnected(true);
        ws.onmessage = (e) => {
          try {
            const data = JSON.parse(e.data) as { regions: RegionOut[] };
            if (Array.isArray(data.regions)) setRegions(data.regions);
          } catch {
            // ignore malformed messages
          }
        };
        ws.onclose = () => {
          setConnected(false);
          retryTimeout = setTimeout(connect, 3000);
        };
        ws.onerror = () => ws.close();
      } catch {
        retryTimeout = setTimeout(connect, 3000);
      }
    };

    connect();
    return () => {
      clearTimeout(retryTimeout);
      ws?.close();
    };
  }, []);

  return { regions, connected };
}
