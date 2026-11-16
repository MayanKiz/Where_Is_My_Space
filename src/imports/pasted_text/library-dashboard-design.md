AKGEC Occupancy Dashboard
Complete Build Instructions — Figma UI Design + Claude Code Full-Stack

What We're Building
A real-time library occupancy dashboard for AKGEC campus.
Cameras are mounted region-wise across the library. Each camera runs a YOLO people-detection model independently and sends a live count to a central backend. The dashboard shows students which areas of the library are free or occupied — at a glance, instantly. Admin users configure which camera maps to which region and set capacities.
4 regions (expandable by admin at any time):
RegionDefault CameraDefault CapacityEntrance / Lobbycam_0140Main Reading Hallcam_0280Upper Floor / Quiet Zonecam_0330Collaborative / Group Studycam_0425


PART 1 — FIGMA DESIGN INSTRUCTIONS

1.1 Design Brief
Product: AKGEC Occupancy Dashboard
Audience: Two roles — Students (read-only, public) and Admin (configure + manage, login required)
Tone: Clean utilitarian campus-tech. Dark theme — feels live, like a monitoring board. Warm green/amber/red occupancy signal system.
Core rule: Occupancy status must be readable in under 2 seconds, from across a room or on a phone screen.

1.2 Color System (CSS Variables)
TokenHexUsage--bg-primary#0F1117App background--bg-card#1A1D27Region cards background--bg-elevated#22263AModals, navbar, admin panel--bg-input#2A2E42Form inputs--status-free#22C55EFREE state — <40% capacity--status-free-bg#052E16FREE card subtle tint--status-moderate#F59E0BMODERATE state — 40–74%--status-moderate-bg#2D1B00MODERATE card tint--status-full#EF4444FULL state — ≥75%--status-full-bg#2D0707FULL card tint--status-offline#475569Camera offline / unknown--text-primary#F1F5F9Headings, region names--text-secondary#94A3B8Labels, timestamps, metadata--text-muted#475569Disabled, placeholder--accent#6366F1Buttons, links, interactive--accent-hover#4F46E5Button hover state--border#2A2E42Card borders, dividers--border-offline#334155Dashed border for offline card

1.3 Typography
RoleFontWeightSizeRegion name (card)DM Sans700 Bold18pxLive count numberIBM Plex Mono60032pxCapacity label (e.g. "/ 80")IBM Plex Mono40020pxStatus badge textDM Sans60012pxSection headingsDM Sans70022pxBody / table textDM Sans40014pxTimestamp / metadataIBM Plex Mono40011pxButton textDM Sans60014px
Import from Google Fonts: DM Sans (400, 600, 700) + IBM Plex Mono (400, 600)

1.4 Spacing System
Use an 8px base grid throughout.
TokenValueUsespace-14pxTight inline gapsspace-28pxInner card padding (tight)space-312pxBetween badge + countspace-416pxCard inner paddingspace-624pxBetween cardsspace-832pxSection gapsspace-1248pxPage top padding
Card corner radius: 12px. Modal corner radius: 16px. Badge corner radius: 6px. Button corner radius: 8px.

1.5 Figma File Page Structure
Organise the Figma file into these pages:
Page 1: 🎨 Design Tokens       ← color styles, text styles, effect styles
Page 2: 🧩 Components          ← all reusable components
Page 3: 🖥️ Desktop Screens     ← all desktop-sized frames
Page 4: 📱 Mobile Screens      ← all mobile-sized frames
Page 5: 🔄 States & Flows      ← interaction notes, state transitions

1.6 Component Specifications
Component A — Region Card
Variants axis: status = free | moderate | full | offline
Fixed size: 280px wide × 180px tall (desktop). Full width on mobile.
Auto-layout: Vertical, padding 16px all sides, gap 10px between elements.
Layer structure (top to bottom):
RegionCard/
├── Row: [RegionName (text)]  [StatusBadge component]
├── CountRow: [LiveCount "28"] [Divider " / "] [Capacity "30"]
├── CapacityBar component
└── Timestamp "Updated 3s ago"
Per variant:

free: card bg = --status-free-bg, left border 3px solid --status-free
moderate: card bg = --status-moderate-bg, left border 3px solid --status-moderate
full: card bg = --status-full-bg, left border 3px solid --status-full
offline: card bg = --bg-card, border 2px dashed --border-offline, all text --text-muted

