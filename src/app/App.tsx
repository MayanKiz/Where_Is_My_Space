/* MARKER-MAKE-KIT-INVOKED */
import { useState, useEffect, useCallback } from "react";
import { Region } from "./components/types";
import { RegionCard } from "./components/RegionCard";
import { StudentTopNav, AdminTopNav } from "./components/TopNavBar";
import { SmartSuggestionStrip } from "./components/SmartSuggestionStrip";
import { AdminLoginForm } from "./components/AdminLoginForm";
import { AdminPanel } from "./components/AdminPanel";
import { useRealtimeCount, RegionOut } from "../hooks/useRealtimeCount";
import { useAuth } from "../hooks/useAuth";

type View = "dashboard" | "login" | "admin";

// When a real backend is configured, never show simulated numbers — only real
// data or an honest "connecting / offline" state. Simulation is for local dev only.
const IS_LIVE = Boolean(import.meta.env.VITE_API_BASE_URL);

const SEED: Region[] = [
  {
    id: "r1",
    name: "Entrance / Lobby",
    count: 12, reserved: 3,
    capacity: 40, status: "free",
    camId: "cam_01", camOnline: true, lastUpdated: "2s ago",
    locationNotes: "Ground floor main entrance. Camera mounted above main doors.",
    section: "library",
  },
  {
    id: "r2",
    name: "Main Reading Hall",
    count: 62, reserved: 5,
    capacity: 80, status: "moderate",
    camId: "cam_02", camOnline: true, lastUpdated: "1s ago",
    locationNotes: "Central hall, rows A–H. High-ceiling area with skylight.",
    section: "library",
  },
  {
    id: "r3",
    name: "Upper Floor / Quiet Zone",
    count: 28, reserved: 2,
    capacity: 30, status: "full",
    camId: "cam_03", camOnline: true, lastUpdated: "4s ago",
    locationNotes: "Strict silence policy. Staircase access only.",
    section: "library",
  },
  {
    id: "r4",
    name: "Collaborative / Group Study",
    count: 8, reserved: 4,
    capacity: 25, status: "free",
    camId: "cam_04", camOnline: true, lastUpdated: "2s ago",
    locationNotes: "West wing, round tables. Audio permitted at low volumes.",
    section: "library",
  },
];

// CS-IT Canteen placeholder — shown when no live canteen regions exist in backend DB yet
const GYM_PLACEHOLDER: Region[] = [
  {
    id: "g1",
    name: "Main CS-IT Canteen Floor",
    count: 0, reserved: 0,
    capacity: 50, status: "offline",
    camId: "cam_canteen_01", camOnline: false, lastUpdated: "not connected",
    locationNotes: "Add canteen region via Admin Panel to go live.",
    section: "canteen",
  },
];

// LT placeholder — shown when no live LT regions exist in backend DB yet
const BADMINTON_PLACEHOLDER: Region[] = [
  {
    id: "b1",
    name: "LT Block",
    count: 0, reserved: 0,
    capacity: 24, status: "offline",
    camId: "cam_lt_01", camOnline: false, lastUpdated: "not connected",
    locationNotes: "Add lt region via Admin Panel to go live.",
    section: "lt",
  },
];

// Shown on the live site until the WebSocket delivers real data.
const CONNECTING_SEED: Region[] = SEED.map(r => ({
  ...r,
  count: 0,
  reserved: 0,
  status: "offline" as const,
  camOnline: false,
  lastUpdated: "connecting…",
}));

function computeStatus(count: number, capacity: number): Region["status"] {
  const p = count / capacity;
  if (p >= 0.75) return "full";
  if (p >= 0.40) return "moderate";
  return "free";
}

