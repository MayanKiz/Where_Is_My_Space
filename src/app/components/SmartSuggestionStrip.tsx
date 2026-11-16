import { Lightbulb } from "lucide-react";
import { Region } from "./types";

interface Props {
  regions: Region[];
  inline?: boolean; // true on mobile — no fixed height, padding adjusted
}

export function SmartSuggestionStrip({ regions, inline = false }: Props) {
  const online = regions.filter(r => r.status !== "offline");

  const least = online.reduce<Region | null>((best, r) => {
    if (!best) return r;
    return (r.count / r.capacity) < (best.count / best.capacity) ? r : best;
  }, null);

  const text = least
    ? `${least.name} is the least crowded right now — ${least.count} / ${least.capacity} people`
    : "All monitored areas are currently offline";

  return (
    <div style={{
      height: inline ? undefined : "44px",
      minHeight: inline ? "44px" : undefined,
      backgroundColor: "#22263A",
      borderTop: "1px solid #2A2E42",
      borderRadius: inline ? "12px" : "0",
      display: "flex",
      alignItems: "center",
      padding: "0 20px",
      gap: "10px",
      flexShrink: 0,
    }}>
      <Lightbulb size={16} color="#F59E0B" style={{ flexShrink: 0 }} />
      <span style={{
        fontFamily: "'DM Sans', sans-serif",
        fontSize: "14px",
        color: "#94A3B8",
        overflow: "hidden",
        textOverflow: "ellipsis",
        whiteSpace: "nowrap",
      }}>
        <span style={{ color: "#F59E0B", fontWeight: 600 }}>Tip: </span>
        {text}
      </span>
    </div>
  );
}
