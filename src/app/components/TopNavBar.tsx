import { Settings, LogOut, User } from "lucide-react";

interface StudentNavProps {
  lastUpdated: string;
  connected?: boolean;
  onAdminClick: () => void;
}

interface AdminNavProps {
  username: string;
  onLogout: () => void;
  onStudentView: () => void;
}

export function StudentTopNav({ lastUpdated, connected = false, onAdminClick }: StudentNavProps) {
  return (
    <div style={{
      height: "56px",
      backgroundColor: "#22263A",
      padding: "0 24px",
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      borderBottom: "1px solid #2A2E42",
      flexShrink: 0,
    }}>
      {/* Left: live dot + title */}
      <div style={{ display: "flex", alignItems: "center", gap: "10px", minWidth: 0 }}>
        <span style={{
          width: "8px",
          height: "8px",
          borderRadius: "50%",
          backgroundColor: connected ? "#22C55E" : "#475569",
          display: "inline-block",
          flexShrink: 0,
          animation: connected ? "pulse-dot 2s infinite" : "none",
        }} />
        <span style={{
          fontFamily: "'DM Sans', sans-serif",
          fontWeight: 700,
          fontSize: "15px",
          color: "#F1F5F9",
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
        }}>
          AKGEC Campus Occupancy Dashboard
        </span>
      </div>

      {/* Right: timestamp + admin link */}
      <div style={{ display: "flex", alignItems: "center", gap: "16px", flexShrink: 0 }}>
        <span style={{
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: "12px",
          color: "#94A3B8",
          whiteSpace: "nowrap",
        }}>
          Last updated: {lastUpdated}
        </span>
        <button
          onClick={onAdminClick}
          style={{
            background: "none",
            border: "1px solid #2A2E42",
            borderRadius: "8px",
            padding: "5px 12px",
            color: "#94A3B8",
            fontFamily: "'DM Sans', sans-serif",
            fontSize: "13px",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: "6px",
            transition: "border-color 0.2s, color 0.2s",
            whiteSpace: "nowrap",
          }}
          onMouseEnter={e => {
            (e.currentTarget as HTMLButtonElement).style.borderColor = "#6366F1";
            (e.currentTarget as HTMLButtonElement).style.color = "#F1F5F9";
          }}
          onMouseLeave={e => {
            (e.currentTarget as HTMLButtonElement).style.borderColor = "#2A2E42";
            (e.currentTarget as HTMLButtonElement).style.color = "#94A3B8";
          }}
        >
          <Settings size={14} />
          Admin
        </button>
      </div>
    </div>
  );
}

export function AdminTopNav({ username, onLogout, onStudentView }: AdminNavProps) {
  return (
    <div style={{
      height: "56px",
      backgroundColor: "#22263A",
      padding: "0 24px",
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      borderBottom: "1px solid #2A2E42",
      flexShrink: 0,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
        <Settings size={18} color="#6366F1" />
        <span style={{
          fontFamily: "'DM Sans', sans-serif",
          fontWeight: 700,
          fontSize: "15px",
          color: "#F1F5F9",
        }}>
          Admin Panel
        </span>
        <span style={{ width: "1px", height: "18px", backgroundColor: "#2A2E42" }} />
        <button
          onClick={onStudentView}
          style={{
            background: "none",
            border: "none",
            color: "#94A3B8",
            fontFamily: "'DM Sans', sans-serif",
            fontSize: "13px",
            cursor: "pointer",
            padding: 0,
            transition: "color 0.2s",
          }}
          onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.color = "#6366F1"; }}
          onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.color = "#94A3B8"; }}
        >
          ← Live Dashboard
        </button>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <User size={14} color="#475569" />
          <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "13px", color: "#94A3B8" }}>
            {username}@akgec
          </span>
        </div>
        <button
          onClick={onLogout}
          style={{
            background: "none",
            border: "1px solid #334155",
            borderRadius: "8px",
            padding: "5px 12px",
            color: "#94A3B8",
            fontFamily: "'DM Sans', sans-serif",
            fontWeight: 500,
            fontSize: "13px",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: "6px",
            transition: "all 0.2s",
          }}
          onMouseEnter={e => {
            const b = e.currentTarget as HTMLButtonElement;
            b.style.backgroundColor = "#EF4444";
            b.style.color = "#fff";
            b.style.borderColor = "#EF4444";
          }}
          onMouseLeave={e => {
            const b = e.currentTarget as HTMLButtonElement;
            b.style.backgroundColor = "transparent";
            b.style.color = "#94A3B8";
            b.style.borderColor = "#334155";
          }}
        >
          <LogOut size={14} />
          Logout
        </button>
      </div>
    </div>
  );
}
