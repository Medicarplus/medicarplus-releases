import { useState } from "react";
import { Toaster } from "@/components/ui/sonner";
import { toast } from "sonner";
import { createLicenseRequest } from "@/lib/licenseApi";

const INSTALL_ID_RE = /^CD-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$/;
const apiBase = process.env.REACT_APP_BACKEND_URL || "";

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
  const [showInstallId, setShowInstallId] = useState(false);
  const [lookupStatus, setLookupStatus] = useState(null); // null | 'searching' | 'found' | 'notfound'
  const [recognizedInfo, setRecognizedInfo] = useState(null); // { company_name, current_plan, current_status, current_expires_at }
  const INSTALL_ID_PATTERN = /^CD-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$/;

  async function tryLookupInstallId(iid) {
    const clean = String(iid || "").trim().toUpperCase();
    if (!INSTALL_ID_PATTERN.test(clean)) {
      setLookupStatus(null);
      setRecognizedInfo(null);
      return;
    }
    setLookupStatus("searching");
    setRecognizedInfo(null);
    try {
      const res = await fetch(`${apiBase}/api/licenses/lookup/${encodeURIComponent(clean)}`);
      const data = await res.json();
      if (data.found) {
        // Auto-relleno de los campos que estén vacíos (no pisa lo que el usuario haya escrito)
        setForm((prev) => ({
          ...prev,
          company_name: prev.company_name || data.company_name || "",
          contact_name: prev.contact_name || data.contact_name || "",
          email: prev.email || data.email || "",
          phone: prev.phone || data.phone || "",
          tax_id: prev.tax_id || data.tax_id || "",
        }));
        setRecognizedInfo({
          company_name: data.company_name,
          current_plan: data.current_plan,
          current_status: data.current_status,
          current_expires_at: data.current_expires_at,
        });
        setLookupStatus("found");
      } else {
        setLookupStatus("notfound");
      }
    } catch (e) {
      setLookupStatus(null);
    }
  }

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    const installId = form.install_id.trim().toUpperCase();
    // Install ID is now OPTIONAL. Si el cliente aún no tiene la app, déjalo vacío.
    if (installId && !INSTALL_ID_RE.test(installId)) {
      setErr(
        "El formato del Install ID no es válido. Debe ser CD-XXXX-XXXX-XXXX-XXXX o déjalo vacío si aún no tienes la app.",
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
      toast.success("Solicitud enviada");
    } catch (ex) {
      const msg = ex?.response?.data?.detail;
      let humanMsg = ex.message || "Error enviando la solicitud";
      if (Array.isArray(msg)) {
        // Pydantic error blob → convert to human message
        const first = msg[0];
        if (first) {
          const field = (first.loc || []).slice(1).join(".") || "campo";
          humanMsg = `Error en el campo "${field}": ${first.msg || "no válido"}`;
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
            ¡Solicitud enviada!
          </h1>
          <p style={{ color: "#cbd5e1", lineHeight: 1.6, fontSize: 15 }}>
            Hemos recibido tu solicitud correctamente. Te contactaremos a tu email con los <b>detalles de pago</b>.
          </p>

          <div style={{ background: "#0f172a", border: "1px solid #f5b301", borderRadius: 10, padding: 18, margin: "22px 0", textAlign: "left" }}>
            <div style={{ color: "#f5b301", fontSize: 11, letterSpacing: 1.5, fontWeight: 700, marginBottom: 10 }}>📋 PRÓXIMOS PASOS</div>
            <ol style={{ color: "#cbd5e1", fontSize: 13, lineHeight: 1.8, margin: 0, paddingLeft: 20 }}>
              <li>Revisaremos tu solicitud en <b>menos de 24h</b></li>
              <li>Te enviaremos un email con la <b>factura proforma</b> y los datos de transferencia bancaria</li>
              <li>Una vez <b>recibamos el pago</b>, te enviamos la clave de activación y el enlace de descarga de la app</li>
              <li>Instalas la app, pegas la clave y ya puedes empezar a trabajar</li>
            </ol>
          </div>

          <p style={{ color: "#94a3b8", fontSize: 11, marginTop: 8 }}>
            💬 ¿Dudas? Escribe a <a href="mailto:info@medicarplus.es" style={{ color: "#f5b301" }}>info@medicarplus.es</a>
          </p>
          <p style={{ color: "#94a3b8", fontSize: 12, marginTop: 24 }}>
            MediCar Plus
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
            position: "relative",
          }}
        >
          {/* Botón X para volver a la home / cancelar la operación */}
          <a
            href="/"
            data-testid="close-request-license"
            aria-label="Cerrar y volver a la portada"
            title="Cerrar y volver a la portada"
            style={{
              position: "absolute",
              top: 16,
              right: 16,
              width: 36,
              height: 36,
              borderRadius: "50%",
              background: "#0f172a",
              border: "1px solid #475569",
              color: "#94a3b8",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 20,
              textDecoration: "none",
              cursor: "pointer",
              transition: "all .15s",
              fontFamily: "system-ui, sans-serif",
              lineHeight: 1,
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = "#dc2626"; e.currentTarget.style.color = "#fff"; e.currentTarget.style.borderColor = "#dc2626"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "#0f172a"; e.currentTarget.style.color = "#94a3b8"; e.currentTarget.style.borderColor = "#475569"; }}
          >
            ×
          </a>
          <div style={{ textAlign: "center", marginBottom: 28 }}>
            <div style={{ fontSize: 48, marginBottom: 8 }}>📮</div>
            <h1 style={{ margin: 0, color: "#f5b301", fontSize: 26, letterSpacing: 1 }}>
              Solicitar licencia
            </h1>
            <p style={{ color: "#94a3b8", fontSize: 13, margin: "8px 0 0" }}>
              MediCar Plus · Software comercial
            </p>
          </div>

          {/* PRICING CARDS */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, marginBottom: 24 }}>
            <PricingCard
              title="TRIAL"
              subtitle="Prueba"
              price="0€"
              period="60 días"
              features={["✓ Todas las funciones", "✓ Sin tarjeta", "✓ 60 días gratis"]}
              accent="#64748b"
              selected={form.plan_requested === "TRIAL"}
              onClick={() => setForm({ ...form, plan_requested: "TRIAL" })}
            />
            <PricingCard
              title="STD"
              subtitle="Estándar"
              price="29,90€"
              period="/mes"
              altPrice="299,90€/año"
              savings="16% descuento"
              features={["✓ Caja del día", "✓ IRPF + Libreta", "✓ Estadísticas", "✓ Soporte email"]}
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
              subtitle="Ampliado"
              price="39,90€"
              period="/mes"
              altPrice="399,90€/año"
              savings="17% descuento"
              features={["✓ Todo STD +", "✓ SMS / WhatsApp", "✓ Calendario de citas", "✓ Auditoría interna", "✓ Soporte prioritario"]}
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
            <b style={{ color: "#f5b301" }}>ℹ️ Sobre el Install ID:</b> es un código único que identifica tu instalación.
            Si <b>aún no tienes la app</b>, deja este campo vacío — cuando aprobemos tu solicitud te enviaremos la app para que lo genere.
            Si <b>ya tienes la app instalada</b>, ábrela, ve al modal de activación y copia el código{" "}
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
            <b style={{ color: "#7ee3aa", fontSize: 13 }}>💰 Forma de pago: Transferencia bancaria</b>
            <div style={{ marginTop: 6 }}>
              Una vez recibamos tu solicitud, te enviaremos un <b>email con la factura proforma</b> y los datos bancarios para hacer la transferencia. Una vez confirmado el pago, recibirás la clave de activación.
            </div>
            <div style={{ marginTop: 6, fontSize: 11, color: "#94a3b8", fontStyle: "italic" }}>
              Sin compromiso: solo pagas si aceptas la oferta que te hagamos.
            </div>
          </div>

          <div style={{ display: "grid", gap: 14 }}>
            <div style={{ background: "#0f172a", border: "1px dashed #334155", borderRadius: 8, padding: 12 }}>
              {!showInstallId ? (
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "#94a3b8" }}>
                    <span>¿Ya tienes la app instalada en tu ordenador?</span>
                    <span
                      title="Si ya has instalado MediCar Plus en tu ordenador y quieres mejorar tu plan o renovarlo, esta sección es para reconocerte automáticamente. Abre la app → verás un código CD-XXXX-XXXX-XXXX-XXXX en el modal de activación. Pégalo aquí y sabremos exactamente qué ordenador es. Si aún no tienes la app instalada, déjalo cerrado y descárgala después."
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        justifyContent: "center",
                        width: 18,
                        height: 18,
                        borderRadius: "50%",
                        background: "#f5b30122",
                        border: "1px solid #f5b301",
                        color: "#f5b301",
                        fontSize: 11,
                        fontWeight: 800,
                        cursor: "help",
                        userSelect: "none",
                      }}
                      data-testid="install-id-help"
                    >
                      ?
                    </span>
                  </div>
                  <button
                    type="button"
                    data-testid="toggle-install-id"
                    onClick={() => setShowInstallId(true)}
                    style={{ background: "transparent", border: "1px solid #f5b301", color: "#f5b301", padding: "6px 12px", borderRadius: 6, fontSize: 11, fontWeight: 700, cursor: "pointer", fontFamily: "inherit", letterSpacing: .5 }}
                  >
                    SÍ, INTRODUCIR INSTALL ID
                  </button>
                </div>
              ) : (
                <div>
                  <label style={labelStyle}>INSTALL ID <span style={{ color: "#64748b", fontWeight: 400 }}>(código que aparece en la app)</span></label>
                  <input
                    data-testid="req-install-id"
                    placeholder="CD-XXXX-XXXX-XXXX-XXXX"
                    value={form.install_id}
                    onChange={(e) => {
                      const v = e.target.value.toUpperCase();
                      setForm({ ...form, install_id: v });
                      // Auto-lookup en cuanto el patrón sea válido
                      if (INSTALL_ID_PATTERN.test(v)) tryLookupInstallId(v);
                      else { setLookupStatus(null); setRecognizedInfo(null); }
                    }}
                    onBlur={(e) => tryLookupInstallId(e.target.value)}
                    style={inputStyle}
                  />
                  {lookupStatus === "searching" && (
                    <div style={{ marginTop: 8, fontSize: 11, color: "#94a3b8" }}>🔎 Buscando tus datos…</div>
                  )}
                  {lookupStatus === "found" && recognizedInfo && (
                    <div data-testid="lookup-found-banner" style={{ marginTop: 10, padding: "10px 12px", background: "#052e1a", border: "1px solid #22c55e", borderRadius: 8, fontSize: 12, color: "#bbf7d0", lineHeight: 1.5 }}>
                      <div style={{ fontWeight: 700, color: "#22c55e", marginBottom: 4 }}>
                        ✓ Te hemos reconocido
                      </div>
                      <div>
                        <b style={{ color: "#fde68a" }}>{recognizedInfo.company_name || "(sin nombre)"}</b>
                        {recognizedInfo.current_plan && (
                          <> · Plan actual: <b style={{ color: "#fde68a" }}>{recognizedInfo.current_plan}</b></>
                        )}
                      </div>
                      <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 4 }}>
                        Hemos rellenado tus datos automáticamente. Revísalos y modifica lo que necesites.
                      </div>
                    </div>
                  )}
                  {lookupStatus === "notfound" && (
                    <div data-testid="lookup-notfound-banner" style={{ marginTop: 10, padding: "8px 12px", background: "#1e1b0a", border: "1px solid #f59e0b", borderRadius: 8, fontSize: 11, color: "#fde68a" }}>
                      ℹ️ Este Install ID no está en nuestro sistema todavía. Rellena tus datos abajo como cliente nuevo.
                    </div>
                  )}
                  <button
                    type="button"
                    onClick={() => { setShowInstallId(false); setForm({ ...form, install_id: "" }); setLookupStatus(null); setRecognizedInfo(null); }}
                    style={{ marginTop: 8, background: "transparent", border: "none", color: "#94a3b8", fontSize: 11, cursor: "pointer", textDecoration: "underline", padding: 0 }}
                  >
                    ↩ Aún no tengo la app instalada
                  </button>
                </div>
              )}
            </div>
            <div>
              <label style={labelStyle}>NOMBRE DE LA EMPRESA *</label>
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
                <label style={labelStyle}>PERSONA DE CONTACTO</label>
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
                <label style={labelStyle}>TELÉFONO</label>
                <input
                  data-testid="req-phone"
                  value={form.phone}
                  onChange={(e) => setForm({ ...form, phone: e.target.value })}
                  style={inputStyle}
                />
              </div>
            </div>
            <div>
              <label style={labelStyle}>PLAN SELECCIONADO</label>
              <div style={{ padding: "10px 14px", background: "#0f172a", border: "1px solid #334155", borderRadius: 8, color: "#f5b301", fontFamily: "Georgia,serif", fontSize: 13 }}>
                {form.plan_requested === "TRIAL" && "🆓 TRIAL — Prueba gratuita 60 días"}
                {form.plan_requested === "STD_MES" && "📦 STD Mensual — 29,90€/mes"}
                {form.plan_requested === "STD_ANY" && "📦 STD Anual — 299,90€/año (ahorras 16%)"}
                {form.plan_requested === "PREMIUM_MES" && "⭐ PREMIUM Mensual — 39,90€/mes"}
                {form.plan_requested === "PREMIUM_ANY" && "⭐ PREMIUM Anual — 399,90€/año (ahorras 17%)"}
                <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 4, fontStyle: "italic" }}>
                  Selecciona otro plan clicando las tarjetas de arriba.
                </div>
              </div>
            </div>
            <div>
              <label style={labelStyle}>NOTAS / COMENTARIOS</label>
              <textarea
                data-testid="req-notes"
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
                rows={3}
                placeholder="Cuéntanos cualquier cosa que nos ayude a preparar tu licencia…"
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
              He leído y acepto la{" "}
              <a
                href="/privacy"
                target="_blank"
                rel="noreferrer"
                style={{ color: "#f5b301", textDecoration: "underline" }}
              >
                política de privacidad
              </a>
              . Mis datos se tratarán para gestionar mi solicitud de licencia.
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
            {busy ? "Enviando…" : "✉ Enviar solicitud"}
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
            Al enviar, aceptas recibir tu clave de licencia en la dirección de correo
            indicada. MediCar Plus se reserva el derecho de aprobar o denegar
            solicitudes.
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
          {hasBillingToggle && isYearly ? "/año" : period}
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
