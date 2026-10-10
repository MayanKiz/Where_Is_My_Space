export type ZoneStatus = "available" | "busy" | "unknown";

export type ZoneSummary = {
  id: string;
  name: string;
  location: string;
  capacity: number | null;
  occupied: number | null;
  available: number | null;
  status: ZoneStatus;
  updatedAt: string | null;
};

export type DashboardSummary = {
  source: "sample";
  totalCapacity: number;
  occupied: number;
  available: number;
  zones: ZoneSummary[];
  lastUpdated: string | null;
};