function fmtFull(d: Date) {
  return d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function formatRelativeTime(isoString: string): string {
  // Backend returns naive UTC datetimes (no Z suffix) — force UTC so JS doesn't
  // misread them as local time (IST = UTC+5:30 causes "5h ago" bug)
  const utc = isoString.endsWith("Z") || isoString.includes("+") ? isoString : isoString + "Z";
  const diff = Math.floor((Date.now() - new Date(utc).getTime()) / 1000);
  if (diff < 0) return "just now";
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

function fromRegionOut(r: RegionOut): Region {
  return {
    id: String(r.id),
    name: r.name,
    count: r.current_count,
    reserved: r.reserved_count ?? 0,
    capacity: r.capacity,
    status: r.status,
    camId: r.camera_id,
    camOnline: r.camera_online,
    lastUpdated: r.last_updated ? formatRelativeTime(r.last_updated) : "never",
    locationNotes: r.description ?? "",
    section: (r.section === "canteen" ? "canteen" : r.section === "lt" ? "lt" : "library"),
  };
}

function useIsMobile() {
  const [mobile, setMobile] = useState(() => window.innerWidth < 640);
  useEffect(() => {
    const fn = () => setMobile(window.innerWidth < 640);
    window.addEventListener("resize", fn);
    return () => window.removeEventListener("resize", fn);
  }, []);
  return mobile;
}

function SectionHeader({ label, count, accent }: { label: string; count: number; accent: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "16px" }}>
      <span style={{
        fontFamily: "'DM Sans', sans-serif",
        fontWeight: 700,
        fontSize: "13px",
        color: accent,
        textTransform: "uppercase",
        letterSpacing: "0.1em",
      }}>
        {label}
      </span>
      <span style={{
        fontFamily: "'IBM Plex Mono', monospace",
        fontSize: "11px",
        color: "#334155",
        backgroundColor: "#1A1D27",
        padding: "2px 8px",
        borderRadius: "4px",
        border: "1px solid #2A2E42",
      }}>
        {count} zone{count !== 1 ? "s" : ""}
      </span>
      <div style={{ flex: 1, height: "1px", backgroundColor: "#1E2030" }} />
    </div>
  );
}

