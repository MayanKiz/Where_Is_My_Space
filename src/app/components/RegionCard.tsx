import { useState } from "react";
import { Region } from "./types";
import { StatusBadge } from "./StatusBadge";
import { CapacityBar } from "./CapacityBar";

interface RegionCardProps {
  region: Region;
  mobile?: boolean;
}

const cardBg: Record<string, string> = {
  free:     "#052E16",
  moderate: "#2D1B00",
  full:     "#2D0707",
  offline:  "#1E293B",
};

const borderColors: Record<string, string> = {
  free:     "#22C55E",
  moderate: "#F59E0B",
  full:     "#EF4444",
  offline:  "#334155",
};

export function RegionCard({ region, mobile = false }: RegionCardProps) {
  const [hovered, setHovered] = useState(false);
  const isOffline = region.status === "offline";
  const fillPct = isOffline ? 0 : Math.round((region.count / region.capacity) * 100);
  const countSize = mobile ? "24px" : "32px";

  const borderStyle = isOffline
    ? { border: `2px dashed ${borderColors.offline}` }
    : { borderLeft: `3px solid ${borderColors[region.status]}` };

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        backgroundColor: hovered
          ? isOffline ? "#243044" : cardBg[region.status] + "ee"
          : cardBg[region.status],
        ...borderStyle,
        borderRadius: "12px",
        padding: "16px",
        display: "flex",
        flexDirection: "column",
        gap: "10px",
        transition: "background-color 0.2s ease, box-shadow 0.2s ease",
        boxShadow: hovered ? "0 4px 20px rgba(0,0,0,0.3)" : "none",
        position: "relative",
        height: mobile ? "auto" : "180px",
        minHeight: mobile ? "140px" : "180px",
        boxSizing: "border-box",
      }}
    >
      {mobile ? (
        /* Mobile: badge top-right absolute, name on its own line */
        <>
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "8px" }}>
            <span style={{
              fontFamily: "'DM Sans', sans-serif",
              fontWeight: 600,
              fontSize: "16px",
              color: isOffline ? "#475569" : "#F1F5F9",
              lineHeight: 1.3,
              flex: 1,
            }}>
              {region.name}
            </span>
            <StatusBadge status={region.status} />
          </div>
          <div style={{ display: "flex", alignItems: "baseline", gap: "4px" }}>
            <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontWeight: 600, fontSize: countSize, color: isOffline ? "#475569" : "#F1F5F9", lineHeight: 1 }}>
              {isOffline ? "—" : region.count}
            </span>
            <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontWeight: 400, fontSize: "16px", color: "#475569" }}>
              {" "}/ {region.capacity}
            </span>
          </div>
          <CapacityBar count={region.count} capacity={region.capacity} status={region.status} />
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "11px", color: "#475569" }}>
              {isOffline ? `Camera offline · Last known: ${region.lastUpdated}` : `Updated ${region.lastUpdated}`}
            </span>
            {!isOffline && region.reserved > 0 && (
              <span style={{
                fontFamily: "'IBM Plex Mono', monospace",
                fontSize: "10px",
                color: "#F59E0B",
                backgroundColor: "#2D1B00",
                padding: "2px 6px",
                borderRadius: "4px",
                border: "1px solid #78350F",
                letterSpacing: "0.03em",
              }}>
                {region.reserved} reserved 💻
              </span>
            )}
          </div>
        </>
      ) : (
        /* Desktop layout */
        <>
          {/* Row 1: Name + Badge */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "8px" }}>
            <span style={{
              fontFamily: "'DM Sans', sans-serif",
              fontWeight: 700,
              fontSize: "18px",
              color: isOffline ? "#475569" : "#F1F5F9",
              lineHeight: 1.3,
              flex: 1,
              minWidth: 0,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}>
              {region.name}
            </span>
            <StatusBadge status={region.status} />
          </div>

          {/* Row 2: Count */}
          <div style={{ display: "flex", alignItems: "baseline", gap: "4px" }}>
            <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontWeight: 600, fontSize: "32px", color: isOffline ? "#475569" : "#F1F5F9", lineHeight: 1 }}>
              {isOffline ? "—" : region.count}
            </span>
            <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontWeight: 400, fontSize: "20px", color: "#475569" }}>
              {" "}/ {region.capacity}
            </span>
          </div>

          {/* Row 3: Bar */}
          <CapacityBar count={region.count} capacity={region.capacity} status={region.status} />

          {/* Row 4: Footer */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: "auto" }}>
            <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "11px", color: "#475569" }}>
              {isOffline ? `Camera offline · Last known: ${region.lastUpdated}` : `Updated ${region.lastUpdated}`}
            </span>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              {!isOffline && region.reserved > 0 && (
                <span style={{
                  fontFamily: "'IBM Plex Mono', monospace",
                  fontSize: "10px",
                  color: "#F59E0B",
                  backgroundColor: "#2D1B00",
                  padding: "2px 6px",
                  borderRadius: "4px",
                  border: "1px solid #78350F",
                  letterSpacing: "0.03em",
                }}>
                  {region.reserved} reserved 💻
                </span>
              )}
              {!isOffline && (
                <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "11px", color: borderColors[region.status] }}>
                  {fillPct}%
                </span>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