Hover state (interactive variant): card bg lightens by 5%, subtle box-shadow 0 4px 20px rgba(0,0,0,0.3)

Component B — StatusBadge
Variants: status = FREE | MODERATE | FULL | OFFLINE
Size: auto-width, 24px height. Padding: 4px 10px.
Style: filled pill. Font: DM Sans 600, 12px, uppercase. Rounded corners 6px.
VariantBGText colorFREE#052E16#22C55EMODERATE#2D1B00#F59E0BFULL#2D0707#EF4444OFFLINE#1E293B#475569

Component C — CapacityBar
Width: 100% of parent. Height: 8px. Corner radius: 4px.
Layers:

Background track: full width, --border color
Fill bar: width = (current_count / capacity) × 100%, color = status color

Variants: status = free | moderate | full | offline (offline = gray fill)
In Figma, represent fill width using a variable or annotation like fill% = count/capacity.

Component D — CameraStatusDot
Size: 8px circle.
Variants:

live: #22C55E, with a pulsing ring animation annotation
disconnected: #EF4444, static

Used in both the Admin table and a small indicator on each RegionCard in Admin view.

Component E — AdminTableRow
Width: 100% of table container. Height: 52px.
Columns (use auto-layout, horizontal):
[Region Name — flex grow]  [Camera ID — 140px]  [Capacity — 80px]  [Status dot — 80px]  [Edit icon button — 40px]
States: default | hover (bg --bg-elevated) | editing (row highlighted with accent border)

Component F — EditRegionModal
Size: 480px wide, auto height. Corner radius 16px. Background --bg-elevated.
Fields (vertical auto-layout, gap 16px, padding 24px):
Header: "Edit Region" (DM Sans 700, 18px)  [✕ close]
─────────
Label: "Region Name"
Input: text field, placeholder "e.g. Main Reading Hall"
─────────
Label: "Camera ID / Stream URL"
Input: text field, placeholder "cam_01  or  rtsp://192.168.1.x/..."
Helper text: "This is the ID the ML node uses when posting counts."
─────────
Label: "Max Capacity (people)"
Input: number field, min=1
─────────
Label: "Location Notes (optional)"
Input: textarea, 3 rows
─────────
Row: [Cancel — ghost button]  [Save Changes — primary button]

Component G — TopNavBar
Height: 56px. Full width. Background --bg-elevated. Horizontal padding 24px.
Student variant:
[● Live dot + "AKGEC Occupancy Dashboard"]    [Last updated: 3s ago — monospace]
Live dot: 8px circle #22C55E, CSS pulse animation.
Admin variant:
[⚙ icon + "Admin Panel"]    [username label]  [Logout button — ghost]

Component H — SmartSuggestionStrip
Height: 44px. Full width. Background --bg-elevated, top border 1px --border.
Layout:
[💡 icon]  ["Group Study is the least crowded right now — 8 / 25 people"]
Text: DM Sans 400, 14px, --text-secondary. Icon: amber --status-moderate.

Component I — AdminLoginForm
Size: 360px wide card, centered on page. Background --bg-card. Padding 32px. Radius 16px.
Fields:
"Admin Login" heading (DM Sans 700, 22px)
─────────
Label: "Username"
Input: text field
─────────
Label: "Password"
Input: password field, toggle show/hide
─────────
[Login — full width primary button]
─────────
Error state: red helper text "Invalid credentials" below button

