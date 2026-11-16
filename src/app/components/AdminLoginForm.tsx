import { useState } from "react";
import { Lock, User, Eye, EyeOff } from "lucide-react";

interface AdminLoginFormProps {
  onLoginAttempt: (username: string, password: string) => Promise<void>;
}

export function AdminLoginForm({ onLoginAttempt }: AdminLoginFormProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await onLoginAttempt(username, password);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Invalid credentials");
    } finally {
      setLoading(false);
    }
  };

  const inputBase: React.CSSProperties = {
    width: "100%",
    backgroundColor: "#2A2E42",
    border: "1px solid #334155",
    borderRadius: "8px",
    padding: "10px 12px 10px 36px",
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
    <div style={{
      width: "360px",
      backgroundColor: "#1A1D27",
      borderRadius: "16px",
      padding: "32px",
      display: "flex",
      flexDirection: "column",
      gap: "16px",
      border: "1px solid #2A2E42",
    }}>
      <div style={{ marginBottom: "4px" }}>
        <h2 style={{
          fontFamily: "'DM Sans', sans-serif",
          fontWeight: 700,
          fontSize: "22px",
          color: "#F1F5F9",
          margin: "0 0 4px",
          lineHeight: 1.2,
        }}>
          Admin Login
        </h2>
        <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "13px", color: "#475569" }}>
          AKGEC · Library Management
        </span>
      </div>

      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        {/* Username */}
        <div>
          <label style={labelStyle}>Username</label>
          <div style={{ position: "relative" }}>
            <User size={15} color="#475569" style={{ position: "absolute", left: "12px", top: "50%", transform: "translateY(-50%)", pointerEvents: "none" }} />
            <input
              type="text"
              value={username}
              onChange={e => { setUsername(e.target.value); setError(""); }}
              placeholder="admin"
              autoComplete="username"
              style={inputBase}
              onFocus={e => { (e.target as HTMLInputElement).style.borderColor = "#6366F1"; }}
              onBlur={e => { (e.target as HTMLInputElement).style.borderColor = "#334155"; }}
            />
          </div>
        </div>

        {/* Password */}
        <div>
          <label style={labelStyle}>Password</label>
          <div style={{ position: "relative" }}>
            <Lock size={15} color="#475569" style={{ position: "absolute", left: "12px", top: "50%", transform: "translateY(-50%)", pointerEvents: "none" }} />
            <input
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={e => { setPassword(e.target.value); setError(""); }}
              placeholder="••••••••"
              autoComplete="current-password"
              style={{ ...inputBase, paddingRight: "40px" }}
              onFocus={e => { (e.target as HTMLInputElement).style.borderColor = "#6366F1"; }}
              onBlur={e => { (e.target as HTMLInputElement).style.borderColor = "#334155"; }}
            />
            <button
              type="button"
              onClick={() => setShowPassword(p => !p)}
              style={{
                position: "absolute",
                right: "10px",
                top: "50%",
                transform: "translateY(-50%)",
                background: "none",
                border: "none",
                cursor: "pointer",
                color: "#475569",
                padding: "2px",
                display: "flex",
                alignItems: "center",
              }}
            >
              {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
            </button>
          </div>
        </div>

        {/* Error */}
        {error && (
          <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "13px", color: "#EF4444" }}>
            {error}
          </span>
        )}

        <button
          type="submit"
          disabled={loading}
          style={{
            width: "100%",
            backgroundColor: "#6366F1",
            border: "none",
            borderRadius: "8px",
            padding: "12px",
            color: "#fff",
            fontFamily: "'DM Sans', sans-serif",
            fontWeight: 600,
            fontSize: "14px",
            cursor: loading ? "wait" : "pointer",
            transition: "background-color 0.2s",
            marginTop: "4px",
            opacity: loading ? 0.8 : 1,
          }}
          onMouseEnter={e => { if (!loading) (e.currentTarget as HTMLButtonElement).style.backgroundColor = "#4F46E5"; }}
          onMouseLeave={e => { if (!loading) (e.currentTarget as HTMLButtonElement).style.backgroundColor = "#6366F1"; }}
        >
          {loading ? "Authenticating…" : "Login"}
        </button>
      </form>
    </div>
  );
}
