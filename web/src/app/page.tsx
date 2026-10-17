"use client";

import {
  Activity, ArrowDownRight, ArrowUpRight, BookOpen, Building2, Camera,
  CircleHelp, Database, FileVideo, Filter, GraduationCap, LayoutDashboard,
  LockKeyhole, MapPinned, ScanSearch, ShieldCheck, Sparkles, Users, Video, Zap,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { OccupancyFeed, WimsHealth, fetchHealth, fetchLiveOccupancy, getWimsApiUrl } from "@/lib/api";

type DisplayZone = {
  id: string;
  name: string;
  location: string;
  capacity: number;
  occupied: number | null;
  status: string;
  live: boolean;
};

const sampleZones: DisplayZone[] = [
  { id: "LIB-01", name: "Central Library", location: "Block A · Level 1", capacity: 42, occupied: 28, status: "Busy", live: false },
  { id: "STU-02", name: "Quiet Study Hall", location: "Block A · Level 2", capacity: 24, occupied: 9, status: "Available", live: false },
  { id: "LOU-03", name: "Student Lounge", location: "Student Centre", capacity: 18, occupied: 13, status: "Filling up", live: false },
  { id: "LAB-04", name: "Innovation Lab", location: "Block C · Ground", capacity: 30, occupied: 0, status: "Not connected", live: false },
];

type LiveState = {
  feed: OccupancyFeed | null;
  health: WimsHealth | null;
  error: string | null;
};

function useLiveWims(): LiveState {
  const [state, setState] = useState<LiveState>({ feed: null, health: null, error: null });

  useEffect(() => {
    if (!getWimsApiUrl()) {
      setState({ feed: null, health: null, error: "API URL not configured" });
      return;
    }
    let cancelled = false;
    const load = async () => {
      try {
        const [feed, health] = await Promise.all([
          fetchLiveOccupancy().catch(() => null),
          fetchHealth().catch(() => null),
        ]);
        if (cancelled) return;
        if (!feed) {
          setState({ feed: null, health, error: "API reachable, but live occupancy is empty. Create zones and process a clip." });
        } else {
          setState({ feed, health, error: null });
        }
      } catch (error) {
        if (!cancelled) {
          setState({ feed: null, health: null, error: error instanceof Error ? error.message : "Could not reach the WIMS API." });
        }
      }
    };
    void load();
    const timer = setInterval(load, 30_000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  return state;
}

function MetricCard({
  label,
  value,
  icon: Icon,
  tone,
  note,
}: {
  label: string;
  value: string;
  icon: typeof Users;
  tone: "cyan" | "green" | "violet" | "red";
  note: string;
}) {
  return (
    <article className="metric-card">
      <div className="metric-top">
        <span>{label}</span>
        <span className={`metric-icon tone-${tone}`}><Icon size={15} /></span>
      </div>
      <div className="metric-value">{value}</div>
      <div className="metric-foot"><span className={`tiny-dot tone-${tone}`} />{note}</div>
    </article>
  );
}

export default function DashboardPage() {
  const { feed, health, error } = useLiveWims();
  const liveMode = Boolean(feed && feed.zones.length > 0);

  const zones: DisplayZone[] = useMemo(() => {
    if (!liveMode || !feed) return sampleZones;
    return feed.zones.map((zone) => ({
      id: zone.slug || zone.id.slice(0, 8),
      name: zone.name,
      location: zone.location_name || "Campus",
      capacity: zone.capacity,
      occupied: zone.available_count === null ? null : zone.capacity - zone.available_count,
      status: zone.has_live_data ? zone.status : "Awaiting data",
      live: zone.has_live_data,
    }));
  }, [feed, liveMode]);

  const totalCapacity = zones.reduce((sum, zone) => sum + zone.capacity, 0);
  const occupied = zones.reduce((sum, zone) => sum + (zone.occupied ?? 0), 0);
  const liveZonesWithData = zones.filter((zone) => zone.live).length;

  const connectionNote = error
    ? `Sample values shown — ${error}`
    : liveMode
      ? "Live values from the WIMS API"
      : "Sample values only";

  const activities = [
    {
      icon: ScanSearch,
      title: "AI inference worker implemented",
      detail: "OpenCV + YOLO person detection processes uploaded clips and RTSP feeds; results land in occupancy snapshots.",
      color: "violet",
    },
    {
      icon: Database,
      title: liveMode ? "Live Supabase data flowing" : "Supabase connection pending",
      detail: liveMode
        ? `Latest occupancy read at ${new Date(feed!.generated_at).toLocaleTimeString()}.`
        : "Configure the WIMS API URL and apply the migrations to see live data here.",
      color: "cyan",
    },
    {
      icon: ShieldCheck,
      title: "Privacy-first by design",
      detail: "No face recognition; raw clips are deleted right after processing.",
      color: "green",
    },
  ];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#overview" aria-label="WIMS overview">
          <span className="brand-mark"><MapPinned size={19} strokeWidth={1.8} /></span>
          <span><span className="brand-title">Where Is My Space?</span><span className="brand-subtitle">Spatial intelligence</span></span>
        </a>
        <div className="nav-label">Workspace</div>
        <nav aria-label="Main navigation">
          <a className="nav-link active" href="#overview"><LayoutDashboard size={16} />Overview<span className="nav-current" /></a>
          <a className="nav-link" href="#zones"><MapPinned size={16} />Space map</a>
          <a className="nav-link" href="#video-source"><FileVideo size={16} />Video sources<span className="nav-soon">MVP</span></a>
          <a className="nav-link" href="#activity"><Activity size={16} />Processing status</a>
        </nav>
        <div className="nav-label">Explore</div>
        <nav aria-label="Explore">
          <a className="nav-link" href="#privacy"><ShieldCheck size={16} />Privacy & safety</a>
          <a className="nav-link" href="#how-it-works"><CircleHelp size={16} />How it works</a>
        </nav>
        <div className="sidebar-bottom">
          <div className="privacy-card" id="privacy">
            <div className="privacy-title"><LockKeyhole size={14} className="tone-green" /> Privacy-first approach</div>
            <p className="privacy-copy">Occupancy intelligence, not identities. Raw video is processed temporarily and deleted after processing or at expiry.</p>
            <a className="privacy-link" href="#how-it-works">Read our principles <ArrowUpRight size={12} /></a>
          </div>
          <div className="sidebar-footer"><span className="footer-square" /> WIMS LABS <span>·</span> PROTOTYPE 001</div>
        </div>
      </aside>

      <main className="main-area" id="overview">
        <header className="topbar">
          <div className="breadcrumb">Workspace <span>/</span> <strong>Overview</strong></div>
          <div className="top-actions">
            <span className="environment-tag"><span className="environment-dot" />{liveMode ? "API connected" : "Local preview"}</span>
            <span className="status-pill"><span className="status-dot" />{liveMode ? "Live data" : "Sample data"}</span>
            <button type="button" className="avatar" aria-label="Project profile">WM</button>
          </div>
        </header>

        <div className="content">
          <section className="page-heading">
            <div>
              <div className="eyebrow"><Sparkles size={13} /> PHYSICAL SPACES, MADE INTELLIGIBLE</div>
              <h1 className="page-title">Know your space.<br /><span className="gradient-text">Before you get there.</span></h1>
              <p className="page-subtitle">
                {liveMode
                  ? "Live campus space availability, computed by the AI worker from real camera clips — no faces, no identities."
                  : "A live view of campus space availability, built around privacy-conscious computer vision. This workspace currently shows clearly labelled sample values."}
              </p>
            </div>
            <a className="primary-button" href="/capture"><Camera size={15} /> Open Capture app <ArrowUpRight size={13} /></a>
          </section>

          <section className="metrics-grid" aria-label={liveMode ? "Live summary" : "Example summary"}>
            <MetricCard
              label={liveMode ? "Configured capacity" : "Configured capacity"}
              value={String(totalCapacity)}
              icon={Building2}
              tone="cyan"
              note={liveMode ? "From live zone config" : "Sample setup"}
            />
            <MetricCard
              label={liveMode ? "People now" : "Sample occupancy"}
              value={liveMode ? String(occupied) : String(occupied)}
              icon={Users}
              tone="red"
              note={liveMode ? "Latest detections" : "Illustrative only"}
            />
            <MetricCard
              label={liveMode ? "Spaces free" : "Sample spaces free"}
              value={String(Math.max(totalCapacity - occupied, 0))}
              icon={MapPinned}
              tone="green"
              note={liveMode ? "Computed live" : "Not live data"}
            />
            <MetricCard
              label={liveMode ? "Zones reporting" : "Connected sources"}
              value={liveMode ? `${liveZonesWithData}/${zones.length}` : "0"}
              icon={Camera}
              tone="violet"
              note={liveMode ? "Zones with occupancy data" : "No source connected"}
            />
          </section>

          <section className="content-grid">
            <article className="panel" id="zones">
              <div className="panel-heading">
                <div><div className="panel-title">Campus space map</div><div className="panel-subtitle">{liveMode ? "Live zone occupancy · updated every 30 s" : "Illustrative zones · replace with a real floor plan later"}</div></div>
                <span className="micro-tag"><MapPinned size={12} /> {liveMode ? "LIVE LAYOUT" : "DEMO LAYOUT"}</span>
              </div>
              <div className="map-stage" role="img" aria-label={liveMode ? "Campus zone map with live occupancy" : "Illustrative campus zone map with four labelled areas"}>
                <div className="map-grid" />
                <div className="map-axis h" /><div className="map-axis v" />
                <div className="map-connector connector-one" /><div className="map-connector connector-two" />
                {zones.slice(0, 4).map((zone, index) => {
                  const free = Math.max(zone.capacity - (zone.occupied ?? 0), 0);
                  const fullness = (zone.occupied ?? 0) / Math.max(zone.capacity, 1);
                  const positionClass = ["zone-a", "zone-b", "zone-c", "zone-d"][index];
                  const noData = zone.occupied === null;
                  return (
                    <div key={zone.id} className={`zone ${positionClass} ${noData ? "zone-muted" : ""}`}>
                      <span className="zone-number">{String(index + 1).padStart(2, "0")}</span>
                      <strong>{zone.name}</strong>
                      <span className="zone-meta">{zone.location}</span>
                      <span className={`zone-count ${noData ? "tone-muted" : fullness > 0.65 ? "tone-red" : "tone-green"}`}>
                        {noData ? "No feed" : `${free} spaces free`}
                      </span>
                    </div>
                  );
                })}
                <span className="map-label top-left">NORTH WING</span>
                <span className="map-label bottom-right">CAMPUS / BLOCK A—C</span>
              </div>
              <div className="map-legend">
                <span className="legend-item"><span className="legend-dot free" />Lower occupancy</span>
                <span className="legend-item"><span className="legend-dot busy" />Higher occupancy</span>
                <span className="legend-item"><span className="legend-dot unknown" />No source</span>
                <span className="legend-note">{liveMode ? "Live sensor data" : "Sample map, not real sensor data"}</span>
              </div>
            </article>

            <article className="panel" id="video-source">
              <div className="panel-heading">
                <div><div className="panel-title">WIMS Capture app</div><div className="panel-subtitle">One mobile workspace for every video source</div></div>
                <span className="micro-tag"><Camera size={12} /> SOURCE STUDIO</span>
              </div>
              <a href="/capture" className="capture-launch-card">
                <span className="capture-launch-icon"><Camera size={21} /></span>
                <span className="capture-launch-copy"><strong>Open WIMS Capture</strong><small>Phone camera · screen recording · MP4/WebM · extra IP cameras</small><em>Open source studio <ArrowUpRight size={12} /></em></span>
                <ArrowUpRight size={16} className="capture-launch-arrow" />
              </a>
              <div className="capture-launch-facts"><span><LockKeyhole size={13} /> Paired device access</span><span><Database size={13} /> Source metadata stored in Supabase</span></div>
              <div className="integration-note"><Database size={15} /><span><strong>Current stage:</strong> source registry, temporary video upload, and AI person detection. Clips are processed by the inference worker and results appear as occupancy snapshots.</span></div>
            </article>
          </section>

          <section className="bottom-grid">
            <article className="panel">
              <div className="panel-heading">
                <div><div className="panel-title">Space directory</div><div className="panel-subtitle">{liveMode ? "Live zones with the latest occupancy estimate" : "Example zones for the first campus pilot"}</div></div>
                <button type="button" className="icon-button" aria-label="Filter zones" title={liveMode ? "Live data" : "Static preview"}><Filter size={14} /></button>
              </div>
              <div className="table-wrap">
                <table className="zone-table">
                  <thead><tr><th>SPACE</th><th>CAPACITY</th><th>OCCUPIED*</th><th>STATUS</th></tr></thead>
                  <tbody>{zones.map((zone) => {
                    const statusClass = zone.status === "Available" ? "good" : zone.status === "Busy" || zone.status === "Full" ? "busy" : "";
                    return <tr key={zone.id}>
                      <td><span className="zone-name"><span className="zone-symbol">{zone.id.startsWith("LIB") ? <BookOpen size={13} /> : zone.id.startsWith("LAB") ? <Zap size={13} /> : zone.id.startsWith("STU") ? <GraduationCap size={13} /> : <Users size={13} />}</span><span><strong>{zone.name}</strong><small>{zone.location}</small></span></span></td>
                      <td>{zone.capacity}</td><td>{zone.occupied ?? "—"}</td><td><span className={`state-tag ${statusClass}`}><span className="state-dot" />{zone.status}</span></td>
                    </tr>;
                  })}</tbody>
                </table>
              </div>
              <div className="table-disclaimer">
                * {liveMode
                  ? "Occupancy is the peak person count observed inside the zone during the latest processed clip or stream sample — an estimate, not an exact seat count."
                  : "Example values only. Availability is calculated from processed video once the AI worker runs."}
              </div>
            </article>

            <article className="panel" id="activity">
              <div className="panel-heading">
                <div><div className="panel-title">System status</div><div className="panel-subtitle">What is connected in this build?</div></div>
                <span className="micro-tag">HONEST STATUS</span>
              </div>
              <div className="activity-list">{activities.map((item) => {
                const Icon = item.icon;
                return <div className="activity-item" key={item.title}>
                  <span className={`activity-icon tone-${item.color}`}><Icon size={14} /></span>
                  <span className="activity-text"><strong>{item.title}</strong><small>{item.detail}</small></span>
                  <span className="activity-chevron"><ArrowDownRight size={13} /></span>
                </div>;
              })}</div>
              <div className="pipeline" id="how-it-works">
                <div className="pipeline-title">Processing pipeline <span>{liveMode ? "LIVE" : "READY"}</span></div>
                <div className="pipeline-steps"><span><Video size={12} /> MP4</span><i /> <span><ScanSearch size={12} /> AI</span><i /> <span><Database size={12} /> Data</span></div>
                <p>Video → person detection → zone occupancy → Supabase → dashboard. {health ? `API health: ${health.video_processing}.` : "Each stage is verified before being marked active."}</p>
              </div>
            </article>
          </section>

          <footer className="footer-note"><span><ShieldCheck size={12} /> Privacy is a design constraint, not an add-on.</span><span>WIMS / 001 <span className="footer-divider">·</span> {connectionNote}</span></footer>
        </div>
      </main>
    </div>
  );
}