1.7 Screens to Design
Screen 1 — Student Dashboard (Desktop, 1440×900)
┌──────────────────────────────────────────────────────┐
│  ● AKGEC Occupancy Dashboard   Updated: 2s  │  ← TopNavBar
├──────────────────────────────────────────────────────┤
│                                                      │
│  AKGEC — Library Live Status                │  ← Page heading
│  4 regions · Last full refresh: 10:24:05 AM          │  ← Subtitle (monospace)
│                                                      │
│  ┌────────────────────┐  ┌────────────────────┐      │
│  │ ENTRANCE / LOBBY   │  │ MAIN READING HALL  │      │
│  │ FREE          [🟢] │  │ MODERATE      [🟡] │      │
│  │ 12            / 40 │  │ 62            / 80 │      │
│  │ ████░░░░░░░░░░░░░  │  │ ██████████░░░░░░░  │      │
│  │ Updated 2s ago     │  │ Updated 1s ago     │      │
│  └────────────────────┘  └────────────────────┘      │
│                                                      │
│  ┌────────────────────┐  ┌────────────────────┐      │
│  │ UPPER FLOOR        │  │ GROUP STUDY        │      │
│  │ FULL          [🔴] │  │ FREE          [🟢] │      │
│  │ 28            / 30 │  │ 8             / 25 │      │
│  │ ████████████████░  │  │ ████░░░░░░░░░░░░░  │      │
│  │ Updated 4s ago     │  │ Updated 2s ago     │      │
│  └────────────────────┘  └────────────────────┘      │
│                                                      │
├──────────────────────────────────────────────────────┤
│  💡 Group Study is the least crowded — 8 / 25 people │  ← SmartSuggestionStrip
└──────────────────────────────────────────────────────┘

Screen 2 — Admin Login (Desktop, 1440×900)
Full-page dark background. Centered AdminLoginForm card. Logo/title above the card.
States to show:

Default (empty form)
Error state ("Invalid credentials" in red)


Screen 3 — Admin Panel (Desktop, 1440×900)
┌──────────────────────────────────────────────────────┐
│  ⚙ Admin Panel              admin@bits-hyd  [Logout] │  ← TopNavBar (admin variant)
├──────────────────────────────────────────────────────┤
│                                                      │
│  Regions & Camera Configuration                      │
│                                          [+ Add Region]│
│  ┌──────────────────────────────────────────────┐    │
│  │ Region Name       Camera ID    Cap.  Status  │    │
│  ├──────────────────────────────────────────────┤    │
│  │ Entrance / Lobby  cam_01       40    ● Live ✏│    │
│  │ Main Reading Hall cam_02       80    ● Live ✏│    │
│  │ Upper Floor       cam_03       30    ● Live ✏│    │
│  │ Group Study       cam_04       25    ✗ Off  ✏│    │
│  └──────────────────────────────────────────────┘    │
│                                                      │
│  Camera Feed Health                                  │
│  cam_01 ● Live · last ping 1s                        │
│  cam_02 ● Live · last ping 2s                        │
│  cam_03 ● Live · last ping 3s                        │
│  cam_04 ✗ Disconnected · last seen 4m ago            │
└──────────────────────────────────────────────────────┘
Also design: Edit Region Modal overlaid on this screen (open state).

Screen 4 — Offline / Degraded State (Desktop)
Same as Screen 1 but cam_04 (Group Study) is offline:

That card uses the offline variant — grayed, dashed border
Count shows "— / 25" with label "Camera offline · Last known: 8"
SmartSuggestion updates to exclude offline region


Screen 5 — Mobile Student Dashboard (390×844)
Single column. Cards are full-width. Count number is slightly smaller (24px). Status badge is top-right of card. Suggestion strip is at the bottom, scrolls with content.
┌───────────────────────────┐
│ ● Campus Library  2s ago  │
├───────────────────────────┤
│ ┌─────────────────────┐   │
│ │ ENTRANCE     [FREE] │   │
│ │ 12  /  40           │   │
│ │ ████░░░░░░░░░░░░░   │   │
│ └─────────────────────┘   │
│ ┌─────────────────────┐   │
│ │ MAIN HALL  [MODERATE│   │
│ │ 62  /  80           │   │
│ │ ██████████░░░░░░░   │   │
│ └─────────────────────┘   │
│  ... (2 more cards)       │
├───────────────────────────┤
│ 💡 Group Study is freest  │
└───────────────────────────┘

1.8 Figma Component Checklist

 Design Tokens page (color styles, text styles named to match token table)
 RegionCard — 4 variants (free, moderate, full, offline)
 RegionCard — hover state
 StatusBadge — 4 variants
 CapacityBar — 4 variants
 CameraStatusDot — live + disconnected
 AdminTableRow — default + hover + editing
 EditRegionModal — empty + filled + error
 TopNavBar — student + admin variants
 SmartSuggestionStrip
 AdminLoginForm — default + error
 Screen 1: Student Dashboard Desktop
 Screen 2: Admin Login Desktop
 Screen 3: Admin Panel Desktop (with modal overlay variant)
 Screen 4: Offline/Degraded state Desktop
 Screen 5: Mobile Student Dashboard