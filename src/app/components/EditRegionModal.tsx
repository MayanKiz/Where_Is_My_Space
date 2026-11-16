import { useState } from "react";
import { X, Trash2 } from "lucide-react";
import { Region } from "./types";

interface EditRegionModalProps {
  region: Region;
  isNew?: boolean;
  onSave: (updated: Region) => void;
  onDelete?: () => void;
  onClose: () => void;
}

export function EditRegionModal({ region, isNew = false, onSave, onDelete, onClose }: EditRegionModalProps) {
  const [name, setName] = useState(region.name);
  const [camId, setCamId] = useState(region.camId);
  const [capacity, setCapacity] = useState(String(region.capacity));
  const [notes, setNotes] = useState(region.locationNotes);
  const [section, setSection] = useState<"library" | "canteen" | "lt">(region.section ?? "library");
  const [confirmDelete, setConfirmDelete] = useState(false);

  const handleSave = () => {
    onSave({ ...region, name, camId, capacity: parseInt(capacity) || region.capacity, locationNotes: notes, section });
  };

  const inputStyle: React.CSSProperties = {
    width: "100%",
    backgroundColor: "#2A2E42",
    border: "1px solid #334155",
    borderRadius: "8px",
    padding: "10px 12px",
    color: "#F1F5F9",
    fontFamily: "'IBM Plex Mono', monospace",
    fontSize: "14px",
    outline: "none",
    boxSizing: "border-box",
    transition: "border-color 0.2s",
  };

  const labelStyle: React.CSSProperties = {
    fontFamily: "'DM Sans', sans-serif",
    fontSize: "13px",
    fontWeight: 500,
    color: "#94A3B8",
    marginBottom: "6px",
    display: "block",
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(0,0,0,0.6)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 50,
        backdropFilter: "blur(2px)",
      }}
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        style={{
          width: "480px",
          maxWidth: "calc(100vw - 32px)",
          backgroundColor: "#22263A",
          borderRadius: "16px",
          padding: "24px",
          display: "flex",
          flexDirection: "column",
          gap: "16px",
          border: "1px solid #2A2E42",
          boxShadow: "0 8px 40px rgba(0,0,0,0.5)",
        }}
      >
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span
            style={{
              fontFamily: "'DM Sans', sans-serif",
              fontWeight: 700,
              fontSize: "18px",
              color: "#F1F5F9",
            }}
          >
            {isNew ? "Add Region" : "Edit Region"}
          </span>
          <button
            onClick={onClose}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              color: "#475569",
              padding: "4px",
              borderRadius: "6px",
              display: "flex",
              alignItems: "center",
              transition: "color 0.2s",
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.color = "#F1F5F9"; }}
            onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.color = "#475569"; }}
          >
            <X size={20} />
          </button>
        </div>

        {/* Region Name */}
        <div>
          <label style={labelStyle}>Region Name</label>
          <input
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="e.g. Main Reading Hall"
            style={inputStyle}
            onFocus={e => { (e.target as HTMLInputElement).style.borderColor = "#6366F1"; }}
            onBlur={e => { (e.target as HTMLInputElement).style.borderColor = "#334155"; }}
          />
        </div>

        {/* Camera ID */}
        <div>
          <label style={labelStyle}>Camera ID / URL</label>
          <input
            type="text"
            value={camId}
            onChange={e => setCamId(e.target.value)}
            placeholder="e.g. cam_02"
            style={inputStyle}
            onFocus={e => { (e.target as HTMLInputElement).style.borderColor = "#6366F1"; }}
            onBlur={e => { (e.target as HTMLInputElement).style.borderColor = "#334155"; }}
          />
          <span
            style={{
              fontFamily: "'DM Sans', sans-serif",
              fontSize: "11px",
              color: "#475569",
              marginTop: "4px",
              display: "block",
            }}
          >
            ID the ML node uses when posting counts
          </span>
        </div>

        {/* Max Capacity */}
        <div>
          <label style={labelStyle}>Max Capacity</label>
          <input
            type="number"
            value={capacity}
            onChange={e => setCapacity(e.target.value)}
            min={1}
            style={inputStyle}
            onFocus={e => { (e.target as HTMLInputElement).style.borderColor = "#6366F1"; }}
            onBlur={e => { (e.target as HTMLInputElement).style.borderColor = "#334155"; }}
          />
        </div>

        {/* Section */}
        <div>
          <label style={labelStyle}>Section</label>
          <div style={{ display: "flex", gap: "8px" }}>
            {(["library", "canteen", "lt"] as const).map(s => {
              const accent = s === "canteen" ? "#06B6D4" : s === "lt" ? "#F59E0B" : "#6366F1";
              const bg = s === "canteen" ? "#0C2A30" : s === "lt" ? "#2D1B00" : "#1E1F3A";
              const label = s === "library" ? "📚 Library" : s === "canteen" ? "🍽️ CS-IT Canteen" : "🏫 LT";
              return (
                <button
                  key={s}
                  onClick={() => setSection(s)}
                  style={{
                    flex: 1,
                    padding: "9px",
                    borderRadius: "8px",
                    border: `1px solid ${section === s ? accent : "#334155"}`,
                    backgroundColor: section === s ? bg : "transparent",
                    color: section === s ? accent : "#475569",
                    fontFamily: "'DM Sans', sans-serif",
                    fontWeight: 600,
                    fontSize: "13px",
                    cursor: "pointer",
                    textTransform: "capitalize",
                    transition: "all 0.15s",
                  }}
                >
                  {label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Notes */}
        <div>
          <label style={labelStyle}>Notes (optional)</label>
          <textarea
            value={notes}
            onChange={e => setNotes(e.target.value)}
            rows={3}
            style={{
              ...inputStyle,
              resize: "vertical",
              fontFamily: "'DM Sans', sans-serif",
            }}
            onFocus={e => { (e.target as HTMLTextAreaElement).style.borderColor = "#6366F1"; }}
            onBlur={e => { (e.target as HTMLTextAreaElement).style.borderColor = "#334155"; }}
          />
        </div>

        {/* Delete confirmation strip */}
        {!isNew && onDelete && confirmDelete && (
          <div style={{
            backgroundColor: "#2D0707",
            border: "1px solid #EF4444",
            borderRadius: "8px",
            padding: "12px 16px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "12px",
          }}>
            <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "13px", color: "#FCA5A5" }}>
              Delete this region permanently?
            </span>
            <div style={{ display: "flex", gap: "8px", flexShrink: 0 }}>
              <button
                onClick={() => setConfirmDelete(false)}
                style={{
                  background: "none",
                  border: "1px solid #475569",
                  borderRadius: "6px",
                  padding: "5px 12px",
                  color: "#94A3B8",
                  fontFamily: "'DM Sans', sans-serif",
                  fontSize: "12px",
                  cursor: "pointer",
                }}
              >
                Cancel
              </button>
              <button
                onClick={onDelete}
                style={{
                  backgroundColor: "#EF4444",
                  border: "none",
                  borderRadius: "6px",
                  padding: "5px 12px",
                  color: "#fff",
                  fontFamily: "'DM Sans', sans-serif",
                  fontWeight: 600,
                  fontSize: "12px",
                  cursor: "pointer",
                }}
              >
                Delete
              </button>
            </div>
          </div>
        )}

        {/* Actions */}
        <div style={{ display: "flex", gap: "8px", justifyContent: "space-between", marginTop: "4px" }}>
          {/* Delete button — only for existing regions */}
          {!isNew && onDelete && !confirmDelete ? (
            <button
              onClick={() => setConfirmDelete(true)}
              style={{
                background: "none",
                border: "1px solid #334155",
                borderRadius: "8px",
                padding: "10px 14px",
                color: "#475569",
                fontFamily: "'DM Sans', sans-serif",
                fontSize: "13px",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: "6px",
                transition: "all 0.2s",
              }}
              onMouseEnter={e => {
                const b = e.currentTarget as HTMLButtonElement;
                b.style.borderColor = "#EF4444";
                b.style.color = "#EF4444";
              }}
              onMouseLeave={e => {
                const b = e.currentTarget as HTMLButtonElement;
                b.style.borderColor = "#334155";
                b.style.color = "#475569";
              }}
            >
              <Trash2 size={14} />
              Delete
            </button>
          ) : (
            <span />
          )}

          <div style={{ display: "flex", gap: "10px" }}>
            <button
              onClick={onClose}
              style={{
                background: "none",
                border: "1px solid #2A2E42",
                borderRadius: "8px",
                padding: "10px 20px",
                color: "#94A3B8",
                fontFamily: "'DM Sans', sans-serif",
                fontWeight: 500,
                fontSize: "14px",
                cursor: "pointer",
                transition: "border-color 0.2s, color 0.2s",
              }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLButtonElement).style.borderColor = "#475569";
                (e.currentTarget as HTMLButtonElement).style.color = "#F1F5F9";
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLButtonElement).style.borderColor = "#2A2E42";
                (e.currentTarget as HTMLButtonElement).style.color = "#94A3B8";
              }}
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              style={{
                backgroundColor: "#6366F1",
                border: "none",
                borderRadius: "8px",
                padding: "10px 20px",
                color: "#fff",
                fontFamily: "'DM Sans', sans-serif",
                fontWeight: 600,
                fontSize: "14px",
                cursor: "pointer",
                transition: "background-color 0.2s",
              }}
              onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.backgroundColor = "#4F46E5"; }}
              onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.backgroundColor = "#6366F1"; }}
            >
              {isNew ? "Add Region" : "Save Changes"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
