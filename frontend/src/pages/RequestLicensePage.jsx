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
    plan_requested: "STD_ANY",
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
    // Install ID is now OPTIONAL. Si el client encara no té l'app, deixa-ho buit.
    if (installId && !INSTALL_ID_RE.test(installId)) {
      setErr(
        "El format de l'Install ID no és vàlid. Ha de ser CD-XXXX-XXXX-XXXX-XXXX o deixa'l buit si encara no tens l'app.",
      );
      return;
    }
    setBusy(true);
    try {
      await createLicenseRequest({
        install_id: installId || null,
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
      let humanMsg = ex.message || "Error enviant la sol·licitud";
      if (Array.isArray(msg)) {
        // Pydantic error blob → convert to human message
        const first = msg[0];
        if (first) {
          const field = (first.loc || []).slice(1).join(".") || "camp";
          humanMsg = `Error al camp "${field}": ${first.msg || "no vàlid"}`;
        }
      } else if (typeof msg === "string") {
        humanMsg = msg;
      }
      setErr(humanMsg);
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
            Hem rebut la teva sol·licitud correctament. Et contactarem al teu email amb els <b>detalls de pagament</b>.
          </p>

          <div style={{ background: "#0f172a", border: "1px solid #f5b301", borderRadius: 10, padding: 18, margin: "22px 0", textAlign: "left" }}>
            <div style={{ color: "#f5b301", fontSize: 11, letterSpacing: 1.5, fontWeight: 700, marginBottom: 10 }}>📋 PROPERS PASSOS</div>
            <ol style={{ color: "#cbd5e1", fontSize: 13, lineHeight: 1.8, margin: 0, paddingLeft: 20 }}>
              <li>Revisarem la teva sol·licitud en <b>menys de 24h</b></li>
              <li>T'enviarem un email amb la <b>factura proforma</b> i les dades de transferència bancària</li>
              <li>Un cop <b>rebem el pagament</b>, t'enviem la clau d'activació i el link de descàrrega de l'app</li>
              <li>Instal·les l'app, enganxes la clau i ja pots començar a treballar</li>
            </ol>
          </div>

          <p style={{ color: "#94a3b8", fontSize: 11, marginTop: 8 }}>
            💬 Dubtes? Escriu a <a href="mailto:info@medicarplus.es" style={{ color: "#f5b301" }}>info@medicarplus.es</a>
          </p>
          <p style={{ color: "#94a3b8", fontSize: 12, marginTop: 24 }}>
            M.Brugulat Lopez · MediCar Plus
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
              MediCar Plus · Software comercial · M.Brugulat Lopez
            </p>
          </div>

          {/* PRICING CARDS */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, marginBottom: 24 }}>
            <PricingCard
              title="TRIAL"
              subtitle="Prova"
              price="0€"
              period="30 dies"
              features={["✓ Totes les funcions", "✓ Sense targeta", "✓ 30 dies gratis"]}
              accent="#64748b"
              selected={form.plan_requested === "TRIAL"}
              onClick={() => setForm({ ...form, plan_requested: "TRIAL" })}
            />
            <PricingCard
              title="STD"
              subtitle="Estàndard"
              price="29,90€"
              period="/mes"
              altPrice="299,90€/any"
              savings="16% descompte"
              features={["✓ Caixa del dia", "✓ IRPF + Llibreta", "✓ Estadístiques", "✓ Suport email"]}
              accent="#f5b301"
              hasBillingToggle
              billingValue={form.plan_requested}
              onMonthly={() => setForm({ ...form, plan_requested: "STD_MES" })}
              onYearly={() => setForm({ ...form, plan_requested: "STD_ANY" })}
              monthlyValue="STD_MES"
              yearlyValue="STD_ANY"
            />
            <PricingCard
              title="PREMIUM"
              subtitle="Ampliat"
              price="39,90€"
              period="/mes"
              altPrice="399,90€/any"
              savings="17% descompte"
              features={["✓ Tot STD +", "✓ SMS / WhatsApp", "✓ Cercador clients", "✓ Suport prioritari"]}
              accent="#3ddc97"
              badge="POPULAR"
              hasBillingToggle
              billingValue={form.plan_requested}
              onMonthly={() => setForm({ ...form, plan_requested: "PREMIUM_MES" })}
              onYearly={() => setForm({ ...form, plan_requested: "PREMIUM_ANY" })}
              monthlyValue="PREMIUM_MES"
              yearlyValue="PREMIUM_ANY"
            />
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
            <b style={{ color: "#f5b301" }}>ℹ️ Sobre l'Install ID:</b> és un codi únic que identifica la teva instal·lació.
            Si <b>encara no tens l'app</b>, deixa aquest camp buit — quan aprovem la teva sol·licitud t'enviarem l'app perquè el generi.
            Si <b>ja tens l'app instal·lada</b>, obre-la, ves al modal d'activació i copia el codi{" "}
            <code style={{ color: "#e2e8f0" }}>CD-XXXX-XXXX-XXXX-XXXX</code>.
          </div>

          <div
            style={{
              background: "linear-gradient(135deg,#065f46 0%,#0f172a 100%)",
              border: "1px solid #059669",
              borderRadius: 8,
              padding: 14,
              marginBottom: 22,
              fontSize: 12,
              color: "#cbd5e1",
              lineHeight: 1.55,
            }}
          >
            <b style={{ color: "#7ee3aa", fontSize: 13 }}>💰 Forma de pagament: Transferència bancària</b>
            <div style={{ marginTop: 6 }}>
              Un cop rebem la teva sol·licitud, t'enviarem un <b>email amb la factura proforma</b> i les dades bancàries per fer la transferència. Un cop confirmat el pagament, rebràs la clau d'activació.
            </div>
            <div style={{ marginTop: 6, fontSize: 11, color: "#94a3b8", fontStyle: "italic" }}>
              Sense compromís: només pagues si acceptes l'oferta que et fem.
            </div>
          </div>

          <div style={{ display: "grid", gap: 14 }}>
            <div>
              <label style={labelStyle}>INSTALL ID <span style={{ color: "#64748b", fontWeight: 400 }}>(opcional)</span></label>
              <input
                data-testid="req-install-id"
                placeholder="CD-XXXX-XXXX-XXXX-XXXX o deixa-ho buit"
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
              <label style={labelStyle}>PLAN SELECCIONAT</label>
              <div style={{ padding: "10px 14px", background: "#0f172a", border: "1px solid #334155", borderRadius: 8, color: "#f5b301", fontFamily: "Georgia,serif", fontSize: 13 }}>
                {form.plan_requested === "TRIAL" && "🆓 TRIAL — Prova gratuïta 30 dies"}
                {form.plan_requested === "STD_MES" && "📦 STD Mensual — 29,90€/mes"}
                {form.plan_requested === "STD_ANY" && "📦 STD Anual — 299,90€/any (estalvies 16%)"}
                {form.plan_requested === "PREMIUM_MES" && "⭐ PREMIUM Mensual — 39,90€/mes"}
                {form.plan_requested === "PREMIUM_ANY" && "⭐ PREMIUM Anual — 399,90€/any (estalvies 17%)"}
                <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 4, fontStyle: "italic" }}>
                  Selecciona un altre pla clicant les targetes de dalt.
                </div>
              </div>
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
            indicada. M.Brugulat Lopez es reserva el dret d'aprovar o denegar
            sol·licituds.
          </p>
        </form>
      </div>
      <Toaster position="top-right" richColors closeButton theme="dark" />
    </>
  );
}

