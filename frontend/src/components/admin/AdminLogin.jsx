import { useState } from "react";
import { AdminTokenStore, pingAdmin } from "@/lib/licenseApi";

export default function AdminLogin({ onLogin }) {
  const [token, setToken] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      const ok = await pingAdmin(token.trim());
      if (!ok) {
        setErr("Token invàlid. Comprova-ho.");
        setLoading(false);
        return;
      }
      AdminTokenStore.set(token.trim());
      onLogin();
    } catch (ex) {
      setErr("Error de connexió: " + (ex?.message || "unknown"));
      setLoading(false);
    }
  };

  return (
    <div
      data-testid="admin-login-screen"
      style={{
        minHeight: "100vh",
        background: "linear-gradient(135deg,#0f172a,#1e293b)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 20,
        fontFamily: "Georgia, serif",
        color: "#e2e8f0",
      }}
    >
      <form
        onSubmit={submit}
        style={{
          background: "#1e293b",
          border: "2px solid #f5b301",
          borderRadius: 16,
          padding: 40,
          maxWidth: 480,
          width: "100%",
          boxShadow: "0 20px 60px rgba(0,0,0,0.5)",
        }}
      >
        <div style={{ textAlign: "center", marginBottom: 28 }}>
          <div style={{ fontSize: 48, marginBottom: 8 }}>🔐</div>
          <h1
            style={{
              margin: 0,
              color: "#f5b301",
              fontSize: 26,
              letterSpacing: 1,
            }}
          >
            Panell d'administració
          </h1>
          <p style={{ color: "#94a3b8", fontSize: 13, margin: "8px 0 0" }}>
            MediCar Plus · License Server
          </p>
        </div>
        <label
          style={{
            display: "block",
            fontSize: 12,
            color: "#f5b301",
            letterSpacing: 1.5,
            fontWeight: 700,
            marginBottom: 8,
          }}
        >
          ADMIN TOKEN
        </label>
        <input
          data-testid="admin-token-input"
          type="password"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          placeholder="MB-ADMIN-..."
          autoFocus
          style={{
            width: "100%",
            padding: 12,
            background: "#0f172a",
            border: "2px solid #475569",
            borderRadius: 8,
            color: "#e2e8f0",
            fontFamily: "'Courier New', monospace",
            fontSize: 15,
            letterSpacing: 2,
            boxSizing: "border-box",
          }}
        />
        {err && (
          <div
            data-testid="admin-login-error"
            style={{ color: "#ef4444", fontSize: 13, marginTop: 10 }}
          >
            ✗ {err}
          </div>
        )}
        <button
          data-testid="admin-login-submit"
          type="submit"
          disabled={loading || !token.trim()}
          style={{
            marginTop: 22,
            width: "100%",
            padding: 14,
            background:
              loading || !token.trim()
                ? "#475569"
                : "linear-gradient(135deg,#f5b301,#d97706)",
            color: "#0f172a",
            border: "none",
            borderRadius: 10,
            fontFamily: "Georgia, serif",
            fontSize: 16,
            fontWeight: 700,
            letterSpacing: 2,
            cursor: loading ? "wait" : "pointer",
            textTransform: "uppercase",
          }}
        >
          {loading ? "Verificant…" : "✓ Entrar"}
        </button>
        <div
          style={{
            textAlign: "center",
            marginTop: 24,
            paddingTop: 20,
            borderTop: "1px solid #334155",
            color: "#64748b",
            fontSize: 11,
          }}
        >
          Marc Brugulat Lopez · v2 comercial
        </div>
      </form>
    </div>
  );
}
