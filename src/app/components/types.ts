export type RegionStatus = "free" | "moderate" | "full" | "offline";
export type RegionSection = "library" | "canteen" | "lt";

export interface Region {
  id: string;
  name: string;
  count: number;
  reserved: number;
  capacity: number;
  status: RegionStatus;
  camId: string;
  camOnline: boolean;
  lastUpdated: string;
  locationNotes: string;
  section: RegionSection;
}