/** PricingCard · Targeta per triar pla amb toggle mensual/anual opcional */
function PricingCard({
  title, subtitle, price, period, altPrice, savings, features, accent,
  selected, onClick, badge,
  hasBillingToggle, billingValue, onMonthly, onYearly, monthlyValue, yearlyValue,
}) {
  const isSelected =
    selected ||
    (hasBillingToggle && (billingValue === monthlyValue || billingValue === yearlyValue));
  const isMonthly = hasBillingToggle && billingValue === monthlyValue;
  const isYearly = hasBillingToggle && billingValue === yearlyValue;

  return (
    <div
      onClick={hasBillingToggle ? undefined : onClick}
      style={{
        position: "relative",
        background: isSelected ? "#0f172a" : "#141a24",
        border: `2px solid ${isSelected ? accent : "#334155"}`,
        borderRadius: 12,
        padding: 12,
        cursor: hasBillingToggle ? "default" : "pointer",
        transition: "all .2s ease",
        boxShadow: isSelected ? `0 4px 18px ${accent}30` : "none",
        display: "flex",
        flexDirection: "column",
        gap: 6,
      }}
    >
      {badge && (
        <div
          style={{
            position: "absolute",
            top: -10,
            right: 8,
            background: accent,
            color: "#0f172a",
            fontSize: 9,
            padding: "2px 8px",
            borderRadius: 4,
            fontWeight: 700,
            letterSpacing: 1,
          }}
        >
          {badge}
        </div>
      )}
      <div style={{ color: accent, fontSize: 11, fontWeight: 700, letterSpacing: 1.5 }}>{title}</div>
      <div style={{ color: "#94a3b8", fontSize: 10, marginTop: -4 }}>{subtitle}</div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 4, marginTop: 4 }}>
        <div style={{ color: "#e2e8f0", fontSize: 22, fontWeight: 700 }}>
          {hasBillingToggle && isYearly ? altPrice.split("/")[0] : price}
        </div>
        <div style={{ color: "#64748b", fontSize: 11 }}>
          {hasBillingToggle && isYearly ? "/any" : period}
        </div>
      </div>
      {hasBillingToggle && (
        <div style={{ display: "flex", gap: 4, marginTop: 4 }}>
          <button
            type="button"
            onClick={onMonthly}
            style={{
              flex: 1,
              padding: "5px 6px",
              background: isMonthly ? accent : "transparent",
              color: isMonthly ? "#0f172a" : "#94a3b8",
              border: `1px solid ${isMonthly ? accent : "#334155"}`,
              borderRadius: 4,
              fontSize: 10,
              fontWeight: 700,
              cursor: "pointer",
            }}
          >
            MENSUAL
          </button>
          <button
            type="button"
            onClick={onYearly}
            style={{
              flex: 1,
              padding: "5px 6px",
              background: isYearly ? accent : "transparent",
              color: isYearly ? "#0f172a" : "#94a3b8",
              border: `1px solid ${isYearly ? accent : "#334155"}`,
              borderRadius: 4,
              fontSize: 10,
              fontWeight: 700,
              cursor: "pointer",
              position: "relative",
            }}
          >
            ANUAL
          </button>
        </div>
      )}
      {savings && hasBillingToggle && (
        <div style={{ color: accent, fontSize: 9, fontStyle: "italic", textAlign: "center", marginTop: 2 }}>
          {isYearly ? `✓ ${savings}` : `↓ ${altPrice} anual`}
        </div>
      )}
      <div style={{ marginTop: 6, display: "flex", flexDirection: "column", gap: 3, borderTop: "1px solid #334155", paddingTop: 8 }}>
        {features.map((f, i) => (
          <div key={i} style={{ color: "#cbd5e1", fontSize: 10 }}>{f}</div>
        ))}
      </div>
    </div>
  );
}
