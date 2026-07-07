import { useState } from "react";
import { Toaster } from "@/components/ui/sonner";
import { toast } from "sonner";
import { createLicenseRequest } from "@/lib/licenseApi";

const INSTALL_ID_RE = /^CD-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$/;

export default function RequestLicensePage() {
  const [form, setForm] = useState({
    install_id: "",
    company_name: "",
    contact_name: "",
    email: "",
    phone: "",
    tax_id: "",
    plan_requested: "STD",
    notes: "",
    consent: false,
    website: "", // honeypot
  });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    const installId = form.install_id.trim().toUpperCase();
    if (!INSTALL_ID_RE.test(installId)) {
      setErr(
        "L'Install ID ha de tenir el format CD-XXXX-XXXX-XXXX-XXXX. El pots trobar al modal d'activació de l'aplicació.",
      );
      return;
    }
    setBusy(true);
    try {
      await createLicenseRequest({
        install_id: installId,
        company_name: form.company_name.trim(),
        contact_name: form.contact_name.trim() || null,
        email: form.email.trim(),
        phone: form.phone.trim() || null,
        tax_id: form.tax_id.trim() || null,
        plan_requested: form.plan_requested,
        notes: form.notes.trim() || null,
        consent: form.consent,
        website: form.website, // honeypot; humans leave empty
      });
      setDone(true);
      toast.success("Sol·licitud enviada");
    } catch (ex) {
      const msg = ex?.response?.data?.detail;
      setErr(typeof msg === "string" ? msg : JSON.stringify(msg) || ex.message);
    } finally {
      setBusy(false);
    }
  };

  const inputStyle = {
    width: "100%",
    padding: "11px 14px",
    background: "#0f172a",
    border: "1.5px solid #334155",
    borderRadius: 8,
    color: "#e2e8f0",
    fontFamily: "'Courier New', monospace",
    fontSize: 13,
    boxSizing: "border-box",
  };
  const labelStyle = {
    display: "block",
    fontSize: 11,
    color: "#f5b301",
    letterSpacing: 1.5,
    fontWeight: 700,
    marginBottom: 6,
  };

  if (done) {
    return (
      <div
        data-testid="request-success-screen"
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
        <div
          style={{
            background: "#1e293b",
            border: "2px solid #22c55e",
            borderRadius: 16,
            padding: 40,
            maxWidth: 520,
            width: "100%",
            textAlign: "center",
            boxShadow: "0 20px 60px rgba(0,0,0,0.5)",
          }}
        >
          <div style={{ fontSize: 64, marginBottom: 12 }}>✓</div>
          <h1 style={{ color: "#22c55e", margin: "0 0 12px 0", fontSize: 26 }}>
            Sol·licitud enviada!
          </h1>
          <p style={{ color: "#cbd5e1", lineHeight: 1.6, fontSize: 15 }}>
            Hem rebut la teva sol·licitud correctament.
            <br />
            Et contactarem aviat per email amb la teva clau d'activació.
          </p>
          <p style={{ color: "#94a3b8", fontSize: 12, marginTop: 24 }}>
            Marc Brugulat Lopez · Caja del Día
          </p>
        </div>
      </div>
    );
  }

  return (
    <>
      <div
        data-testid="request-license-page"
        style={{
          minHeight: "100vh",
          background: "linear-gradient(135deg,#0f172a,#1e293b)",
          padding: "40px 20px",
          fontFamily: "Georgia, serif",
          color: "#e2e8f0",
        }}
      >
        <form
          onSubmit={submit}
          style={{
            maxWidth: 620,
            margin: "0 auto",
            background: "#1e293b",
            border: "2px solid #f5b301",
            borderRadius: 16,
            padding: 40,
            boxShadow: "0 20px 60px rgba(0,0,0,0.5)",
          }}
        >
          <div style={{ textAlign: "center", marginBottom: 28 }}>
            <div style={{ fontSize: 48, marginBottom: 8 }}>📮</div>
            <h1 style={{ margin: 0, color: "#f5b301", fontSize: 26, letterSpacing: 1 }}>
              Sol·licitar llicència
            </h1>
            <p style={{ color: "#94a3b8", fontSize: 13, margin: "8px 0 0" }}>
              Caja del Día · Software comercial · Marc Brugulat Lopez
            </p>
          </div>

          <div
            style={{
              background: "#0f172a",
              border: "1px solid #334155",
              borderRadius: 8,
              padding: 14,
              marginBottom: 22,
              fontSize: 12,
              color: "#94a3b8",
              lineHeight: 1.55,
            }}
          >
            <b style={{ color: "#f5b301" }}>Com trobar l'Install ID:</b> obre l'aplicació{" "}
            <b>Caja del Día</b> · al modal d'activació apareixerà un codi amb el format{" "}
            <code style={{ color: "#e2e8f0" }}>CD-XXXX-XXXX-XXXX-XXXX</code>. Copia'l i
            enganxa'l aquí sota.
          </div>

          <div style={{ display: "grid", gap: 14 }}>
            <div>
              <label style={labelStyle}>INSTALL ID *</label>
              <input
                data-testid="req-install-id"
                required
                placeholder="CD-XXXX-XXXX-XXXX-XXXX"
                value={form.install_id}
                onChange={(e) => setForm({ ...form, install_id: e.target.value.toUpperCase() })}
                style={inputStyle}
              />
            </div>
            <div>
              <label style={labelStyle}>NOM DE L'EMPRESA *</label>
              <input
                data-testid="req-company"
                required
                value={form.company_name}
                onChange={(e) => setForm({ ...form, company_name: e.target.value })}
                style={{ ...inputStyle, fontFamily: "Georgia, serif" }}
              />
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div>
                <label style={labelStyle}>PERSONA DE CONTACTE</label>
                <input
                  data-testid="req-contact"
                  value={form.contact_name}
                  onChange={(e) => setForm({ ...form, contact_name: e.target.value })}
                  style={{ ...inputStyle, fontFamily: "Georgia, serif" }}
                />
              </div>
              <div>
                <label style={labelStyle}>NIF / CIF</label>
                <input
                  data-testid="req-taxid"
                  value={form.tax_id}
                  onChange={(e) => setForm({ ...form, tax_id: e.target.value })}
                  style={inputStyle}
                />
              </div>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 12 }}>
              <div>
                <label style={labelStyle}>EMAIL *</label>
                <input
                  data-testid="req-email"
                  required
                  type="email"
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  style={inputStyle}
                />
              </div>
              <div>
                <label style={labelStyle}>TELÈFON</label>
                <input
                  data-testid="req-phone"
                  value={form.phone}
                  onChange={(e) => setForm({ ...form, phone: e.target.value })}
                  style={inputStyle}
                />
              </div>
            </div>
            <div>
              <label style={labelStyle}>PLAN SOL·LICITAT</label>
              <select
                data-testid="req-plan"
                value={form.plan_requested}
                onChange={(e) => setForm({ ...form, plan_requested: e.target.value })}
                style={inputStyle}
              >
                <option value="TRIAL">TRIAL — Prova gratuïta</option>
                <option value="STD">STD — Estàndard</option>
                <option value="PREMIUM">PREMIUM — Ampliat</option>
              </select>
            </div>
            <div>
              <label style={labelStyle}>NOTES / COMENTARIS</label>
              <textarea
                data-testid="req-notes"
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
                rows={3}
                placeholder="Explica'ns qualsevol cosa que ens ajudi a preparar la teva llicència…"
                style={{ ...inputStyle, resize: "vertical", fontFamily: "Georgia, serif" }}
              />
            </div>
          </div>

          {err && (
            <div
              data-testid="request-error"
              style={{
                color: "#ef4444",
                fontSize: 13,
                marginTop: 14,
                padding: 10,
                background: "rgba(239,68,68,0.1)",
                borderRadius: 6,
                border: "1px solid rgba(239,68,68,0.3)",
              }}
            >
              ✗ {err}
            </div>
          )}

          {/* Honeypot: visually hidden, tab-index -1. Real users won't fill it. */}
          <div style={{ position: "absolute", left: "-9999px", top: "-9999px" }} aria-hidden="true">
            <label>Web (deixa buit)</label>
            <input
              type="text"
              tabIndex={-1}
              autoComplete="off"
              value={form.website}
              onChange={(e) => setForm({ ...form, website: e.target.value })}
            />
          </div>

          <label
            data-testid="req-consent-label"
            style={{
              display: "flex",
              alignItems: "flex-start",
              gap: 10,
              marginTop: 20,
              padding: 12,
              background: "#0f172a",
              border: "1px solid #334155",
              borderRadius: 8,
              cursor: "pointer",
              fontSize: 12,
              color: "#cbd5e1",
              lineHeight: 1.5,
            }}
          >
            <input
              data-testid="req-consent"
              type="checkbox"
              checked={form.consent}
              onChange={(e) => setForm({ ...form, consent: e.target.checked })}
              style={{ marginTop: 3, transform: "scale(1.2)", accentColor: "#f5b301" }}
            />
            <span>
              He llegit i accepto la{" "}
              <a
                href="/privacy"
                target="_blank"
                rel="noreferrer"
                style={{ color: "#f5b301", textDecoration: "underline" }}
              >
                política de privacitat
              </a>
              . Les meves dades es tractaran per gestionar la meva sol·licitud de llicència.
            </span>
          </label>

          <button
            data-testid="request-submit"
            type="submit"
            disabled={busy || !form.consent}
            style={{
              marginTop: 18,
              width: "100%",
              padding: 14,
              background:
                busy || !form.consent
                  ? "#475569"
                  : "linear-gradient(135deg,#f5b301,#d97706)",
              color: "#0f172a",
              border: "none",
              borderRadius: 10,
              fontFamily: "Georgia, serif",
              fontSize: 16,
              fontWeight: 700,
              letterSpacing: 2,
              cursor: busy || !form.consent ? "not-allowed" : "pointer",
              textTransform: "uppercase",
            }}
          >
            {busy ? "Enviant…" : "✉ Enviar sol·licitud"}
          </button>

          <p
            style={{
              textAlign: "center",
              color: "#64748b",
              fontSize: 11,
              marginTop: 22,
              paddingTop: 18,
              borderTop: "1px solid #334155",
              lineHeight: 1.55,
            }}
          >
            En enviar, acceptes que rebis la teva clau de llicència a l'adreça de correu
            indicada. Marc Brugulat Lopez es reserva el dret d'aprovar o denegar
            sol·licituds.
          </p>
        </form>
      </div>
      <Toaster position="top-right" richColors closeButton theme="dark" />
    </>
  );
}