export default function App() {
  const { regions: wsRegions, connected } = useRealtimeCount();
  const auth = useAuth();
  const [view, setView] = useState<View>("dashboard");
  const [mockRegions, setMockRegions] = useState<Region[]>(SEED);
  const [liveRegions, setLiveRegions] = useState<Region[]>([]);
  const [refreshTime, setRefreshTime] = useState(fmtFull(new Date()));
  const [secsSince, setSecsSince] = useState(0);
  const [offlineMode, setOfflineMode] = useState(false);
  const isMobile = useIsMobile();

  // Refresh live regions from WebSocket every second (keeps "Xs ago" timestamps fresh)
  useEffect(() => {
    if (!connected || wsRegions.length === 0) {
      setLiveRegions([]);
      return;
    }
    setLiveRegions(wsRegions.map(fromRegionOut));
    setRefreshTime(fmtFull(new Date()));
    setSecsSince(0);
    const id = setInterval(() => setLiveRegions(wsRegions.map(fromRegionOut)), 1000);
    return () => clearInterval(id);
  }, [connected, wsRegions]);

  // Mock simulation — local dev only (no backend configured)
  const simulate = useCallback(() => {
    if (connected || IS_LIVE) return;
    setMockRegions(prev =>
      prev.map(r => {
        if (offlineMode && r.id === "r4") return r;
        const delta = Math.floor(Math.random() * 5) - 2;
        const c = Math.max(0, Math.min(r.capacity, r.count + delta));
        return { ...r, count: c, status: computeStatus(c, r.capacity) };
      })
    );
    setRefreshTime(fmtFull(new Date()));
    setSecsSince(0);
  }, [connected, offlineMode]);

  useEffect(() => {
    const sim = connected || IS_LIVE ? undefined : setInterval(simulate, 5000);
    const counter = setInterval(() => setSecsSince(s => s + 1), 1000);
    return () => {
      if (sim) clearInterval(sim);
      clearInterval(counter);
    };
  }, [simulate, connected]);

  const agoLabel = secsSince < 60
    ? `${secsSince}s ago`
    : `${Math.floor(secsSince / 60)}m ago`;

  // Real data when connected. On the live site, an honest offline placeholder
  // while connecting; mock simulation only in local dev.
  const baseRegions = connected && liveRegions.length > 0
    ? liveRegions
    : IS_LIVE ? CONNECTING_SEED : mockRegions;

  const displayRegions = baseRegions.map(r =>
    offlineMode && r.id === "r4"
      ? { ...r, status: "offline" as const, camOnline: false, lastUpdated: "8:47 AM" }
      : r
  );

  const libraryRegions = displayRegions.filter(r => r.section === "library");
  const liveCanteenRegions = displayRegions.filter(r => r.section === "canteen");
  const liveLtRegions = displayRegions.filter(r => r.section === "lt");
  // Show live data if available, else show placeholder so each section always appears
  const canteenRegions = liveCanteenRegions.length > 0 ? liveCanteenRegions : GYM_PLACEHOLDER;
  const ltRegions = liveLtRegions.length > 0 ? liveLtRegions : BADMINTON_PLACEHOLDER;

  const handleLoginAttempt = useCallback(async (u: string, p: string) => {
    await auth.login(u, p);
    setView("admin");
  }, [auth]);

  const handleLogout = useCallback(() => {
    auth.logout();
    setView("dashboard");
  }, [auth]);

  return (
    <div style={{
      width: "100%",
      height: "100%",
      backgroundColor: "#0F1117",
      display: "flex",
      flexDirection: "column",
      fontFamily: "'DM Sans', sans-serif",
      overflow: "hidden",
    }}>
      <style>{`
        @keyframes pulse-dot {
          0%, 100% { box-shadow: 0 0 0 0px rgba(34,197,94,0.5); }
          60%       { box-shadow: 0 0 0 5px rgba(34,197,94,0.07); }
        }
        @keyframes fadeUp {
          from { opacity: 0; transform: translateY(10px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        * { box-sizing: border-box; }
        input::placeholder, textarea::placeholder { color: #334155; }
        input[type=number]::-webkit-inner-spin-button { opacity: 0.4; }
        ::-webkit-scrollbar { width: 5px; height: 5px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #2A2E42; border-radius: 4px; }
      `}</style>

      {/* ── ADMIN LOGIN ─────────────────────────────────── */}
      {view === "login" && (
        <div style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: "20px",
          padding: "24px",
          overflow: "auto",
          animation: "fadeUp 0.25s ease",
        }}>
          <div style={{ textAlign: "center", marginBottom: "4px" }}>
            <div style={{ fontFamily: "'DM Sans', sans-serif", fontWeight: 700, fontSize: "24px", color: "#F1F5F9", marginBottom: "6px" }}>
              AKGEC
            </div>
            <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "11px", color: "#475569", letterSpacing: "0.14em", textTransform: "uppercase" }}>
              AKGEC Occupancy Management System
            </div>
            <div style={{ margin: "16px auto 0", width: "40px", height: "1px", backgroundColor: "#2A2E42" }} />
          </div>

          <AdminLoginForm onLoginAttempt={handleLoginAttempt} />

          <button
            onClick={() => setView("dashboard")}
            style={{
              background: "none",
              border: "none",
              color: "#334155",
              fontFamily: "'DM Sans', sans-serif",
              fontSize: "13px",
              cursor: "pointer",
              transition: "color 0.2s",
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.color = "#94A3B8"; }}
            onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.color = "#334155"; }}
          >
            ← Back to Live Dashboard
          </button>
        </div>
      )}

      {/* ── ADMIN PANEL ─────────────────────────────────── */}
      {view === "admin" && auth.isAdmin && (
        <>
          <AdminTopNav
            username={auth.username ?? "admin"}
            onLogout={handleLogout}
            onStudentView={() => setView("dashboard")}
          />
          <AdminPanel
            regions={displayRegions}
            onUpdateRegions={setMockRegions}
            token={auth.token}
          />
        </>
      )}

      {/* ── STUDENT DASHBOARD ───────────────────────────── */}
      {view === "dashboard" && (
        <>
          <StudentTopNav
            lastUpdated={agoLabel}
            connected={connected}
            onAdminClick={() => setView("login")}
          />

          <div style={{ flex: 1, overflow: "auto", padding: isMobile ? "20px 16px" : "clamp(24px, 4vw, 48px)" }}>

            <div style={{
              marginBottom: "28px",
              display: "flex",
              alignItems: "flex-start",
              justifyContent: "space-between",
              flexWrap: "wrap",
              gap: "12px",
            }}>
              <div>
                <h1 style={{
                  fontFamily: "'DM Sans', sans-serif",
                  fontWeight: 700,
                  fontSize: isMobile ? "20px" : "clamp(22px, 2.2vw, 28px)",
                  color: "#F1F5F9",
                  margin: 0,
                  lineHeight: 1.25,
                }}>
                  AKGEC — Library Live Status
                </h1>
                <p style={{
                  fontFamily: "'IBM Plex Mono', monospace",
                  fontSize: "12px",
                  color: "#475569",
                  margin: "6px 0 0",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  flexWrap: "wrap",
                }}>
                  <span>{libraryRegions.length} library · {liveCanteenRegions.length} canteen · {liveLtRegions.length} LT</span>
                  <span style={{ color: "#2A2E42" }}>·</span>
                  {connected
                    ? <span style={{ color: "#22C55E" }}>Live</span>
                    : <span style={{ color: "#475569" }}>Demo mode</span>
                  }
                  {offlineMode && <span style={{ color: "#2A2E42" }}>·</span>}
                  {offlineMode && <span style={{ color: "#EF4444" }}>1 camera offline</span>}
                  <span style={{ color: "#2A2E42" }}>·</span>
                  <span>Refreshed {refreshTime}</span>
                </p>
              </div>

              {/* Offline demo toggle — local dev only, never on the live site */}
              {!connected && !IS_LIVE && (
                <button
                  onClick={() => setOfflineMode(p => !p)}
                  style={{
                    backgroundColor: offlineMode ? "#2D0707" : "transparent",
                    border: `1px solid ${offlineMode ? "#EF4444" : "#2A2E42"}`,
                    borderRadius: "8px",
                    padding: "6px 12px",
                    color: offlineMode ? "#EF4444" : "#334155",
                    fontFamily: "'IBM Plex Mono', monospace",
                    fontSize: "11px",
                    cursor: "pointer",
                    transition: "all 0.2s",
                    whiteSpace: "nowrap",
                    alignSelf: "flex-start",
                    letterSpacing: "0.03em",
                  }}
                  onMouseEnter={e => {
                    if (!offlineMode) {
                      (e.currentTarget as HTMLButtonElement).style.borderColor = "#475569";
                      (e.currentTarget as HTMLButtonElement).style.color = "#94A3B8";
                    }
                  }}
                  onMouseLeave={e => {
                    if (!offlineMode) {
                      (e.currentTarget as HTMLButtonElement).style.borderColor = "#2A2E42";
                      (e.currentTarget as HTMLButtonElement).style.color = "#334155";
                    }
                  }}
                >
                  {offlineMode ? "● cam_04 offline · restore" : "⚡ Simulate cam_04 offline"}
                </button>
              )}
            </div>

            {/* Library Section */}
            <SectionHeader label="Library" count={libraryRegions.length} accent="#6366F1" />
            {isMobile ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "12px", marginBottom: "32px" }}>
                {libraryRegions.map((r, i) => (
                  <div key={r.id} style={{ animation: `fadeUp 0.3s ease ${i * 0.06}s both` }}>
                    <RegionCard region={r} mobile />
                  </div>
                ))}
                <div style={{ marginTop: "8px" }}>
                  <SmartSuggestionStrip regions={libraryRegions} inline />
                </div>
              </div>
            ) : (
              <div style={{
                display: "grid",
                gridTemplateColumns: "repeat(2, minmax(280px, 1fr))",
                gap: "16px",
                maxWidth: "900px",
                marginBottom: "40px",
              }}>
                {libraryRegions.map((r, i) => (
                  <div key={r.id} style={{ animation: `fadeUp 0.3s ease ${i * 0.07}s both` }}>
                    <RegionCard region={r} />
                  </div>
                ))}
              </div>
            )}

            {/* CS-IT Canteen Section */}
            <SectionHeader label="CS-IT Canteen" count={liveCanteenRegions.length} accent="#06B6D4" />
            {isMobile ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "12px", marginBottom: "32px" }}>
                {canteenRegions.map((r, i) => (
                  <div key={r.id} style={{ animation: `fadeUp 0.3s ease ${i * 0.06}s both` }}>
                    <RegionCard region={r} mobile />
                  </div>
                ))}
              </div>
            ) : (
              <div style={{
                display: "grid",
                gridTemplateColumns: "repeat(2, minmax(280px, 1fr))",
                gap: "16px",
                maxWidth: "900px",
                marginBottom: "40px",
              }}>
                {canteenRegions.map((r, i) => (
                  <div key={r.id} style={{ animation: `fadeUp 0.3s ease ${i * 0.07}s both` }}>
                    <RegionCard region={r} />
                  </div>
                ))}
              </div>
            )}

            {/* LT Section */}
            <SectionHeader label="LT" count={liveLtRegions.length} accent="#F59E0B" />
            {isMobile ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                {ltRegions.map((r, i) => (
                  <div key={r.id} style={{ animation: `fadeUp 0.3s ease ${i * 0.06}s both` }}>
                    <RegionCard region={r} mobile />
                  </div>
                ))}
              </div>
            ) : (
              <div style={{
                display: "grid",
                gridTemplateColumns: "repeat(2, minmax(280px, 1fr))",
                gap: "16px",
                maxWidth: "900px",
              }}>
                {ltRegions.map((r, i) => (
                  <div key={r.id} style={{ animation: `fadeUp 0.3s ease ${i * 0.07}s both` }}>
                    <RegionCard region={r} />
                  </div>
                ))}
              </div>
            )}
          </div>

          {!isMobile && <SmartSuggestionStrip regions={libraryRegions} />}
        </>
      )}
    </div>
  );
}
