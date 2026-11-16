import { RegionStatus } from "./types";

interface StatusBadgeProps {
  status: RegionStatus;
}

const config: Record<RegionStatus, { label: string; bg: string; color: string }> = {
  free:     { label: "FREE",     bg: "#052E16", color: "#22C55E" },
  moderate: { label: "MODERATE", bg: "#2D1B00", color: "#F59E0B" },
  full:     { label: "FULL",     bg: "#2D0707", color: "#EF4444" },
  offline:  { label: "OFFLINE",  bg: "#1E293B", color: "#475569" },
};

export function StatusBadge({ status }: StatusBadgeProps) {
  const { label, bg, color } = config[status];
  return (
    <span
      style={{
        backgroundColor: bg,
        color,
        fontSize: "12px",
        fontFamily: "'DM Sans', sans-serif",
        fontWeight: 600,
        letterSpacing: "0.08em",
        padding: "4px 10px",
        borderRadius: "6px",
        textTransform: "uppercase",
        lineHeight: 1,
        display: "inline-flex",
        alignItems: "center",
        height: "24px",
        whiteSpace: "nowrap",
      }}
    >
      {label}
    </span>
  );
}
