"use client";

import {
  Activity, ArrowDownRight, ArrowUpRight, BookOpen, Building2, Camera,
  CircleHelp, Database, FileVideo, Filter, GraduationCap, LayoutDashboard,
  LockKeyhole, MapPinned, ScanSearch, ShieldCheck, Sparkles, Users, Video, Zap,
} from "lucide-react";

const sampleZones = [
  { id: "LIB-01", name: "Central Library", location: "Block A · Level 1", capacity: 42, occupied: 28, status: "Busy" },
  { id: "STU-02", name: "Quiet Study Hall", location: "Block A · Level 2", capacity: 24, occupied: 9, status: "Available" },
  { id: "LOU-03", name: "Student Lounge", location: "Student Centre", capacity: 18, occupied: 13, status: "Filling up" },
  { id: "LAB-04", name: "Innovation Lab", location: "Block C · Ground", capacity: 30, occupied: 0, status: "Not connected" },
];

const activities = [
  { icon: Video, title: "Video analysis is not connected yet", detail: "Capture uploads are planned; the AI inference worker is next.", color: "violet" },
  { icon: Database, title: "Supabase connection pending", detail: "Requires your Supabase project and migrations to be configured.", color: "cyan" },
  { icon: ShieldCheck, title: "Privacy-first by design", detail: "No face recognition; clips use private temporary storage.", color: "green" },
];

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
  const totalCapacity = sampleZones.reduce((sum, zone) => sum + zone.capacity, 0);
  const occupied = sampleZones.reduce((sum, zone) => sum + zone.occupied, 0);

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
            <p className="privacy-copy">Occupancy intelligence, not identities. Raw video should be processed temporarily and not stored by default.</p>
            <a className="privacy-link" href="#how-it-works">Read our principles <ArrowUpRight size={12} /></a>
          </div>
          <div className="sidebar-footer"><span className="footer-square" /> WIMS LABS <span>·</span> PROTOTYPE 001</div>
        </div>
      </aside>

      <main className="main-area" id="overview">
        <header className="topbar">
          <div className="breadcrumb">Workspace <span>/</span> <strong>Overview</strong></div>
          <div className="top-actions">
            <span className="environment-tag"><span className="environment-dot" />Local preview</span>
            <span className="status-pill"><span className="status-dot" />Prototype mode</span>
            <button type="button" className="avatar" aria-label="Project profile">WM</button>
          </div>
        </header>

        <div className="content">
          <section className="page-heading">
            <div>
              <div className="eyebrow"><Sparkles size={13} /> PHYSICAL SPACES, MADE INTELLIGIBLE</div>
              <h1 className="page-title">Know your space.<br /><span className="gradient-text">Before you get there.</span></h1>
              <p className="page-subtitle">A live view of campus space availability, built around privacy-conscious computer vision. This workspace currently shows clearly labelled sample values.</p>
            </div>
            <a className="primary-button" href="/capture"><Camera size={15} /> Open Capture app <ArrowUpRight size={13} /></a>
          </section>

          <section className="metrics-grid" aria-label="Example summary">
            <MetricCard label="Configured capacity" value={String(totalCapacity)} icon={Building2} tone="cyan" note="Sample setup" />
            <MetricCard label="Sample occupancy" value={String(occupied)} icon={Users} tone="red" note="Illustrative only" />
            <MetricCard label="Sample spaces free" value={String(totalCapacity - occupied)} icon={MapPinned} tone="green" note="Not live data" />
            <MetricCard label="Connected sources" value="0" icon={Camera} tone="violet" note="No source connected" />
          </section>

          <section className="content-grid">
            <article className="panel" id="zones">
              <div className="panel-heading">
                <div><div className="panel-title">Campus space map</div><div className="panel-subtitle">Illustrative zones · replace with a real floor plan later</div></div>
                <span className="micro-tag"><MapPinned size={12} /> DEMO LAYOUT</span>
              </div>
              <div className="map-stage" role="img" aria-label="Illustrative campus zone map with four labelled areas">
                <div className="map-grid" />
                <div className="map-axis h" /><div className="map-axis v" />
                <div className="map-connector connector-one" /><div className="map-connector connector-two" />
                {sampleZones.map((zone, index) => {
                  const free = zone.capacity - zone.occupied;
                  const fullness = zone.occupied / zone.capacity;
                  const positionClass = ["zone-a", "zone-b", "zone-c", "zone-d"][index];
                  return (
                    <div key={zone.id} className={`zone ${positionClass} ${index === 3 ? "zone-muted" : ""}`}>
                      <span className="zone-number">{String(index + 1).padStart(2, "0")}</span>
                      <strong>{zone.name}</strong>
                      <span className="zone-meta">{zone.location}</span>
                      <span className={`zone-count ${index === 3 ? "tone-muted" : fullness > 0.65 ? "tone-red" : "tone-green"}`}>
                        {index === 3 ? "No feed" : `${free} spaces free`}
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
                <span className="legend-note">Sample map, not real sensor data</span>
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
              <div className="integration-note"><Database size={15} /><span><strong>Current stage:</strong> source registry and temporary video upload. The AI worker and continuous live stream analysis still need to be connected.</span></div>
            </article>
          </section>

          <section className="bottom-grid">
            <article className="panel">
              <div className="panel-heading">
                <div><div className="panel-title">Space directory</div><div className="panel-subtitle">Example zones for the first campus pilot</div></div>
                <button type="button" className="icon-button" aria-label="Filter example zones" title="This is a static preview"><Filter size={14} /></button>
              </div>
              <div className="table-wrap">
                <table className="zone-table">
                  <thead><tr><th>SPACE</th><th>CAPACITY</th><th>OCCUPIED*</th><th>STATUS</th></tr></thead>
                  <tbody>{sampleZones.map((zone) => {
                    const statusClass = zone.status === "Available" ? "good" : zone.status === "Busy" ? "busy" : "";
                    return <tr key={zone.id}>
                      <td><span className="zone-name"><span className="zone-symbol">{zone.id.startsWith("LIB") ? <BookOpen size={13} /> : zone.id.startsWith("LAB") ? <Zap size={13} /> : zone.id.startsWith("STU") ? <GraduationCap size={13} /> : <Users size={13} />}</span><span><strong>{zone.name}</strong><small>{zone.location}</small></span></span></td>
                      <td>{zone.capacity}</td><td>{zone.id === "LAB-04" ? "—" : zone.occupied}</td><td><span className={`state-tag ${statusClass}`}><span className="state-dot" />{zone.status}</span></td>
                    </tr>;
                  })}</tbody>
                </table>
              </div>
              <div className="table-disclaimer">* Example values only. Availability will be calculated from processed video in a later step.</div>
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
                <div className="pipeline-title">Target processing pipeline <span>PLANNED</span></div>
                <div className="pipeline-steps"><span><Video size={12} /> MP4</span><i /> <span><ScanSearch size={12} /> AI</span><i /> <span><Database size={12} /> Data</span></div>
                <p>Video → detection → zone occupancy → Supabase → dashboard. Each stage will be verified before being marked active.</p>
              </div>
            </article>
          </section>

          <footer className="footer-note"><span><ShieldCheck size={12} /> Privacy is a design constraint, not an add-on.</span><span>WIMS / 001 <span className="footer-divider">·</span> Prototype UI <span className="footer-divider">·</span> No live feed connected</span></footer>
        </div>
      </main>
    </div>
  );
}
