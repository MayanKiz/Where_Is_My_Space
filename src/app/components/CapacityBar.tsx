import { RegionStatus } from "./types";

interface CapacityBarProps {
  count: number;
  capacity: number;
  status: RegionStatus;
}

const fillColors: Record<RegionStatus, string> = {
  free:     "#22C55E",
  moderate: "#F59E0B",
  full:     "#EF4444",
  offline:  "#475569",
};

export function CapacityBar({ count, capacity, status }: CapacityBarProps) {
  const pct = status === "offline" ? 0 : Math.min(100, (count / capacity) * 100);
  return (
    <div
      style={{
        width: "100%",
        height: "8px",
        borderRadius: "4px",
        backgroundColor: "#2A2E42",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          width: `${pct}%`,
          height: "100%",
          borderRadius: "4px",
          backgroundColor: fillColors[status],
          transition: "width 0.6s ease",
        }}
      />
    </div>
  );
}
