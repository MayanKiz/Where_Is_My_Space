"use client";

import dynamic from "next/dynamic";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

const Stage = dynamic(() => import("react-konva").then((module) => module.Stage), { ssr: false });
const Layer = dynamic(() => import("react-konva").then((module) => module.Layer), { ssr: false });
const Rect = dynamic(() => import("react-konva").then((module) => module.Rect), { ssr: false });
const Text = dynamic(() => import("react-konva").then((module) => module.Text), { ssr: false });
const ImageShape = dynamic(() => import("react-konva").then((module) => module.Image), { ssr: false });

type Seat = {
  id: number;
  label: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  status: "EMPTY" | "OCCUPIED" | "RESERVED";
};
type Analytics = { total: number; occupied: number; empty: number; occupancy_rate: number; sessions_today: number };
type Point = { x: number; y: number };

const apiBase = () => (process.env.NEXT_PUBLIC_WIMS_API_URL || "http://localhost:8000").replace(/\/+$/, "");

function useCameraImage(url: string) {
  const [image, setImage] = useState<HTMLImageElement | undefined>();
  useEffect(() => {
    const next = new window.Image();
    next.onload = () => setImage(next);
    next.src = `${url}?t=${Date.now()}`;
  }, [url]);
  return image;
}

export default function DashboardPage() {
  const [seats, setSeats] = useState<Seat[]>([]);
  const [analytics, setAnalytics] = useState<Analytics>({ total: 0, occupied: 0, empty: 0, occupancy_rate: 0, sessions_today: 0 });
  const [available, setAvailable] = useState<string[]>([]);
  const [frameUrl, setFrameUrl] = useState(`${apiBase()}/api/camera/frame`);
  const [drawing, setDrawing] = useState<Point | null>(null);
  const [drafts, setDrafts] = useState<Seat[]>([]);
  const [label, setLabel] = useState("");
  const [message, setMessage] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  const image = useCameraImage(frameUrl);
  const width = 900;
  const height = 510;
  const scaleX = image ? width / image.naturalWidth : 1;
  const scaleY = image ? height / image.naturalHeight : 1;

  const refresh = async () => {
    const [seatResponse, analyticsResponse, availableResponse] = await Promise.all([
      fetch(`${apiBase()}/api/seats`, { cache: "no-store" }),
      fetch(`${apiBase()}/api/analytics`, { cache: "no-store" }),
      fetch(`${apiBase()}/api/seats/available`, { cache: "no-store" }),
    ]);
    if (!seatResponse.ok || !analyticsResponse.ok || !availableResponse.ok) throw new Error("Could not load seat data.");
    const seatPayload = await seatResponse.json() as { seats: Seat[] };
    setSeats(seatPayload.seats);
    setDrafts(seatPayload.seats);
    setAnalytics(await analyticsResponse.json() as Analytics);
    setAvailable(await availableResponse.json() as string[]);
  };

  useEffect(() => {
    void refresh().catch((error: unknown) => setMessage(error instanceof Error ? error.message : "API unavailable."));
    const socket = new WebSocket(`${apiBase().replace(/^http/, "ws")}/ws/seats`);
    socket.onmessage = (event) => {
      const payload = JSON.parse(event.data) as { seats?: Seat[]; analytics?: Analytics };
      if (payload.seats) {
        setSeats(payload.seats);
        setDrafts(payload.seats);
      }
      if (payload.analytics) setAnalytics(payload.analytics);
      if (payload.seats) {
        setAvailable(payload.seats.filter((seat) => seat.status === "EMPTY").map((seat) => seat.label));
        setFrameUrl(`${apiBase()}/api/camera/frame`);
      }
    };
    return () => socket.close();
  }, []);

  const displayedSeats = useMemo(() => drafts.length ? drafts : seats, [drafts, seats]);

  function pointerPosition(event: { target: { getStage: () => { getPointerPosition: () => Point | null } | null } }) {
    const stage = event.target.getStage();
    const point = stage?.getPointerPosition();
    return point ? { x: point.x / scaleX, y: point.y / scaleY } : null;
  }

  function handlePointerDown(event: { target: { getStage: () => unknown } }) {
    const point = pointerPosition(event as never);
    if (point) setDrawing(point);
  }

  function handlePointerUp(event: { target: { getStage: () => unknown } }) {
    if (!drawing) return;
    const point = pointerPosition(event as never);
    if (!point) return;
    const x1 = Math.min(drawing.x, point.x);
    const y1 = Math.min(drawing.y, point.y);
    const x2 = Math.max(drawing.x, point.x);
    const y2 = Math.max(drawing.y, point.y);
    if (x2 - x1 > 8 && y2 - y1 > 8) {
      const nextLabel = label.trim() || `S${String(drafts.length + 1).padStart(2, "0")}`;
      setDrafts((current) => [...current, { id: -Date.now(), label: nextLabel, x1, y1, x2, y2, status: "EMPTY" }]);
      setLabel("");
    }
    setDrawing(null);
  }

  async function saveMap(event: FormEvent) {
    event.preventDefault();
    const response = await fetch(`${apiBase()}/api/seats/map`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ seats: drafts.map(({ label: seatLabel, x1, y1, x2, y2, status }) => ({ label: seatLabel, x1, y1, x2, y2, status })) }),
    });
    if (!response.ok) {
      setMessage("Could not save seat zones.");
      return;
    }
    setMessage("Seat map saved.");
    await refresh();
  }

  async function uploadFrame(file: File) {
    const body = new FormData();
    body.append("file", file);
    const response = await fetch(`${apiBase()}/api/camera/frame`, { method: "POST", body });
    if (!response.ok) {
      setMessage("Could not upload the CCTV frame.");
      return;
    }
    setFrameUrl(`${apiBase()}/api/camera/frame`);
    setMessage("CCTV frame updated.");
  }

  return (
    <main className="seat-dashboard">
      <header className="seat-header">
        <div>
          <p className="seat-kicker">WIMS · LIBRARY OPERATIONS</p>
          <h1>Where is my space?</h1>
          <p className="seat-muted">Live seat occupancy, mapped directly on your CCTV view.</p>
        </div>
        <button className="seat-button" onClick={() => fileInput.current?.click()}>Upload CCTV frame</button>
        <input ref={fileInput} hidden type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) void uploadFrame(file);
        }} />
      </header>

      <section className="seat-metrics">
        <div><span>Total seats</span><strong>{analytics.total}</strong></div>
        <div className="metric-empty"><span>Khali seats</span><strong>{analytics.empty}</strong></div>
        <div className="metric-occupied"><span>Occupied</span><strong>{analytics.occupied}</strong></div>
        <div><span>Occupancy rate</span><strong>{Math.round(analytics.occupancy_rate * 100)}%</strong></div>
      </section>

      <section className="seat-layout">
        <article className="seat-card mapping-card">
          <div className="seat-card-heading"><div><h2>Seat mapping</h2><p>Draw a rectangle over each seat. Add a label before drawing or use automatic S01, S02 labels.</p></div><span className="seat-live">● LIVE</span></div>
          <div className="seat-canvas">
            {image ? (
              <Stage width={width} height={height} onMouseDown={handlePointerDown} onMouseUp={handlePointerUp} onTouchStart={handlePointerDown} onTouchEnd={handlePointerUp}>
                <Layer>
                  <ImageShape image={image} width={width} height={height} />
                  {displayedSeats.map((seat) => <Rect key={`${seat.id}-${seat.label}`} x={seat.x1 * scaleX} y={seat.y1 * scaleY} width={(seat.x2 - seat.x1) * scaleX} height={(seat.y2 - seat.y1) * scaleY} stroke={seat.status === "OCCUPIED" ? "#ef4444" : "#22c55e"} strokeWidth={2} fill={seat.status === "OCCUPIED" ? "rgba(239,68,68,.18)" : "rgba(34,197,94,.14)"} />)}
                  {displayedSeats.map((seat) => <Text key={`text-${seat.id}-${seat.label}`} x={seat.x1 * scaleX + 5} y={seat.y1 * scaleY + 5} text={seat.label} fill="#ffffff" fontSize={14} fontStyle="bold" shadowColor="#000000" shadowBlur={3} />)}
                </Layer>
              </Stage>
            ) : <div className="seat-empty-canvas">Upload a CCTV frame to start mapping seats.</div>}
          </div>
          <form className="seat-map-actions" onSubmit={(event) => void saveMap(event)}>
            <input value={label} onChange={(event) => setLabel(event.target.value)} placeholder="Next label e.g. S01" aria-label="Seat label" />
            <button className="seat-button" type="submit" disabled={!drafts.length}>Save seat map</button>
          </form>
          {message && <p className="seat-message">{message}</p>}
        </article>

        <aside className="seat-card available-card">
          <div className="seat-card-heading"><div><h2>Khali Seats</h2><p>Available right now</p></div><span className="available-count">{available.length}</span></div>
          <div className="available-list">{available.length ? available.map((seat) => <span key={seat}>{seat}</span>) : <p className="seat-muted">No empty seats right now.</p>}</div>
          <div className="seat-legend"><span><i className="legend-green" /> Khali</span><span><i className="legend-red" /> Bhari hui</span></div>
          <p className="seat-session-note">{analytics.sessions_today} occupancy sessions today</p>
        </aside>
      </section>

      <section className="seat-card floor-card">
        <div className="seat-card-heading"><div><h2>Floor plan</h2><p>Click a seat to see its current status.</p></div></div>
        <div className="floor-grid">{seats.map((seat) => <button key={seat.id} className={`floor-seat ${seat.status.toLowerCase()}`} title={`${seat.label}: ${seat.status}`}>{seat.label}</button>)}</div>
      </section>
    </main>
  );
}
