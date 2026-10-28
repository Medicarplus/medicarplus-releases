import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

// Paleta MediCar Plus (coincideix amb v2.html): navy fons, gold accent, verd metge
const C = {
  bg: "#0a0f1a",
  bgAlt: "#0f172a",
  bgCard: "#131c2e",
  gold: "#f5b301",
  goldSoft: "#fde68a",
  text: "#e8ecf2",
  textDim: "#94a3b8",
  border: "#1e293b",
  green: "#22c55e",
  greenSoft: "#7ee3aa",
};

const Feature = ({ icon, title, children, mockup, onOpen }) => (
  <div
    style={{
      background: C.bgCard,
      border: `1px solid ${C.border}`,
      borderRadius: 14,
      padding: "22px 20px",
      transition: "transform .2s, border-color .2s, box-shadow .2s",
      cursor: mockup ? "pointer" : "default",
      position: "relative",
    }}
    onMouseEnter={(e) => {
      e.currentTarget.style.transform = "translateY(-4px)";
      e.currentTarget.style.borderColor = C.gold;
      if (mockup) e.currentTarget.style.boxShadow = `0 8px 24px rgba(245,179,1,.15)`;
    }}
    onMouseLeave={(e) => {
      e.currentTarget.style.transform = "translateY(0)";
      e.currentTarget.style.borderColor = C.border;
      e.currentTarget.style.boxShadow = "none";
    }}
    onClick={() => mockup && onOpen && onOpen({ icon, title, mockup, children })}
    data-testid={`feature-card-${title.toLowerCase().replace(/\s/g, "-")}`}
  >
    <div style={{ fontSize: 32, marginBottom: 10 }}>{icon}</div>
    <h3 style={{ margin: "0 0 8px", color: C.gold, fontFamily: "Georgia, serif", fontSize: 18 }}>
      {title}
    </h3>
    <p style={{ margin: 0, color: C.textDim, fontSize: 14, lineHeight: 1.55 }}>{children}</p>
    {mockup && (
      <div style={{ marginTop: 12, fontSize: 11, color: C.gold, fontWeight: 600, letterSpacing: ".5px" }}>
        👆 CLICA PARA VER EJEMPLO
      </div>
    )}
  </div>
);

// Modal lightbox para las capturas de ejemplo · click fuera o dentro cierra
const FeatureModal = ({ feature, onClose }) => {
  useEffect(() => {
    if (!feature) return;
    const esc = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", esc);
    document.body.style.overflow = "hidden";
    return () => { document.removeEventListener("keydown", esc); document.body.style.overflow = ""; };
  }, [feature, onClose]);
  if (!feature) return null;
  return (
    <div
      onClick={onClose}
      data-testid="feature-modal-backdrop"
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,.85)", backdropFilter: "blur(8px)",
        zIndex: 100000, display: "flex", alignItems: "center", justifyContent: "center", padding: "24px",
        animation: "fadeIn .2s ease",
      }}
    >
      <div
        style={{
          background: C.bgCard, border: `2px solid ${C.gold}`, borderRadius: 16,
          maxWidth: 900, width: "100%", maxHeight: "92vh", overflow: "auto",
          boxShadow: "0 20px 60px rgba(0,0,0,.6)", cursor: "pointer",
          animation: "slideUp .3s ease",
        }}
        onClick={onClose}
      >
        <div style={{ padding: "20px 24px 12px", borderBottom: `1px solid ${C.border}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <div style={{ fontSize: 32, marginBottom: 4 }}>{feature.icon}</div>
            <h2 style={{ margin: 0, color: C.gold, fontFamily: "Georgia, serif", fontSize: 22 }}>{feature.title}</h2>
          </div>
          <button
            aria-label="Cerrar"
            data-testid="feature-modal-close"
            style={{ background: "transparent", border: `1px solid ${C.border}`, color: C.text, width: 36, height: 36, borderRadius: 8, cursor: "pointer", fontSize: 18 }}
          >✕</button>
        </div>
        <div style={{ padding: "16px 24px", color: C.textDim, fontSize: 14, lineHeight: 1.6 }}>{feature.children}</div>
        <div style={{ padding: "0 24px 24px" }} dangerouslySetInnerHTML={{ __html: feature.mockup }} />
        <div style={{ textAlign: "center", padding: "8px 24px 20px", color: C.textDim, fontSize: 11, fontStyle: "italic" }}>Clica en cualquier punto para cerrar · o pulsa Esc</div>
      </div>
    </div>
  );
};

const PriceCard = ({ plan, monthlyPrice, annualPrice, period, features, highlighted, ctaHref, packageId, apiBase }) => {
  const price = period === "annual" ? annualPrice : monthlyPrice;
  const suffix = period === "annual" ? "/año" : "/mes";
  const savings = period === "annual"
    ? (monthlyPrice * 12 - annualPrice).toFixed(2)
    : null;
  const isTrial = plan === "Trial";
  const [loading, setLoading] = useState(false);
  const [emailModalOpen, setEmailModalOpen] = useState(false);
  const [emailInput, setEmailInput] = useState("");
  const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailInput.trim());

  const openCheckoutModal = () => {
    if (isTrial || !packageId) return;
    setEmailInput("");
    setEmailModalOpen(true);
  };

  const handleStripeCheckout = async () => {
    if (!emailValid) return;
    setLoading(true);
    try {
      const res = await fetch(`${apiBase}/api/payments/create-subscription`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          package_id: packageId,
          origin_url: window.location.origin,
          customer_email: emailInput.trim(),
        }),
      });
      const data = await res.json();
      if (data.url) {
        window.location.href = data.url;
      } else {
        const detail = data.detail ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)) : "";
        alert(`Error creando la sesión de pago${detail ? `:\n\n${detail}` : ""}\n\nSi persiste, contacta con info@medicarplus.es`);
        setLoading(false);
        setEmailModalOpen(false);
      }
    } catch (e) {
      alert("Error de conexión. Intenta de nuevo.");
      setLoading(false);
      setEmailModalOpen(false);
    }
  };
  return (
    <div
      style={{
        background: highlighted ? `linear-gradient(180deg, ${C.gold} 0%, #d97706 100%)` : C.bgCard,
        border: `2px solid ${highlighted ? C.gold : C.border}`,
        borderRadius: 18,
        padding: "28px 24px",
        position: "relative",
        color: highlighted ? "#0f172a" : C.text,
        boxShadow: highlighted ? "0 20px 50px rgba(245,179,1,.25)" : "none",
        transform: highlighted ? "scale(1.03)" : "none",
      }}
      data-testid={`price-card-${plan.toLowerCase()}`}
    >
      {highlighted && (
        <div
          style={{
            position: "absolute",
            top: -14,
            left: "50%",
            transform: "translateX(-50%)",
            background: "#0f172a",
            color: C.gold,
            padding: "4px 14px",
            borderRadius: 100,
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: 1.5,
            textTransform: "uppercase",
            border: `1px solid ${C.gold}`,
          }}
        >
          Más popular
        </div>
      )}
      <h3
        style={{
          margin: 0,
          fontFamily: "Georgia, serif",
          fontSize: 22,
          color: highlighted ? "#0f172a" : C.gold,
        }}
      >
        {plan}
      </h3>
      <div style={{ margin: "18px 0 6px" }}>
        <span style={{ fontSize: 46, fontWeight: 700, fontFamily: "Georgia, serif" }}>
          {price.toFixed(2)}
        </span>
        <span style={{ fontSize: 20, fontWeight: 600 }}> €</span>
        <span style={{ fontSize: 14, opacity: 0.75, marginLeft: 4 }}>{suffix}</span>
      </div>
      {savings && (
        <div
          style={{
            fontSize: 12,
            fontWeight: 700,
            color: highlighted ? "#0f172a" : C.greenSoft,
            marginBottom: 8,
          }}
        >
          Ahorra {savings} € · Equivale a 2 meses gratis
        </div>
      )}
      <ul
        style={{
          listStyle: "none",
          padding: 0,
          margin: "20px 0 24px",
          fontSize: 14,
          lineHeight: 1.9,
        }}
      >
        {features.map((f, i) => (
          <li key={i} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
            <span
              style={{
                color: highlighted ? "#166534" : C.greenSoft,
                fontWeight: 700,
                flexShrink: 0,
              }}
            >
              ✓
            </span>
            <span>{f}</span>
          </li>
        ))}
      </ul>
      {isTrial ? (
        <a
          href={ctaHref}
          data-testid={`price-cta-${plan.toLowerCase()}`}
          style={{
            display: "block",
            textAlign: "center",
            background: highlighted ? "#0f172a" : C.gold,
            color: highlighted ? C.gold : "#0f172a",
            padding: "13px 18px",
            borderRadius: 10,
            textDecoration: "none",
            fontWeight: 700,
            fontSize: 14,
            letterSpacing: 0.5,
          }}
        >
          COMENZAR PRUEBA GRATIS
        </a>
      ) : (
        <>
          <button
            onClick={openCheckoutModal}
            disabled={loading}
            data-testid={`price-cta-stripe-${plan.toLowerCase()}`}
            style={{
              display: "block",
              width: "100%",
              textAlign: "center",
              background: highlighted ? "#0f172a" : C.gold,
              color: highlighted ? C.gold : "#0f172a",
              padding: "13px 18px",
              borderRadius: 10,
              border: "none",
              cursor: loading ? "wait" : "pointer",
              fontWeight: 700,
              fontSize: 14,
              letterSpacing: 0.5,
              opacity: loading ? 0.6 : 1,
              fontFamily: "'Segoe UI', system-ui, sans-serif",
            }}
          >
            {loading ? "⏳ Redirigiendo..." : "💳 PAGAR CON TARJETA"}
          </button>
          <a
            href={ctaHref}
            data-testid={`price-cta-transfer-${plan.toLowerCase()}`}
            style={{
              display: "block",
              marginTop: 10,
              textAlign: "center",
              background: "transparent",
              color: highlighted ? "#0f172a" : C.textDim,
              padding: "10px 18px",
              borderRadius: 10,
              textDecoration: "none",
              fontWeight: 600,
              fontSize: 12,
              border: `1px solid ${highlighted ? "#0f172a30" : C.border}`,
            }}
          >
            🏦 O paga por transferencia bancaria
          </a>
        </>
      )}

      {/* Modal de email para checkout Stripe */}
      {emailModalOpen && (
        <div
          onClick={() => !loading && setEmailModalOpen(false)}
          data-testid="checkout-email-modal"
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(3,7,18,.85)",
            backdropFilter: "blur(6px)",
            zIndex: 9999,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: 20,
            color: "#e2e8f0",
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: "#0b1121",
              border: `2px solid ${C.gold}`,
              borderRadius: 16,
              maxWidth: 460,
              width: "100%",
              padding: 28,
              boxShadow: "0 30px 80px rgba(0,0,0,.6)",
              fontFamily: "'Segoe UI', system-ui, sans-serif",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
              <div>
                <div style={{ fontSize: 11, color: C.gold, letterSpacing: 1.5, fontWeight: 700, marginBottom: 4 }}>
                  PASO 1 DE 2
                </div>
                <h3 style={{ margin: 0, fontFamily: "Georgia,serif", fontSize: 22, color: "#fff" }}>
                  Tu email de facturación
                </h3>
              </div>
              {!loading && (
                <button
                  onClick={() => setEmailModalOpen(false)}
                  aria-label="Cerrar"
                  style={{ background: "transparent", border: "none", color: "#94a3b8", fontSize: 24, cursor: "pointer", lineHeight: 1, padding: 0 }}
                >
                  ×
                </button>
              )}
            </div>

            <div style={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 10, padding: "12px 14px", marginBottom: 18 }}>
              <div style={{ fontSize: 10, color: "#94a3b8", letterSpacing: 1, fontWeight: 700 }}>PLAN SELECCIONADO</div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 4 }}>
                <div style={{ color: C.gold, fontWeight: 700, fontFamily: "Georgia,serif", fontSize: 16 }}>{plan} {period === "annual" ? "Anual" : "Mensual"}</div>
                <div style={{ color: "#fff", fontWeight: 700, fontSize: 16 }}>
                  {price.toFixed(2).replace(".", ",")} €{suffix}
                </div>
              </div>
            </div>

            <label style={{ display: "block", fontSize: 12, color: "#94a3b8", marginBottom: 6, fontWeight: 700, letterSpacing: .5 }}>
              📧 Tu email
            </label>
            <input
              type="email"
              value={emailInput}
              onChange={(e) => setEmailInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && emailValid && !loading) handleStripeCheckout(); }}
              placeholder="tu@centromedico.es"
              autoFocus
              data-testid="checkout-email-input"
              style={{
                width: "100%",
                padding: "12px 14px",
                background: "#0f172a",
                border: `2px solid ${emailInput.length === 0 ? "#334155" : emailValid ? "#22c55e" : "#dc2626"}`,
                borderRadius: 10,
                color: "#e2e8f0",
                fontSize: 15,
                fontFamily: "inherit",
                outline: "none",
                boxSizing: "border-box",
              }}
            />
            <div style={{ fontSize: 11, color: "#64748b", marginTop: 6, lineHeight: 1.5 }}>
              Recibirás la factura y podrás gestionar tu suscripción desde este email.
            </div>

            <button
              onClick={handleStripeCheckout}
              disabled={!emailValid || loading}
              data-testid="checkout-email-submit"
              style={{
                width: "100%",
                marginTop: 20,
                padding: "14px 18px",
                background: emailValid && !loading ? C.gold : "#334155",
                color: emailValid && !loading ? "#0f172a" : "#64748b",
                border: "none",
                borderRadius: 10,
                fontWeight: 700,
                fontSize: 15,
                cursor: emailValid && !loading ? "pointer" : "not-allowed",
                letterSpacing: .5,
                fontFamily: "inherit",
              }}
            >
              {loading ? "⏳ Redirigiendo al pago seguro…" : "💳 Continuar al pago seguro"}
            </button>

            <div style={{ display: "flex", justifyContent: "center", gap: 16, marginTop: 14, fontSize: 11, color: "#64748b" }}>
              <span>🔒 Pago seguro con Stripe</span>
              <span>·</span>
              <span>Cancela cuando quieras</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default function LandingPage() {
  const [period, setPeriod] = useState("monthly"); // monthly | annual · default mensual (Feb 2026)
  const [openFeature, setOpenFeature] = useState(null);
  const apiBase = process.env.REACT_APP_BACKEND_URL;

  // 🎨 Mockups SVG estilizados para cada función · realistas pero simulados
  const MOCKUP_DGT = `<div style="background:#0a0f1a;border:1px solid #1e293b;border-radius:8px;padding:14px;font-family:'Segoe UI',system-ui;color:#e2e8f0;font-size:12px">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
      <div style="color:#3ddc97;font-weight:700;font-size:13px;letter-spacing:.5px">📥 ENTRADAS DEL DÍA · 25/08/2026</div>
      <div style="display:flex;gap:6px"><button style="background:#0e9f6e;color:#0b1121;border:none;padding:4px 10px;border-radius:6px;font-size:11px;font-weight:700">📤 Importar CSV / Excel</button><button style="background:#7f1d1d;color:#fff;border:none;padding:4px 10px;border-radius:6px;font-size:11px">🗑 Vaciar día</button></div>
    </div>
    <div style="display:flex;gap:6px;margin-bottom:8px;flex-wrap:wrap;font-size:10px">
      <span style="background:#065f4633;color:#3ddc97;padding:3px 8px;border-radius:3px;font-weight:700">RENOVACIÓN · CONDUCIR (42)</span>
      <span style="background:#0e7490aa;color:#67e8f9;padding:3px 8px;border-radius:3px;font-weight:700">EXPEDICIÓN · CONDUCIR (22)</span>
      <span style="background:#1e293b;color:#94a3b8;padding:3px 8px;border-radius:3px">OBTENCIÓN · MARINA (3)</span>
      <span style="background:#1e293b;color:#94a3b8;padding:3px 8px;border-radius:3px">OBTENCIÓN · ARMAS (1)</span>
    </div>
    <table style="width:100%;border-collapse:collapse">
      <thead><tr style="background:#0f172a;color:#94a3b8;font-size:10px"><th style="padding:5px 8px;text-align:left">#</th><th style="padding:5px 8px;text-align:left">TIPO</th><th style="padding:5px 8px;text-align:left">GRUPO</th><th style="padding:5px 8px;text-align:left">NOMBRE / CONCEPTO</th><th style="padding:5px 8px;text-align:right">IMPORTE</th><th style="padding:5px 8px;text-align:center">FP</th></tr></thead>
      <tbody style="font-size:11px">
        <tr style="border-bottom:1px solid #1e293b"><td style="padding:5px 8px;color:#64748b">1</td><td style="padding:5px 8px"><span style="background:#1e293b;color:#94a3b8;padding:2px 8px;border-radius:12px">Obtención</span></td><td style="padding:5px 8px">Marina</td><td style="padding:5px 8px;font-weight:600">MARIO SILVA VEGA</td><td style="padding:5px 8px;text-align:right;color:#f5b301;font-family:Consolas">66,50 €</td><td style="padding:5px 8px;text-align:center"><span style="background:#065f4633;color:#3ddc97;padding:2px 8px;border-radius:12px;font-size:10px">Efectivo</span></td></tr>
        <tr style="border-bottom:1px solid #1e293b"><td style="padding:5px 8px;color:#64748b">2</td><td style="padding:5px 8px"><span style="background:#1e293b;color:#94a3b8;padding:2px 8px;border-radius:12px">Obtención</span></td><td style="padding:5px 8px">Marina</td><td style="padding:5px 8px;font-weight:600">LUCÍA HERRERA VIDAL</td><td style="padding:5px 8px;text-align:right;color:#f5b301;font-family:Consolas">66,50 €</td><td style="padding:5px 8px;text-align:center"><span style="background:#065f4633;color:#3ddc97;padding:2px 8px;border-radius:12px;font-size:10px">Efectivo</span></td></tr>
        <tr style="border-bottom:1px solid #1e293b"><td style="padding:5px 8px;color:#64748b">3</td><td style="padding:5px 8px"><span style="background:#1e293b;color:#94a3b8;padding:2px 8px;border-radius:12px">Obtención</span></td><td style="padding:5px 8px">Armas</td><td style="padding:5px 8px;font-weight:600">DAVID RUIZ CARBÓ</td><td style="padding:5px 8px;text-align:right;color:#f5b301;font-family:Consolas">66,50 €</td><td style="padding:5px 8px;text-align:center"><span style="background:#065f4633;color:#3ddc97;padding:2px 8px;border-radius:12px;font-size:10px">Efectivo</span></td></tr>
        <tr style="border-bottom:1px solid #1e293b"><td style="padding:5px 8px;color:#64748b">4</td><td style="padding:5px 8px"><span style="background:#065f46;color:#6ee7b7;padding:2px 8px;border-radius:12px">Renovación</span></td><td style="padding:5px 8px">Conducir</td><td style="padding:5px 8px;font-weight:600">JULIA CANO ORTEGA</td><td style="padding:5px 8px;text-align:right;color:#f5b301;font-family:Consolas">66,50 €</td><td style="padding:5px 8px;text-align:center"><span style="background:#065f4633;color:#3ddc97;padding:2px 8px;border-radius:12px;font-size:10px">Efectivo</span></td></tr>
        <tr style="border-bottom:1px solid #1e293b"><td style="padding:5px 8px;color:#64748b">5</td><td style="padding:5px 8px"><span style="background:#0e7490;color:#a5f3fc;padding:2px 8px;border-radius:12px">Expedición</span></td><td style="padding:5px 8px">Conducir</td><td style="padding:5px 8px;font-weight:600">NURIA BLANC PIÑOL</td><td style="padding:5px 8px;text-align:right;color:#f5b301;font-family:Consolas">51,00 €</td><td style="padding:5px 8px;text-align:center"><span style="background:#065f4633;color:#3ddc97;padding:2px 8px;border-radius:12px;font-size:10px">Efectivo</span></td></tr>
        <tr><td style="padding:5px 8px;color:#64748b">6</td><td style="padding:5px 8px"><span style="background:#065f46;color:#6ee7b7;padding:2px 8px;border-radius:12px">Renovación</span></td><td style="padding:5px 8px">Conducir</td><td style="padding:5px 8px;font-weight:600">MARC ESTRADA ROURA</td><td style="padding:5px 8px;text-align:right;color:#f5b301;font-family:Consolas">66,50 €</td><td style="padding:5px 8px;text-align:center"><span style="background:#065f4633;color:#3ddc97;padding:2px 8px;border-radius:12px;font-size:10px">Efectivo</span></td></tr>
      </tbody>
    </table>
    <div style="margin-top:8px;padding:8px 10px;background:#065f4622;border:1px solid #065f46;border-radius:6px;font-size:11px;color:#6ee7b7">✅ 68 entradas procesadas · Total 4.788,91 € · Tarjeta 3.281,27 € · Efectivo 1.507,64 € · Sin duplicados</div>
  </div>`;
  const MOCKUP_CERT = `<div style="background:#0a0f1a;border:1px solid #1e293b;border-radius:8px;padding:14px;font-family:'Segoe UI',system-ui;color:#e2e8f0;font-size:12px"><div style="color:#f5b301;font-weight:700;font-size:13px;margin-bottom:8px">📋 Certificados médicos · Agosto 2026</div><table style="width:100%;border-collapse:collapse;font-size:11px"><thead><tr style="background:#0f172a;color:#94a3b8;font-size:10px"><th style="padding:6px 8px;text-align:left">FECHA</th><th style="padding:6px 8px;text-align:left">TIPO</th><th style="padding:6px 8px;text-align:left">CLIENTE</th><th style="padding:6px 8px;text-align:right">IMPORTE</th></tr></thead><tbody>
    <tr style="border-bottom:1px solid #1e293b"><td style="padding:5px 8px;color:#94a3b8">24/08/2026</td><td style="padding:5px 8px"><span style="background:#0e7490;color:#a5f3fc;padding:2px 8px;border-radius:12px">Permiso</span></td><td style="padding:5px 8px;font-weight:600">LAURA VIVES PONS</td><td style="padding:5px 8px;text-align:right;color:#f5b301;font-family:Consolas">66,50 €</td></tr>
    <tr style="border-bottom:1px solid #1e293b"><td style="padding:5px 8px;color:#94a3b8">25/08/2026</td><td style="padding:5px 8px"><span style="background:#065f46;color:#6ee7b7;padding:2px 8px;border-radius:12px">Armas</span></td><td style="padding:5px 8px;font-weight:600">ROBERTO DÍAZ SOLÀ</td><td style="padding:5px 8px;text-align:right;color:#f5b301;font-family:Consolas">78,00 €</td></tr>
    <tr style="border-bottom:1px solid #1e293b"><td style="padding:5px 8px;color:#94a3b8">25/08/2026</td><td style="padding:5px 8px"><span style="background:#7c2d12;color:#fdba74;padding:2px 8px;border-radius:12px">Embarcaciones</span></td><td style="padding:5px 8px;font-weight:600">MIREIA FONT CASAS</td><td style="padding:5px 8px;text-align:right;color:#f5b301;font-family:Consolas">92,00 €</td></tr>
    <tr><td style="padding:5px 8px;color:#94a3b8">26/08/2026</td><td style="padding:5px 8px"><span style="background:#4a044e;color:#f0abfc;padding:2px 8px;border-radius:12px">Bomberos</span></td><td style="padding:5px 8px;font-weight:600">SERGIO PLA COMES</td><td style="padding:5px 8px;text-align:right;color:#f5b301;font-family:Consolas">54,00 €</td></tr>
  </tbody></table>
  <div style="margin-top:8px;padding:8px 10px;background:#065f4622;border:1px solid #065f46;border-radius:6px;font-size:11px;color:#6ee7b7">📊 Este mes: <b>127 permisos</b> · 34 armas · 18 embarcaciones · 7 bomberos = 186 certificados · <b>9.734,50 €</b></div></div>`;
  const MOCKUP_IRPF = `<div style="background:#0a0f1a;border:1px solid #1e293b;border-radius:8px;padding:14px;font-family:'Segoe UI',system-ui;color:#e2e8f0;font-size:12px"><div style="color:#f5b301;font-weight:700;font-size:13px;margin-bottom:10px">📊 IRPF Trimestral · T2 · 2026</div><table style="width:100%;border-collapse:collapse;font-size:11px"><thead><tr style="background:#0f172a;color:#94a3b8;font-size:10px"><th style="padding:6px 8px;text-align:left">CONCEPTO</th><th style="padding:6px 8px;text-align:right">ABRIL</th><th style="padding:6px 8px;text-align:right">MAYO</th><th style="padding:6px 8px;text-align:right">JUNIO</th><th style="padding:6px 8px;text-align:right">TOTAL T2</th></tr></thead><tbody>
    <tr style="border-bottom:1px solid #1e293b"><td style="padding:5px 8px">Facturación bruta</td><td style="padding:5px 8px;text-align:right;font-family:Consolas;color:#22d3ee">4.892,00 €</td><td style="padding:5px 8px;text-align:right;font-family:Consolas;color:#22d3ee">5.104,50 €</td><td style="padding:5px 8px;text-align:right;font-family:Consolas;color:#22d3ee">4.788,91 €</td><td style="padding:5px 8px;text-align:right;font-family:Consolas;color:#22d3ee;font-weight:700">14.785,41 €</td></tr>
    <tr style="border-bottom:1px solid #1e293b"><td style="padding:5px 8px">Retención IRPF (15%)</td><td style="padding:5px 8px;text-align:right;font-family:Consolas;color:#fbbf24">−733,80 €</td><td style="padding:5px 8px;text-align:right;font-family:Consolas;color:#fbbf24">−765,67 €</td><td style="padding:5px 8px;text-align:right;font-family:Consolas;color:#fbbf24">−718,34 €</td><td style="padding:5px 8px;text-align:right;font-family:Consolas;color:#fbbf24;font-weight:700">−2.217,81 €</td></tr>
    <tr style="border-bottom:1px solid #1e293b"><td style="padding:5px 8px">Gastos deducibles</td><td style="padding:5px 8px;text-align:right;font-family:Consolas;color:#f472b6">−1.240,00 €</td><td style="padding:5px 8px;text-align:right;font-family:Consolas;color:#f472b6">−980,50 €</td><td style="padding:5px 8px;text-align:right;font-family:Consolas;color:#f472b6">−1.150,00 €</td><td style="padding:5px 8px;text-align:right;font-family:Consolas;color:#f472b6;font-weight:700">−3.370,50 €</td></tr>
    <tr style="background:#065f4622"><td style="padding:8px;color:#22c55e;font-weight:700">✓ NETO A DECLARAR</td><td></td><td></td><td></td><td style="padding:8px;text-align:right;color:#22c55e;font-family:Consolas;font-weight:700;font-size:13px">9.197,10 €</td></tr>
  </tbody></table>
  <div style="display:flex;gap:6px;margin-top:8px"><button style="background:#3ddc97;color:#0b1121;border:none;padding:5px 12px;border-radius:6px;font-weight:700;font-size:11px">📥 Descargar PDF</button><button style="background:#22d3ee;color:#0b1121;border:none;padding:5px 12px;border-radius:6px;font-weight:700;font-size:11px">📊 Ver desglose diario</button></div></div>`;
  const MOCKUP_AUD = `<div style="background:#0a0f1a;border:1px solid #1e293b;border-radius:8px;padding:14px;font-family:'Segoe UI',system-ui;color:#e2e8f0;font-size:12px">
    <div style="color:#fb923c;font-weight:700;font-size:13px;margin-bottom:8px">🔍 Auditoría de tasas · Clientes repetidos en el rango</div>
    <div style="display:flex;gap:8px;margin-bottom:8px;font-size:10px;color:#94a3b8">DESDE 02/08/2026 · HASTA 26/08/2026 · <span style="color:#ef4444">● Mismo grupo</span> · <span style="color:#f59e0b">⚠ Error 0€</span></div>
    <div style="background:#0f172a;padding:6px 10px;border-radius:4px;font-size:11px;color:#94a3b8;margin-bottom:8px">Rango 02/08/2026 → 26/08/2026 · Mostrando <b style="color:#e2e8f0">3 de 4</b> repetidos · <span style="color:#ef4444">3 mismo grupo</span> · <span style="color:#f59e0b">0 errores</span></div>
    <div style="background:#7f1d1d22;border:1px solid #ef4444;border-radius:6px;padding:10px;margin-bottom:8px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px"><div><span style="color:#ef4444;font-size:14px">●</span> <b style="color:#e2e8f0;font-size:13px">JOSEP SALVANS MACIA</b> <span style="background:#1e293b;color:#94a3b8;padding:2px 6px;border-radius:3px;font-size:10px;margin-left:4px">🎫 2 fichas</span> <span style="background:#7c2d12;color:#fdba74;padding:2px 6px;border-radius:3px;font-size:10px">Conducir ×2</span></div><div style="font-size:10px;color:#94a3b8">Total imp: <b style="color:#f5b301">66,50 €</b></div></div>
      <table style="width:100%;font-size:11px;border-collapse:collapse"><tbody>
        <tr style="background:#0f172a"><td style="padding:4px 8px;color:#94a3b8">24/08/2026</td><td style="padding:4px 8px"><span style="background:#065f46;color:#6ee7b7;padding:2px 6px;border-radius:3px">Renovación</span></td><td style="padding:4px 8px;font-family:Consolas">66,50 €</td><td style="padding:4px 8px"><span style="color:#ef4444">● MISMO GRUPO</span></td></tr>
        <tr><td style="padding:4px 8px;color:#94a3b8">25/08/2026</td><td style="padding:4px 8px"><span style="background:#065f46;color:#6ee7b7;padding:2px 6px;border-radius:3px">Renovación</span></td><td style="padding:4px 8px;font-family:Consolas;color:#f59e0b">0,00 €</td><td style="padding:4px 8px"><span style="color:#f59e0b">⚠ TRÁMITE 0€</span></td></tr>
      </tbody></table>
    </div>
    <div style="background:#7f1d1d22;border:1px solid #ef4444;border-radius:6px;padding:10px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px"><div><span style="color:#ef4444;font-size:14px">●</span> <b style="color:#e2e8f0;font-size:13px">CLARA JOFRÉ MARQUÈS</b> <span style="background:#1e293b;color:#94a3b8;padding:2px 6px;border-radius:3px;font-size:10px;margin-left:4px">🎫 2 fichas</span> <span style="background:#7c2d12;color:#fdba74;padding:2px 6px;border-radius:3px;font-size:10px">Conducir ×2</span></div><div style="font-size:10px;color:#94a3b8">Total imp: <b style="color:#f5b301">51,00 €</b></div></div>
      <table style="width:100%;font-size:11px;border-collapse:collapse"><tbody>
        <tr style="background:#0f172a"><td style="padding:4px 8px;color:#94a3b8">24/08/2026</td><td style="padding:4px 8px"><span style="background:#0e7490;color:#a5f3fc;padding:2px 6px;border-radius:3px">Expedición</span></td><td style="padding:4px 8px;font-family:Consolas">51,00 €</td><td style="padding:4px 8px"><span style="color:#ef4444">● MISMO GRUPO</span></td></tr>
        <tr><td style="padding:4px 8px;color:#94a3b8">25/08/2026</td><td style="padding:4px 8px"><span style="background:#0e7490;color:#a5f3fc;padding:2px 6px;border-radius:3px">Expedición</span></td><td style="padding:4px 8px;font-family:Consolas;color:#f59e0b">0,00 €</td><td style="padding:4px 8px"><span style="color:#f59e0b">⚠ TRÁMITE 0€</span></td></tr>
      </tbody></table>
    </div>
    <div style="text-align:center;margin-top:10px"><button style="background:#7c3aed;color:#fff;border:none;padding:6px 14px;border-radius:6px;font-size:11px;font-weight:700">🤖 Preguntar a la IA sobre esto</button></div>
  </div>`;
  const MOCKUP_CAMBIO = `<div style="background:#0a0f1a;border:1px solid #1e293b;border-radius:8px;padding:14px;font-family:'Segoe UI',system-ui;color:#e2e8f0;font-size:12px">
    <div style="color:#f5b301;font-weight:700;font-size:13px;margin-bottom:10px">💰 Cambio · Reserva caja física · 26/08/2026</div>
    <table style="width:100%;border-collapse:collapse;font-size:11px"><thead><tr style="background:#0f172a;color:#94a3b8;font-size:10px"><th style="padding:6px 8px;text-align:left">DENOMINACIÓN</th><th style="padding:6px 8px;text-align:right">CANTIDAD</th><th style="padding:6px 8px;text-align:right">SUBTOTAL</th></tr></thead><tbody>
      <tr style="border-bottom:1px solid #1e293b"><td style="padding:5px 8px">🟪 Billete 500 €</td><td style="padding:5px 8px;text-align:right;color:#22d3ee">0</td><td style="padding:5px 8px;text-align:right;color:#f5b301;font-family:Consolas">0,00 €</td></tr>
      <tr style="border-bottom:1px solid #1e293b"><td style="padding:5px 8px">🟨 Billete 200 €</td><td style="padding:5px 8px;text-align:right;color:#22d3ee">1</td><td style="padding:5px 8px;text-align:right;color:#f5b301;font-family:Consolas">200,00 €</td></tr>
      <tr style="border-bottom:1px solid #1e293b"><td style="padding:5px 8px">🟩 Billete 100 €</td><td style="padding:5px 8px;text-align:right;color:#22d3ee">3</td><td style="padding:5px 8px;text-align:right;color:#f5b301;font-family:Consolas">300,00 €</td></tr>
      <tr style="border-bottom:1px solid #1e293b"><td style="padding:5px 8px">🟧 Billete 50 €</td><td style="padding:5px 8px;text-align:right;color:#22d3ee">6</td><td style="padding:5px 8px;text-align:right;color:#f5b301;font-family:Consolas">300,00 €</td></tr>
      <tr style="border-bottom:1px solid #1e293b"><td style="padding:5px 8px">🟦 Billete 20 €</td><td style="padding:5px 8px;text-align:right;color:#22d3ee">12</td><td style="padding:5px 8px;text-align:right;color:#f5b301;font-family:Consolas">240,00 €</td></tr>
      <tr style="border-bottom:1px solid #1e293b"><td style="padding:5px 8px">🟥 Billete 10 € · 5 €</td><td style="padding:5px 8px;text-align:right;color:#22d3ee">18</td><td style="padding:5px 8px;text-align:right;color:#f5b301;font-family:Consolas">130,00 €</td></tr>
      <tr><td style="padding:5px 8px">🪙 Monedas mixtas</td><td style="padding:5px 8px;text-align:right;color:#22d3ee">—</td><td style="padding:5px 8px;text-align:right;color:#f5b301;font-family:Consolas">47,30 €</td></tr>
      <tr style="background:#065f4622"><td style="padding:8px;color:#22c55e;font-weight:700">✓ TOTAL CAJA</td><td></td><td style="padding:8px;text-align:right;color:#22c55e;font-family:Consolas;font-weight:700;font-size:14px">1.217,30 €</td></tr>
    </tbody></table>
    <div style="margin-top:8px;padding:8px 10px;background:#0f172a;border-radius:6px;font-size:11px;color:#94a3b8">💡 Al cerrar caja, este importe se repercute automáticamente al saldo del día siguiente</div>
  </div>`;
  const MOCKUP_SEC = `<div style="background:#0a0f1a;border:1px solid #1e293b;border-radius:8px;padding:14px;font-family:'Segoe UI',system-ui;color:#e2e8f0;font-size:12px">
    <div style="color:#f5b301;font-weight:700;font-size:13px;margin-bottom:10px">🔒 Estado seguridad · Backup automático</div>
    <div style="background:#065f4622;border:1px solid #22c55e;border-radius:6px;padding:10px;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center"><div><div style="color:#6ee7b7;font-weight:700">✓ Último snapshot local</div><div style="font-size:11px;color:#94a3b8">Hace 8 min · 24.312 registros · 1,2 MB</div></div><span style="background:#22c55e;color:#0b1121;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700">AUTO 10 MIN</span></div>
    <div style="background:#065f4622;border:1px solid #22c55e;border-radius:6px;padding:10px;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center"><div><div style="color:#6ee7b7;font-weight:700">✓ Backup MongoDB Atlas</div><div style="font-size:11px;color:#94a3b8">Hace 2 h · Cifrado AES-256 · Región EU-West</div></div><span style="background:#22d3ee;color:#0b1121;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700">CLOUD</span></div>
    <div style="background:#065f4622;border:1px solid #22c55e;border-radius:6px;padding:10px;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center"><div><div style="color:#6ee7b7;font-weight:700">✓ Copia file:// disco</div><div style="font-size:11px;color:#94a3b8">C:\\MediCarPlus\\backups\\ · 47 snapshots · 128 MB</div></div><span style="background:#f5b301;color:#0b1121;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700">LOCAL</span></div>
    <div style="background:#0f172a;padding:10px;border-radius:6px;font-size:11px;color:#94a3b8"><b style="color:#e2e8f0">🛡️ Compliance:</b> ✓ RGPD ✓ LOPDGDD ✓ Cifrado extremo a extremo ✓ Sin transferencia a terceros ✓ HWID lock (licencia atada a tu PC)</div>
    <button style="margin-top:8px;background:#22c55e;color:#0b1121;border:none;padding:8px 16px;border-radius:6px;font-weight:700;font-size:12px">📦 Descargar backup completo ahora</button>
  </div>`;
  const MOCKUP_SMS = `<div style="background:#0a0f1a;border:1px solid #1e293b;border-radius:8px;padding:14px;font-family:'Segoe UI',system-ui;color:#e2e8f0;font-size:12px">
    <div style="color:#f5b301;font-weight:700;font-size:13px;margin-bottom:10px">📱 Campaña SMS · Recordatorio DGT · Septiembre 2026</div>
    <div style="background:#0f172a;padding:12px;border-radius:8px;margin-bottom:8px"><div style="display:flex;justify-content:space-between;margin-bottom:6px"><span style="font-size:11px;color:#94a3b8">DESTINATARIOS FILTRADOS AUTOMÁTICAMENTE</span><span style="background:#065f46;color:#6ee7b7;padding:2px 8px;border-radius:12px;font-size:10px;font-weight:700">CADUCA EN 45 DÍAS</span></div><div style="font-size:24px;color:#22d3ee;font-weight:700">98 clientes</div><div style="font-size:11px;color:#94a3b8">Permiso conducir · último cliente activo hace ≤ 5 años</div></div>
    <table style="width:100%;border-collapse:collapse;font-size:11px;margin-bottom:8px"><thead><tr style="background:#0f172a;color:#94a3b8;font-size:10px"><th style="padding:5px 8px;text-align:left">NOMBRE</th><th style="padding:5px 8px;text-align:center">TELÉFONO</th><th style="padding:5px 8px;text-align:center">CADUCA</th><th style="padding:5px 8px;text-align:center">ESTADO</th></tr></thead><tbody>
      <tr style="border-bottom:1px solid #1e293b"><td style="padding:4px 8px;font-weight:600">ELENA CASTRO ROURA</td><td style="padding:4px 8px;text-align:center;font-family:Consolas">6·· ··· 342</td><td style="padding:4px 8px;text-align:center;color:#f59e0b">15/10/2026</td><td style="padding:4px 8px;text-align:center"><span style="background:#22c55e;color:#0b1121;padding:2px 8px;border-radius:12px;font-size:10px;font-weight:700">✓ ENVIADO</span></td></tr>
      <tr style="border-bottom:1px solid #1e293b"><td style="padding:4px 8px;font-weight:600">DAVID PONS AMAT</td><td style="padding:4px 8px;text-align:center;font-family:Consolas">6·· ··· 891</td><td style="padding:4px 8px;text-align:center;color:#f59e0b">02/10/2026</td><td style="padding:4px 8px;text-align:center"><span style="background:#22c55e;color:#0b1121;padding:2px 8px;border-radius:12px;font-size:10px;font-weight:700">✓ ENVIADO</span></td></tr>
      <tr><td style="padding:4px 8px;font-weight:600">MONTSE JORDÀ CASTELLS</td><td style="padding:4px 8px;text-align:center;font-family:Consolas">6·· ··· 517</td><td style="padding:4px 8px;text-align:center;color:#f59e0b">08/10/2026</td><td style="padding:4px 8px;text-align:center"><span style="background:#f5b301;color:#0b1121;padding:2px 8px;border-radius:12px;font-size:10px;font-weight:700">EN COLA</span></td></tr>
    </tbody></table>
    <div style="background:#0f172a;padding:8px 12px;border-radius:6px;font-size:11px;color:#94a3b8;display:flex;justify-content:space-between"><div>💰 Coste total: <b style="color:#f5b301">98 × 0,065 € = 6,37 €</b></div><div>✅ Enviados: <b style="color:#22c55e">62/98</b></div></div>
  </div>`;
  const MOCKUP_PRINT = `<div style="background:#0a0f1a;border:1px solid #1e293b;border-radius:8px;padding:14px;font-family:'Segoe UI',system-ui;color:#e2e8f0;font-size:12px">
    <div style="color:#f5b301;font-weight:700;font-size:13px;margin-bottom:10px">🖨️ Cierre diario · 26/08/2026 · MediCar Vic</div>
    <table style="width:100%;border-collapse:collapse;font-size:11px;margin-bottom:8px"><thead><tr style="background:#0f172a;color:#94a3b8;font-size:10px"><th style="padding:6px 8px;text-align:left">MÉTODO PAGO</th><th style="padding:6px 8px;text-align:right">OPERACIONES</th><th style="padding:6px 8px;text-align:right">IMPORTE</th></tr></thead><tbody>
      <tr style="border-bottom:1px solid #1e293b"><td style="padding:5px 8px">💵 Efectivo</td><td style="padding:5px 8px;text-align:right;color:#22d3ee">23</td><td style="padding:5px 8px;text-align:right;color:#f5b301;font-family:Consolas">1.507,64 €</td></tr>
      <tr style="border-bottom:1px solid #1e293b"><td style="padding:5px 8px">💳 Tarjeta / Banco</td><td style="padding:5px 8px;text-align:right;color:#22d3ee">42</td><td style="padding:5px 8px;text-align:right;color:#f5b301;font-family:Consolas">3.281,27 €</td></tr>
      <tr style="border-bottom:1px solid #1e293b"><td style="padding:5px 8px">📱 Bizum</td><td style="padding:5px 8px;text-align:right;color:#22d3ee">3</td><td style="padding:5px 8px;text-align:right;color:#f5b301;font-family:Consolas">168,00 €</td></tr>
      <tr><td style="padding:5px 8px">📦 Otros</td><td style="padding:5px 8px;text-align:right;color:#22d3ee">0</td><td style="padding:5px 8px;text-align:right;color:#f5b301;font-family:Consolas">0,00 €</td></tr>
      <tr style="background:#065f4622"><td style="padding:8px;color:#22c55e;font-weight:700">✓ TOTAL DIA</td><td style="padding:8px;text-align:right;color:#22c55e;font-family:Consolas;font-weight:700">68</td><td style="padding:8px;text-align:right;color:#22c55e;font-family:Consolas;font-weight:700;font-size:14px">4.956,91 €</td></tr>
    </tbody></table>
    <div style="background:#0f172a;padding:10px;border-radius:6px;font-size:11px;color:#94a3b8"><div style="color:#e2e8f0;font-weight:700;margin-bottom:4px">Desglose por servicio</div>· Renovaciones DGT: <b style="color:#f5b301">42</b> · Expediciones: <b style="color:#f5b301">18</b> · Reconocimientos: <b style="color:#f5b301">8</b></div>
    <div style="display:flex;gap:6px;margin-top:8px"><button style="background:#3ddc97;color:#0b1121;border:none;padding:5px 12px;border-radius:6px;font-weight:700;font-size:11px">🖨️ Imprimir</button><button style="background:#22d3ee;color:#0b1121;border:none;padding:5px 12px;border-radius:6px;font-weight:700;font-size:11px">📥 PDF</button><button style="background:#f5b301;color:#0b1121;border:none;padding:5px 12px;border-radius:6px;font-weight:700;font-size:11px">📧 Enviar por email</button></div>
  </div>`;
  const MOCKUP_UPD = `<div style="background:#0a0f1a;border:1px solid #1e293b;border-radius:8px;padding:14px;font-family:'Segoe UI',system-ui;color:#e2e8f0;font-size:12px">
    <div style="color:#f5b301;font-weight:700;font-size:13px;margin-bottom:10px">🔄 Actualizaciones · MediCar Plus</div>
    <div style="background:#065f4622;border:1px solid #22c55e;border-radius:6px;padding:12px;margin-bottom:8px"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px"><div><div style="color:#6ee7b7;font-weight:700;font-size:14px">✓ Versión 2.14.3 instalada</div><div style="font-size:11px;color:#94a3b8">Hace 3 minutos · Actualización automática · Sin reiniciar</div></div><span style="background:#22c55e;color:#0b1121;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700">AL DÍA</span></div>
      <div style="background:#0f172a;padding:10px;border-radius:6px;font-size:11px"><div style="color:#22d3ee;font-weight:700;margin-bottom:6px;letter-spacing:.5px">📝 NOVEDADES DE ESTA VERSIÓN</div><ul style="margin:0;padding-left:18px;line-height:1.8;color:#e2e8f0"><li>⚡ Buscador global con sinónimos y navegación al día</li><li>📈 Gráfico de comparación 2 años en Autoescuelas</li><li>💼 Panel Honorarios por mes con impresión PDF</li><li>🧠 Autocompletar nombres de trabajadores en nóminas</li><li>🔍 Auditoría de tasas mejorada con IA</li></ul></div>
    </div>
    <table style="width:100%;font-size:11px;border-collapse:collapse"><thead><tr style="background:#0f172a;color:#94a3b8;font-size:10px"><th style="padding:5px 8px;text-align:left">VERSIÓN</th><th style="padding:5px 8px;text-align:center">FECHA</th><th style="padding:5px 8px;text-align:left">DESTACADO</th></tr></thead><tbody>
      <tr style="border-bottom:1px solid #1e293b"><td style="padding:4px 8px;font-family:Consolas;color:#f5b301">v2.14.3</td><td style="padding:4px 8px;text-align:center;color:#94a3b8">Hoy</td><td style="padding:4px 8px;color:#e2e8f0">Gráficos comparativos + IA</td></tr>
      <tr style="border-bottom:1px solid #1e293b"><td style="padding:4px 8px;font-family:Consolas;color:#94a3b8">v2.14.0</td><td style="padding:4px 8px;text-align:center;color:#94a3b8">18/08/2026</td><td style="padding:4px 8px;color:#94a3b8">Import CSV DGT rediseñado</td></tr>
      <tr><td style="padding:4px 8px;font-family:Consolas;color:#94a3b8">v2.13.0</td><td style="padding:4px 8px;text-align:center;color:#94a3b8">02/08/2026</td><td style="padding:4px 8px;color:#94a3b8">Campañas SMS + WhatsApp</td></tr>
    </tbody></table>
  </div>`;

  // 🎬 Feb 2026 · Vídeo demo narrado (voz Echo, 3-4 min) con recorrido completo del software.
  //    El MP4 se sirve desde /demo/medicar_demo.mp4. Si aún no existe, el reproductor
  //    muestra un placeholder elegante con un onError handler.
  const MOCKUP_DEMO_VIDEO = `<div style="background:#000;border-radius:10px;overflow:hidden;position:relative">
    <video controls preload="metadata" playsinline poster="/demo/medicar_demo_poster.jpg" style="width:100%;display:block;aspect-ratio:16/9;background:#000" onerror="(function(v){v.style.display='none';var ph=v.nextElementSibling;if(ph)ph.style.display='flex'})(this)">
      <source src="/demo/medicar_demo.mp4" type="video/mp4">
    </video>
    <div style="display:none;position:absolute;inset:0;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:40px;background:linear-gradient(135deg,#0f172a,#1e293b);color:#e2e8f0;font-family:'Segoe UI',system-ui">
      <div style="font-size:48px;margin-bottom:12px">🎬</div>
      <div style="font-size:15px;font-weight:700;color:#f5b301;margin-bottom:8px">Preparando el vídeo demo…</div>
      <div style="font-size:12px;color:#94a3b8;max-width:460px;line-height:1.6">Se está generando el recorrido narrado del software. Vuelve en unos minutos o escríbenos a <a href="mailto:info@medicarplus.es" style="color:#86efac">info@medicarplus.es</a> para una demo personalizada.</div>
    </div>
  </div>`;

  const MOCKUP_STATS = `<div style="background:#0a0f1a;border:1px solid #1e293b;border-radius:8px;padding:14px;font-family:'Segoe UI',system-ui;color:#e2e8f0;font-size:12px">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">
      <div style="color:#f5b301;font-weight:700;font-size:13px">📊 Estadísticas · <span style="color:#22d3ee">MEDICAR</span></div>
      <div style="margin-left:auto;display:flex;gap:6px">
        <span style="background:#0f172a;padding:3px 10px;border-radius:6px;font-size:10px;color:#94a3b8">Autoescuelas</span>
        <span style="background:#f5b30122;border:1px solid #f5b301;padding:3px 10px;border-radius:6px;font-size:10px;color:#f5b301;font-weight:700">🚦 Tráfico</span>
        <span style="background:#0f172a;padding:3px 10px;border-radius:6px;font-size:10px;color:#94a3b8">Avisos SMS</span>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:2fr 1fr;gap:10px;margin-bottom:10px">
      <div style="background:#0f172a;border-radius:6px;padding:10px">
        <div style="color:#94a3b8;font-size:10px;font-weight:700;letter-spacing:.5px;margin-bottom:6px">📊 ENTRADAS DE TRÁFICO POR MES · 2026</div>
        <svg viewBox="0 0 300 90" style="width:100%;height:80px">
          <text x="180" y="10" fill="#7ee3aa" font-size="9" text-anchor="middle" font-weight="700">448</text>
          <rect x="170" y="14" width="20" height="60" fill="url(#g1)" rx="2"/>
          <text x="210" y="34" fill="#7ee3aa" font-size="9" text-anchor="middle" font-weight="700">164</text>
          <rect x="200" y="38" width="20" height="36" fill="url(#g1)" rx="2"/>
          <line x1="0" y1="74" x2="300" y2="74" stroke="#334155" stroke-width=".5"/>
          <text x="15" y="85" fill="#64748b" font-size="7" text-anchor="middle">ENE</text><text x="45" y="85" fill="#64748b" font-size="7" text-anchor="middle">FEB</text><text x="75" y="85" fill="#64748b" font-size="7" text-anchor="middle">MAR</text><text x="105" y="85" fill="#64748b" font-size="7" text-anchor="middle">ABR</text><text x="135" y="85" fill="#64748b" font-size="7" text-anchor="middle">MAY</text><text x="165" y="85" fill="#64748b" font-size="7" text-anchor="middle">JUN</text><text x="182" y="85" fill="#22d3ee" font-size="7" text-anchor="middle" font-weight="700">JUL</text><text x="212" y="85" fill="#22d3ee" font-size="7" text-anchor="middle" font-weight="700">AGO</text><text x="240" y="85" fill="#64748b" font-size="7" text-anchor="middle">SEP</text><text x="265" y="85" fill="#64748b" font-size="7" text-anchor="middle">OCT</text><text x="285" y="85" fill="#64748b" font-size="7" text-anchor="middle">NOV</text>
          <defs><linearGradient id="g1" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#7ee3aa"/><stop offset="1" stop-color="#22d3ee"/></linearGradient></defs>
        </svg>
      </div>
      <div style="background:#0f172a;border-radius:6px;padding:10px">
        <div style="color:#94a3b8;font-size:10px;font-weight:700;letter-spacing:.5px;margin-bottom:6px">🏷️ TIPOS · 2026</div>
        <svg viewBox="0 0 120 90" style="width:100%;height:80px">
          <text x="12" y="18" fill="#7ee3aa" font-size="9" text-anchor="middle" font-weight="700">251</text>
          <rect x="6" y="22" width="12" height="52" fill="#7ee3aa" rx="2"/>
          <text x="12" y="86" fill="#64748b" font-size="6" text-anchor="middle">EXPED</text>
          <rect x="30" y="70" width="12" height="4" fill="#94a3b8" rx="1"/>
          <text x="36" y="86" fill="#64748b" font-size="6" text-anchor="middle">PERIO</text>
          <rect x="54" y="66" width="12" height="8" fill="#f5b301" rx="1"/>
          <text x="60" y="86" fill="#64748b" font-size="6" text-anchor="middle">PRORR</text>
          <rect x="78" y="60" width="12" height="14" fill="#a855f7" rx="1"/>
          <text x="84" y="86" fill="#64748b" font-size="6" text-anchor="middle">RECUP</text>
          <text x="108" y="8" fill="#f472b6" font-size="9" text-anchor="middle" font-weight="700">351</text>
          <rect x="102" y="12" width="12" height="62" fill="url(#g2)" rx="2"/>
          <text x="108" y="86" fill="#f472b6" font-size="6" text-anchor="middle" font-weight="700">RENOV</text>
          <defs><linearGradient id="g2" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#f472b6"/><stop offset="1" stop-color="#c026d3"/></linearGradient></defs>
        </svg>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:8px">
      <div style="background:#0f172a;border:1px solid #7ee3aa33;border-radius:6px;padding:8px 10px"><div style="font-size:9px;color:#94a3b8">Total entradas</div><div style="font-size:15px;color:#7ee3aa;font-weight:700;font-family:Consolas">612</div></div>
      <div style="background:#0f172a;border:1px solid #22d3ee33;border-radius:6px;padding:8px 10px"><div style="font-size:9px;color:#94a3b8">Total importes</div><div style="font-size:15px;color:#22d3ee;font-weight:700;font-family:Consolas">37.250,00 €</div></div>
      <div style="background:#0f172a;border:1px solid #f5b30133;border-radius:6px;padding:8px 10px"><div style="font-size:9px;color:#94a3b8">Total tasas DGT</div><div style="font-size:15px;color:#f5b301;font-weight:700;font-family:Consolas">5.727,19 €</div></div>
      <div style="background:#0f172a;border:1px solid #a855f733;border-radius:6px;padding:8px 10px"><div style="font-size:9px;color:#94a3b8">Facturado + Tasas</div><div style="font-size:15px;color:#a855f7;font-weight:700;font-family:Consolas">42.977,19 €</div></div>
    </div>
    <table style="width:100%;font-size:10px;border-collapse:collapse"><thead><tr style="background:#0f172a;color:#94a3b8"><th style="padding:5px 6px;text-align:left">MES 2026</th><th style="padding:5px 6px;text-align:right;color:#7ee3aa">TOTAL</th><th style="padding:5px 6px;text-align:right;color:#22d3ee">EXPED</th><th style="padding:5px 6px;text-align:right;color:#f472b6">RENOV</th><th style="padding:5px 6px;text-align:right;color:#f5b301">IMPORTE</th><th style="padding:5px 6px;text-align:right;color:#a855f7">TASAS</th></tr></thead><tbody>
      <tr><td style="padding:4px 6px;color:#e2e8f0">Julio</td><td style="padding:4px 6px;text-align:right;color:#7ee3aa;font-weight:700">448</td><td style="padding:4px 6px;text-align:right;color:#22d3ee">197</td><td style="padding:4px 6px;text-align:right;color:#f472b6">242</td><td style="padding:4px 6px;text-align:right;color:#f5b301;font-family:Consolas">27.109,50 €</td><td style="padding:4px 6px;text-align:right;color:#a855f7;font-family:Consolas">4.198,30 €</td></tr>
      <tr><td style="padding:4px 6px;color:#e2e8f0">Agosto</td><td style="padding:4px 6px;text-align:right;color:#7ee3aa;font-weight:700">164</td><td style="padding:4px 6px;text-align:right;color:#22d3ee">54</td><td style="padding:4px 6px;text-align:right;color:#f472b6">109</td><td style="padding:4px 6px;text-align:right;color:#f5b301;font-family:Consolas">10.140,50 €</td><td style="padding:4px 6px;text-align:right;color:#a855f7;font-family:Consolas">1.528,89 €</td></tr>
    </tbody></table>
  </div>`;

  const MOCKUP_CAL = `<div style="background:#0a0f1a;border:1px solid #1e293b;border-radius:8px;padding:14px;font-family:'Segoe UI',system-ui;color:#e2e8f0;font-size:12px">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">
      <div style="color:#22d3ee;font-weight:700;font-size:13px">📅 Citas del día</div>
      <div style="font-size:10px;color:#94a3b8">Sincronizado con Google Calendar</div>
      <span style="margin-left:auto;background:#22c55e;color:#0b1121;padding:2px 8px;border-radius:20px;font-size:10px;font-weight:700">EN VIVO</span>
    </div>
    <div style="display:flex;gap:6px;margin-bottom:10px">
      <span style="background:#22d3ee;color:#0b1121;padding:4px 10px;border-radius:6px;font-size:10px;font-weight:700">📆 Hoy</span>
      <span style="background:#0f172a;padding:4px 10px;border-radius:6px;font-size:10px;color:#94a3b8">📅 Semana</span>
      <span style="background:#0f172a;padding:4px 10px;border-radius:6px;font-size:10px;color:#94a3b8">⚙️ Calendarios</span>
    </div>
    <div style="background:#0f172a;padding:8px 10px;border-radius:6px;margin-bottom:10px;color:#64748b;font-size:11px">🔎 Buscar por nombre o DNI…</div>
    <div style="display:flex;flex-direction:column;gap:6px">
      <div style="background:#0f172a;border-left:3px solid #22d3ee;border-radius:6px;padding:9px 12px;display:flex;align-items:center;gap:10px">
        <div style="font-family:Consolas;color:#22d3ee;font-weight:700;min-width:52px">09:00</div>
        <div style="flex:1"><div style="color:#e2e8f0;font-weight:700;font-size:12px">Joan García Martí</div><div style="font-size:10px;color:#94a3b8">Renovación carnet · Grupo B</div></div>
        <span style="background:#22c55e22;border:1px solid #22c55e;color:#22c55e;padding:2px 8px;border-radius:20px;font-size:9px;font-weight:700">CONFIRMADA</span>
      </div>
      <div style="background:#0f172a;border-left:3px solid #f5b301;border-radius:6px;padding:9px 12px;display:flex;align-items:center;gap:10px">
        <div style="font-family:Consolas;color:#f5b301;font-weight:700;min-width:52px">09:30</div>
        <div style="flex:1"><div style="color:#e2e8f0;font-weight:700;font-size:12px">Marta Serra López</div><div style="font-size:10px;color:#94a3b8">Certificado embarcaciones · PER</div></div>
        <span style="background:#f5b30122;border:1px solid #f5b301;color:#f5b301;padding:2px 8px;border-radius:20px;font-size:9px;font-weight:700">EN CURSO</span>
      </div>
      <div style="background:#0f172a;border-left:3px solid #94a3b8;border-radius:6px;padding:9px 12px;display:flex;align-items:center;gap:10px">
        <div style="font-family:Consolas;color:#94a3b8;font-weight:700;min-width:52px">10:00</div>
        <div style="flex:1"><div style="color:#e2e8f0;font-weight:700;font-size:12px">Carles Puig Font</div><div style="font-size:10px;color:#94a3b8">Reconocimiento armas · Escopeta</div></div>
        <span style="background:#0f172a;border:1px solid #334155;color:#94a3b8;padding:2px 8px;border-radius:20px;font-size:9px;font-weight:700">PENDIENTE</span>
      </div>
      <div style="background:#0f172a;border-left:3px solid #94a3b8;border-radius:6px;padding:9px 12px;display:flex;align-items:center;gap:10px">
        <div style="font-family:Consolas;color:#94a3b8;font-weight:700;min-width:52px">10:30</div>
        <div style="flex:1"><div style="color:#e2e8f0;font-weight:700;font-size:12px">Laura Vidal Roca</div><div style="font-size:10px;color:#94a3b8">Renovación carnet · Grupo A2</div></div>
        <span style="background:#0f172a;border:1px solid #334155;color:#94a3b8;padding:2px 8px;border-radius:20px;font-size:9px;font-weight:700">PENDIENTE</span>
      </div>
    </div>
    <div style="margin-top:10px;padding:8px 10px;background:#065f4622;border:1px solid #22c55e33;border-radius:6px;font-size:11px;color:#6ee7b7;display:flex;align-items:center;gap:8px">🔔 <b>4 citas hoy</b> · Próxima en 12 min · Al importar el CSV se marca automáticamente quién vino</div>
  </div>`;


  useEffect(() => {
    document.title = "MediCar Plus · Software para centros de reconocimiento médico";
  }, []);

  return (
    <div
      style={{
        background: C.bg,
        color: C.text,
        minHeight: "100vh",
        fontFamily: "'Segoe UI', system-ui, -apple-system, sans-serif",
      }}
      data-testid="landing-page"
    >
      {/* NAV */}
      <nav
        style={{
          position: "sticky",
          top: 0,
          zIndex: 50,
          background: "rgba(10,15,26,.92)",
          backdropFilter: "blur(10px)",
          borderBottom: `1px solid ${C.border}`,
        }}
      >
        <div
          style={{
            maxWidth: 1200,
            margin: "0 auto",
            padding: "14px 24px",
            display: "flex",
            alignItems: "center",
            gap: 16,
          }}
        >
          <div style={{ fontFamily: "Georgia, serif", fontSize: 22, fontWeight: 700 }}>
            <span style={{ color: C.gold }}>MediCar</span>{" "}
            <span style={{ color: C.text }}>Plus</span>
          </div>
          <div style={{ flex: 1 }} />
          <a href="#features" style={navLink} data-testid="nav-features">
            Características
          </a>
          <a href="#pricing" style={navLink} data-testid="nav-pricing">
            Precios
          </a>
          <a href="#faq" style={navLink} data-testid="nav-faq">
            FAQ
          </a>
          <a href="#contact" style={navLink} data-testid="nav-contact">
            Contacto
          </a>
          <Link to="/admin" style={{ ...navLink, color: C.textDim }} data-testid="nav-admin">
            Iniciar sesión
          </Link>
          <a
            href="#pricing"
            data-testid="nav-cta"
            style={{
              background: C.gold,
              color: "#0f172a",
              padding: "9px 16px",
              borderRadius: 8,
              textDecoration: "none",
              fontWeight: 700,
              fontSize: 13,
            }}
          >
            PROBAR GRATIS
          </a>
        </div>
      </nav>

      {/* HERO */}
      <section
        style={{
          padding: "80px 24px 60px",
          background: `radial-gradient(ellipse at top, rgba(245,179,1,.1) 0%, transparent 60%), ${C.bg}`,
        }}
      >
        <div style={{ maxWidth: 1100, margin: "0 auto", textAlign: "center" }}>
          <div
            style={{
              display: "inline-block",
              background: `${C.gold}20`,
              color: C.gold,
              padding: "6px 14px",
              borderRadius: 100,
              fontSize: 12,
              fontWeight: 600,
              letterSpacing: 1,
              marginBottom: 20,
              border: `1px solid ${C.gold}40`,
            }}
            data-testid="hero-badge"
          >
            ✓ CUMPLE NORMATIVA DGT · RGPD · FACTURA ELECTRÓNICA
          </div>
          <h1
            style={{
              margin: 0,
              fontSize: "clamp(34px, 6vw, 60px)",
              fontFamily: "Georgia, serif",
              lineHeight: 1.1,
              letterSpacing: -1,
            }}
            data-testid="hero-title"
          >
            El programa <span style={{ color: C.gold }}>especializado</span>
            <br />
            para <span style={{ color: C.gold }}>centros médicos de reconocimientos para conductores</span>
          </h1>
          <p
            style={{
              margin: "24px auto 32px",
              maxWidth: 720,
              fontSize: 18,
              lineHeight: 1.6,
              color: C.textDim,
            }}
            data-testid="hero-subtitle"
          >
            El único software que gestiona <b style={{ color: C.text }}>caja diaria</b>,{" "}
            <b style={{ color: C.text }}>certificados médicos</b>,{" "}
            <b style={{ color: C.text }}>renovaciones DGT</b> y{" "}
            <b style={{ color: C.text }}>contabilidad IRPF</b> en un solo lugar. Diseñado por y para
            centros de reconocimiento de carnet de conducir.
          </p>
          <div style={{ display: "flex", gap: 14, justifyContent: "center", flexWrap: "wrap" }}>
            <a
              href="/api/download/latest-installer"
              data-testid="hero-cta-download"
              style={{
                background: `linear-gradient(135deg, ${C.gold} 0%, #f08c00 100%)`,
                color: "#0f172a",
                padding: "16px 30px",
                borderRadius: 10,
                textDecoration: "none",
                fontWeight: 800,
                fontSize: 15,
                letterSpacing: 0.5,
                boxShadow: "0 12px 40px rgba(245,179,1,.45)",
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              ⬇️ DESCARGAR MEDICAR PLUS <span style={{ opacity: 0.7, fontSize: 12, fontWeight: 600 }}>· Windows</span>
            </a>
            <a
              href="#pricing"
              data-testid="hero-cta-trial"
              style={{
                background: "transparent",
                color: C.text,
                padding: "16px 30px",
                borderRadius: 10,
                textDecoration: "none",
                fontWeight: 700,
                fontSize: 15,
                letterSpacing: 0.5,
                border: `2px solid ${C.gold}`,
              }}
            >
              🚀 Probar gratis 60 días
            </a>
            <a
              href="#features"
              data-testid="hero-cta-features"
              style={{
                background: "transparent",
                color: C.text,
                padding: "16px 30px",
                borderRadius: 10,
                textDecoration: "none",
                fontWeight: 600,
                fontSize: 15,
                border: `1px solid ${C.border}`,
              }}
            >
              Ver características ↓
            </a>
          </div>
          <p
            style={{
              marginTop: 24,
              fontSize: 13,
              color: C.textDim,
            }}
            data-testid="hero-trust"
          >
            ✓ Sin tarjeta · ✓ Sin compromiso · ✓ Cancela cuando quieras
          </p>
          {/* ────── Instalación en 3 pasos · Feb 2026 ────── */}
          <div
            data-testid="hero-install-steps"
            style={{
              marginTop: 48,
              background: "rgba(245,179,1,.06)",
              border: `1px solid ${C.gold}40`,
              borderRadius: 14,
              padding: "22px 20px",
              maxWidth: 820,
              marginInline: "auto",
            }}
          >
            <div style={{ fontSize: 13, color: C.gold, fontWeight: 800, letterSpacing: 1, textTransform: "uppercase", marginBottom: 14 }}>
              ⚡ Instalación en 3 pasos · 5 minutos · sin conocimientos técnicos
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 16, textAlign: "left" }}>
              <div style={{ background: "rgba(0,0,0,.25)", padding: "14px 16px", borderRadius: 10, borderLeft: `3px solid ${C.gold}` }}>
                <div style={{ fontSize: 24, marginBottom: 6 }}>1️⃣</div>
                <div style={{ fontWeight: 700, color: C.text, fontSize: 14, marginBottom: 4 }}>Descarga</div>
                <div style={{ fontSize: 12, color: C.textDim, lineHeight: 1.5 }}>
                  Pulsa <b style={{ color: C.gold }}>⬇️ Descargar MediCar Plus</b> arriba. Guarda el archivo <code style={{ background: "#0b1121", padding: "1px 5px", borderRadius: 3, fontSize: 11 }}>MediCar-Plus-Setup.exe</code>.
                </div>
              </div>
              <div style={{ background: "rgba(0,0,0,.25)", padding: "14px 16px", borderRadius: 10, borderLeft: `3px solid ${C.gold}` }}>
                <div style={{ fontSize: 24, marginBottom: 6 }}>2️⃣</div>
                <div style={{ fontWeight: 700, color: C.text, fontSize: 14, marginBottom: 4 }}>Instala</div>
                <div style={{ fontSize: 12, color: C.textDim, lineHeight: 1.5 }}>
                  Doble clic al archivo. Si sale <i>"Windows protegió su equipo"</i> → <b style={{ color: C.gold }}>Más información → Ejecutar de todos modos</b>. Siguiente → Instalar.
                </div>
              </div>
              <div style={{ background: "rgba(0,0,0,.25)", padding: "14px 16px", borderRadius: 10, borderLeft: `3px solid ${C.gold}` }}>
                <div style={{ fontSize: 24, marginBottom: 6 }}>3️⃣</div>
                <div style={{ fontWeight: 700, color: C.text, fontSize: 14, marginBottom: 4 }}>Activa</div>
                <div style={{ fontSize: 12, color: C.textDim, lineHeight: 1.5 }}>
                  Pega la clave de licencia que recibiste por email y pulsa <b style={{ color: C.gold }}>✓ Activar licencia</b>. ¡Listo!
                </div>
              </div>
            </div>
            <div style={{ textAlign: "center", marginTop: 14, fontSize: 12, color: C.textDim }}>
              ¿Dudas? Mira la{" "}
              <a href="/guia-client-installacio.html" target="_blank" style={{ color: C.gold, textDecoration: "underline", fontWeight: 700 }}>
                guía completa paso a paso (con capturas)
              </a>{" "}
              · ¿Aún no tienes licencia?{" "}
              <a href="/request-license?plan=TRIAL" style={{ color: C.gold, textDecoration: "underline", fontWeight: 700 }}>
                Pídela gratis aquí
              </a>
            </div>
          </div>
        </div>

        {/* Hero visual: mockup del programa */}
        <div
          style={{
            maxWidth: 1000,
            margin: "60px auto 0",
            padding: 20,
            background: `linear-gradient(180deg, ${C.bgCard} 0%, ${C.bg} 100%)`,
            borderRadius: 20,
            border: `1px solid ${C.border}`,
            boxShadow: "0 30px 80px rgba(0,0,0,.5)",
          }}
        >
          <div
            style={{
              background: C.bgAlt,
              borderRadius: 12,
              padding: 18,
              fontFamily: "'Courier New', monospace",
              fontSize: 13,
              lineHeight: 1.7,
              color: C.textDim,
            }}
          >
            <div style={{ display: "flex", gap: 6, marginBottom: 14 }}>
              <div style={{ width: 12, height: 12, borderRadius: "50%", background: "#ef4444" }} />
              <div style={{ width: 12, height: 12, borderRadius: "50%", background: "#f5b301" }} />
              <div style={{ width: 12, height: 12, borderRadius: "50%", background: "#22c55e" }} />
              <span style={{ marginLeft: 12, color: C.textDim, fontSize: 12 }}>
                MediCar Plus · Cierre diario
              </span>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
              <div style={{ background: C.bgCard, padding: 14, borderRadius: 8 }}>
                <div style={{ color: C.gold, fontSize: 10, letterSpacing: 1.5 }}>SALDO ANTERIOR</div>
                <div style={{ color: C.greenSoft, fontSize: 22, fontWeight: 700, marginTop: 4 }}>
                  1.245,80 €
                </div>
              </div>
              <div style={{ background: C.bgCard, padding: 14, borderRadius: 8 }}>
                <div style={{ color: C.gold, fontSize: 10, letterSpacing: 1.5 }}>TOTAL DÍA</div>
                <div style={{ color: C.text, fontSize: 22, fontWeight: 700, marginTop: 4 }}>
                  423,50 €
                </div>
              </div>
              <div style={{ background: C.bgCard, padding: 14, borderRadius: 8 }}>
                <div style={{ color: C.gold, fontSize: 10, letterSpacing: 1.5 }}>CAJA FÍSICA</div>
                <div style={{ color: C.greenSoft, fontSize: 22, fontWeight: 700, marginTop: 4 }}>
                  289,30 €
                </div>
              </div>
            </div>
            <div style={{ marginTop: 14, color: C.gold, fontSize: 11 }}>
              → 3 IMPORTACIONES DGT · 24 CERTIFICADOS
            </div>
          </div>
        </div>
      </section>

      {/* FEATURES */}
      <section id="features" style={{ padding: "80px 24px", background: C.bgAlt }}>
        <div style={{ maxWidth: 1200, margin: "0 auto" }}>
          <div style={{ textAlign: "center", marginBottom: 50 }}>
            <div
              style={{
                color: C.gold,
                fontSize: 12,
                letterSpacing: 2,
                fontWeight: 700,
                marginBottom: 10,
              }}
            >
              CARACTERÍSTICAS
            </div>
            <h2
              style={{
                fontFamily: "Georgia, serif",
                fontSize: "clamp(28px, 4vw, 42px)",
                margin: 0,
                lineHeight: 1.2,
              }}
            >
              Todo lo que necesitas para tu centro médico
            </h2>
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
              gap: 18,
            }}
          >
            <Feature icon="🚗" title="Importación DGT" mockup={MOCKUP_DGT} onOpen={setOpenFeature}>
              Carga los archivos CSV de la DGT en un clic. Detecta duplicados, agrupa clientes y
              cuadra automáticamente el efectivo, tarjeta, Bizum y transferencia.
            </Feature>
            <Feature icon="📋" title="Certificados médicos" mockup={MOCKUP_CERT} onOpen={setOpenFeature}>
              Registro completo de certificados de conducir, permisos, embarcaciones, armas y
              bomberos. Filtros por tipo y período.
            </Feature>
            <Feature icon="📊" title="Contabilidad IRPF" mockup={MOCKUP_IRPF} onOpen={setOpenFeature}>
              Retención IRPF configurable por empresa (7% autónomos nuevos, 15% general, 19%
              capital). Cálculos trimestrales listos para Hacienda.
            </Feature>
            <Feature icon="🔍" title="Auditoría inteligente" mockup={MOCKUP_AUD} onOpen={setOpenFeature}>
              Detecta errores (importes 0€, duplicados de grupo, discrepancias efectivo/tarjeta) con
              filtros por categoría. Nunca más un cuadre erróneo.
            </Feature>
            <Feature icon="💰" title="Reserva de cambio" mockup={MOCKUP_CAMBIO} onOpen={setOpenFeature}>
              Control por paquetes de monedas y billetes. Repercute automáticamente al saldo
              anterior y a la caja física. Perfecto para el cambio diario.
            </Feature>
            <Feature icon="🔒" title="100% seguro y offline" mockup={MOCKUP_SEC} onOpen={setOpenFeature}>
              Funciona sin internet. Tus datos nunca salen de tu ordenador. Backups automáticos
              cifrados. Cumple RGPD y LOPDGDD.
            </Feature>
            <Feature icon="📱" title="SMS y WhatsApp (Premium)" mockup={MOCKUP_SMS} onOpen={setOpenFeature}>
              Envío automático de recordatorios de renovación DGT y avisos de certificados
              expirados. Ideal para fidelizar clientes.
            </Feature>
            <Feature icon="📈" title="Estadísticas avanzadas" mockup={MOCKUP_STATS} onOpen={setOpenFeature}>
              Panel completo con gráficos por mes, tipos de trámite y facturación. Comparativa
              anual, KPIs en vivo y exportación a PDF con un clic.
            </Feature>
            <Feature icon="📅" title="Calendario de citas integrado" mockup={MOCKUP_CAL} onOpen={setOpenFeature}>
              Sincroniza tu Google Calendar (o cualquier servicio externo) y trabaja con las citas
              del día dentro del programa. Al importar el CSV se marca automáticamente quién vino.
            </Feature>
            <Feature icon="🖨️" title="Informes profesionales" mockup={MOCKUP_PRINT} onOpen={setOpenFeature}>
              Cierre diario, resumen mensual, informe anual, ledger de libreta y export IRPF.
              Impresión directa o PDF.
            </Feature>
            <Feature icon="🔄" title="Actualizaciones automáticas" mockup={MOCKUP_UPD} onOpen={setOpenFeature}>
              El programa se actualiza solo. Nuevas funcionalidades, mejoras y correcciones sin que
              tengas que hacer nada.
            </Feature>
            <Feature icon="🎬" title="Vídeo demo" mockup={MOCKUP_DEMO_VIDEO} onOpen={setOpenFeature}>
              Recorrido narrado de 3 minutos por el software: importar CSV de la DGT, flujo del día,
              estadísticas, SMS y auditoría. Pulsa para verlo.
            </Feature>
          </div>
        </div>
      </section>

      {/* PRICING */}
      <section id="pricing" style={{ padding: "80px 24px" }}>
        <div style={{ maxWidth: 1200, margin: "0 auto" }}>
          <div style={{ textAlign: "center", marginBottom: 40 }}>
            <div
              style={{
                color: C.gold,
                fontSize: 12,
                letterSpacing: 2,
                fontWeight: 700,
                marginBottom: 10,
              }}
            >
              PRECIOS
            </div>
            <h2
              style={{
                fontFamily: "Georgia, serif",
                fontSize: "clamp(28px, 4vw, 42px)",
                margin: "0 0 16px",
              }}
            >
              Precios transparentes, sin sorpresas
            </h2>
            <p style={{ color: C.textDim, fontSize: 16, margin: 0 }}>
              60 días gratis · Sin tarjeta · Cancela cuando quieras
            </p>
          </div>

          {/* Toggle mensual/anual */}
          <div
            style={{
              display: "flex",
              justifyContent: "center",
              marginBottom: 40,
              gap: 4,
              background: C.bgCard,
              padding: 4,
              borderRadius: 100,
              width: "fit-content",
              margin: "0 auto 40px",
              border: `1px solid ${C.border}`,
            }}
          >
            <button
              onClick={() => setPeriod("monthly")}
              data-testid="period-monthly"
              style={{
                background: period === "monthly" ? C.gold : "transparent",
                color: period === "monthly" ? "#0f172a" : C.text,
                border: "none",
                padding: "10px 22px",
                borderRadius: 100,
                cursor: "pointer",
                fontWeight: 700,
                fontSize: 13,
                transition: "all .2s",
              }}
            >
              Mensual
            </button>
            <button
              onClick={() => setPeriod("annual")}
              data-testid="period-annual"
              style={{
                background: period === "annual" ? C.gold : "transparent",
                color: period === "annual" ? "#0f172a" : C.text,
                border: "none",
                padding: "10px 22px",
                borderRadius: 100,
                cursor: "pointer",
                fontWeight: 700,
                fontSize: 13,
              }}
            >
              Anual{" "}
              <span
                style={{
                  fontSize: 10,
                  background: period === "annual" ? "#0f172a" : C.green,
                  color: period === "annual" ? C.gold : "#fff",
                  padding: "2px 8px",
                  borderRadius: 100,
                  marginLeft: 4,
                }}
              >
                -17%
              </span>
            </button>
          </div>

          {/* Cards de preus */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
              gap: 20,
              alignItems: "stretch",
            }}
          >
            {/* TRIAL */}
            <PriceCard
              plan="Trial"
              monthlyPrice={0}
              annualPrice={0}
              period={period}
              apiBase={apiBase}
              ctaHref="/request-license?plan=TRIAL"
              features={[
                "Programa completo 60 días",
                "Todas las características",
                "Sin tarjeta de crédito",
                "Soporte por email",
                "Sin límites durante la prueba",
              ]}
            />

            {/* STANDARD */}
            <PriceCard
              plan="Standard"
              monthlyPrice={29.9}
              annualPrice={299.9}
              period={period}
              apiBase={apiBase}
              packageId={period === "annual" ? "STD_ANY" : "STD_MES"}
              ctaHref={`/request-license?plan=STD&period=${period}`}
              features={[
                "Importación DGT ilimitada",
                "Contabilidad IRPF completa",
                "Auditoría y filtros",
                "Reserva de cambio",
                "1 usuario",
                "Soporte por email (48h)",
                "Actualizaciones automáticas",
                "Backups locales cifrados",
              ]}
            />

            {/* PREMIUM */}
            <PriceCard
              plan="Premium"
              monthlyPrice={39.9}
              annualPrice={399.9}
              period={period}
              highlighted
              apiBase={apiBase}
              packageId={period === "annual" ? "PREMIUM_ANY" : "PREMIUM_MES"}
              ctaHref={`/request-license?plan=PREMIUM&period=${period}`}
              features={[
                "Todo lo de Standard",
                "Hasta 2 usuarios simultáneos",
                "SMS + WhatsApp automáticos",
                "Recordatorios DGT clientes",
                "Backup automático en la nube",
                "Soporte prioritario (24h)",
                "Formación gratuita 1h",
                "Actualizaciones prioritarias",
              ]}
            />
          </div>

          {/* 🏢 Feb 2026 · Mensaje de personalización para centros con varios locales */}
          <div
            style={{
              marginTop: 28,
              padding: "22px 24px",
              background: `linear-gradient(135deg, ${C.bgCard} 0%, rgba(245,179,1,.07) 100%)`,
              borderRadius: 14,
              border: `1px solid ${C.gold}55`,
              textAlign: "center",
            }}
          >
            <div style={{ color: C.gold, fontWeight: 700, marginBottom: 6, fontSize: 15 }}>
              🏢 ¿Tienes varios centros médicos?
            </div>
            <div style={{ color: C.text, fontSize: 14, lineHeight: 1.6, maxWidth: 720, margin: "0 auto" }}>
              Nos adaptamos a medida. Para empresas con <b style={{ color: C.goldSoft }}>más de un local</b> ofrecemos
              planes personalizados tanto en <b>precio</b> como en <b>soporte dedicado</b>.
              Escríbenos a <a href="mailto:info@medicarplus.es" style={{ color: C.greenSoft }}>info@medicarplus.es</a> y te preparamos una propuesta a medida en 24 horas.
            </div>
          </div>

          <div
            style={{
              marginTop: 40,
              padding: 24,
              background: C.bgCard,
              borderRadius: 14,
              border: `1px solid ${C.border}`,
              textAlign: "center",
            }}
          >
            <div style={{ color: C.gold, fontWeight: 700, marginBottom: 8 }}>
              💳 Formas de pago aceptadas
            </div>
            <div style={{ color: C.textDim, fontSize: 14 }}>
              Tarjeta de crédito/débito (Stripe seguro) · Transferencia bancaria · Bizum (consultar)
              · IVA incluido en todos los precios · Factura profesional al instante
            </div>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" style={{ padding: "80px 24px", background: C.bgAlt }}>
        <div style={{ maxWidth: 900, margin: "0 auto" }}>
          <div style={{ textAlign: "center", marginBottom: 40 }}>
            <div
              style={{
                color: C.gold,
                fontSize: 12,
                letterSpacing: 2,
                fontWeight: 700,
                marginBottom: 10,
              }}
            >
              PREGUNTAS FRECUENTES
            </div>
            <h2
              style={{
                fontFamily: "Georgia, serif",
                fontSize: "clamp(28px, 4vw, 42px)",
                margin: 0,
              }}
            >
              Resolvemos tus dudas
            </h2>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {[
              {
                q: "¿Cómo funciona la prueba gratuita de 60 días?",
                a: "Rellenas el formulario con los datos de tu centro, recibes en el email la clave de licencia, la introduces en el programa y ya tienes 60 días completos con todas las funcionalidades. No pedimos tarjeta de crédito ni ningún compromiso. Al finalizar los 60 días, si te interesa, contratas el plan que prefieras. Si no, simplemente el programa deja de funcionar.",
              },
              {
                q: "¿El programa funciona sin internet?",
                a: "Sí. MediCar Plus está diseñado como aplicación de escritorio (Windows). Una vez activado, funciona completamente offline. Solo necesita internet para: 1) La activación inicial de la licencia, 2) Las actualizaciones automáticas, y 3) El envío de SMS/WhatsApp del plan Premium.",
              },
              {
                q: "¿Cumple con la normativa DGT?",
                a: "Sí. El programa lee directamente los archivos CSV que exporta el software oficial de la DGT (el que usan todos los centros de reconocimiento). Además, genera informes cuadrados con las categorías DGT estándar: permisos, renovaciones, PPV, cursos, etc.",
              },
              {
                q: "¿Y mis datos están seguros? ¿Cumple RGPD?",
                a: "Absolutamente. Todos tus datos (clientes, ingresos, contabilidad) se guardan localmente en tu ordenador, cifrados. Ni siquiera nosotros tenemos acceso. Los backups automáticos también son locales. Cumple 100% con RGPD, LOPDGDD y normativa española de protección de datos.",
              },
              {
                q: "¿Qué diferencia hay entre Standard y Premium?",
                a: "Standard es el programa completo para 1 usuario, ideal para centros pequeños/medianos. Premium añade: hasta 2 usuarios simultáneos, envío automático de SMS/WhatsApp a clientes para recordarles renovaciones DGT (aumenta las ventas), backup en la nube automático, soporte prioritario (respuesta en 24h vs 48h) y una hora de formación gratuita.",
              },
              {
                q: "¿Puedo cancelar cuando quiera?",
                a: "Sí, sin penalizaciones. Si pagas mensual, cancelas y el mes siguiente ya no se cobra. Si pagas anual, tienes todo el año contratado (no reembolsamos meses no usados, pero puedes seguir usándolo hasta que expire). Todos los datos que hayas metido siguen siendo tuyos y puedes exportarlos.",
              },
              {
                q: "¿Cómo se actualiza el programa?",
                a: "Automáticamente. Cada vez que abres MediCar Plus, comprueba si hay una versión nueva y la descarga en segundo plano. Al cerrar el programa, se instala. La próxima vez que abras, ya tienes todas las mejoras y novedades. Sin interrupciones.",
              },
              {
                q: "¿Hay una migración desde otro programa?",
                a: "Sí, importamos desde Excel/CSV. Si vienes de otro software, mándanos un ejemplo de tus datos actuales y te ayudamos con la migración en el plan Premium (incluido). En Standard te damos instrucciones detalladas para hacerlo tú mismo en 30 minutos.",
              },
            ].map((it, i) => (
              <FaqItem key={i} q={it.q} a={it.a} idx={i} />
            ))}
          </div>
        </div>
      </section>

      {/* CTA FINAL */}
      <section
        style={{
          padding: "80px 24px",
          background: `linear-gradient(135deg, ${C.bgAlt} 0%, ${C.bg} 100%)`,
        }}
      >
        <div
          style={{
            maxWidth: 900,
            margin: "0 auto",
            textAlign: "center",
            padding: 40,
            background: C.bgCard,
            borderRadius: 20,
            border: `1px solid ${C.gold}40`,
          }}
        >
          <h2
            style={{
              margin: "0 0 12px",
              fontFamily: "Georgia, serif",
              fontSize: "clamp(28px, 4vw, 38px)",
              color: C.gold,
            }}
          >
            Empieza gratis hoy mismo
          </h2>
          <p style={{ color: C.textDim, fontSize: 17, marginBottom: 24 }}>
            60 días completos · Sin tarjeta · Sin compromiso
          </p>
          <a
            href="/request-license?plan=TRIAL"
            data-testid="cta-final-trial"
            style={{
              display: "inline-block",
              background: C.gold,
              color: "#0f172a",
              padding: "18px 40px",
              borderRadius: 12,
              textDecoration: "none",
              fontWeight: 700,
              fontSize: 17,
              letterSpacing: 0.5,
              boxShadow: "0 20px 60px rgba(245,179,1,.4)",
            }}
          >
            🚀 EMPEZAR PRUEBA GRATIS
          </a>
        </div>
      </section>

      {/* CONTACT + FOOTER */}
      <footer id="contact" style={{ padding: "60px 24px 24px", background: "#050810" }}>
        <div style={{ maxWidth: 1200, margin: "0 auto" }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
              gap: 30,
              marginBottom: 40,
            }}
          >
            <div>
              <div style={{ fontFamily: "Georgia, serif", fontSize: 22, marginBottom: 8 }}>
                <span style={{ color: C.gold }}>MediCar</span> Plus
              </div>
              <p style={{ color: C.textDim, fontSize: 13, lineHeight: 1.7, margin: 0 }}>
                Software especializado para centros de reconocimiento médico y de conducir.
                Diseñado con y para profesionales del sector.
              </p>
            </div>
            <div>
              <div style={{ color: C.gold, fontWeight: 700, fontSize: 13, marginBottom: 12 }}>
                Producto
              </div>
              <FooterLink href="#features">Características</FooterLink>
              <FooterLink href="#pricing">Precios</FooterLink>
              <FooterLink href="#faq">FAQ</FooterLink>
              <FooterLink href="/request-license">Probar gratis</FooterLink>
            </div>
            <div>
              <div style={{ color: C.gold, fontWeight: 700, fontSize: 13, marginBottom: 12 }}>
                Cuenta
              </div>
              <FooterLink href="/admin">Iniciar sesión</FooterLink>
              <FooterLink href="/request-license">Solicitar licencia</FooterLink>
              <FooterLink href="/privacy">Política de privacidad</FooterLink>
            </div>
            <div>
              <div style={{ color: C.gold, fontWeight: 700, fontSize: 13, marginBottom: 12 }}>
                Contacto
              </div>
              <div style={{ color: C.textDim, fontSize: 13, lineHeight: 1.9 }}>
                📧{" "}
                <a
                  href="mailto:info@medicarplus.es"
                  style={{ color: C.textDim, textDecoration: "none" }}
                  data-testid="footer-email"
                >
                  info@medicarplus.es
                </a>
                <br />
                🌐 medicarplus.es
                <br />
                📍 España
              </div>
            </div>
          </div>
          <div
            style={{
              borderTop: `1px solid ${C.border}`,
              paddingTop: 20,
              display: "flex",
              gap: 20,
              flexWrap: "wrap",
              alignItems: "center",
              justifyContent: "space-between",
              fontSize: 12,
              color: C.textDim,
            }}
          >
            <div>© 2026 MediCar Plus · Todos los derechos reservados</div>
            <div style={{ display: "flex", gap: 20 }}>
              <a href="/privacy" style={{ color: C.textDim, textDecoration: "none" }}>
                Privacidad
              </a>
              <a href="/privacy#cookies" style={{ color: C.textDim, textDecoration: "none" }}>
                Cookies
              </a>
              <a href="/privacy#terms" style={{ color: C.textDim, textDecoration: "none" }}>
                Términos
              </a>
              <a href="/privacy#lssice" style={{ color: C.textDim, textDecoration: "none" }}>
                LSSICE
              </a>
            </div>
          </div>
        </div>
      </footer>
      <FeatureModal feature={openFeature} onClose={() => setOpenFeature(null)} />
    </div>
  );
}

const navLink = {
  color: "#e8ecf2",
  textDecoration: "none",
  fontSize: 14,
  fontWeight: 500,
  padding: "6px 10px",
};

const FooterLink = ({ href, children }) => (
  <div style={{ marginBottom: 6 }}>
    <a href={href} style={{ color: "#94a3b8", textDecoration: "none", fontSize: 13 }}>
      {children}
    </a>
  </div>
);

const FaqItem = ({ q, a, idx }) => {
  const [open, setOpen] = useState(idx === 0);
  return (
    <div
      style={{
        background: "#131c2e",
        border: `1px solid ${open ? "#f5b301" : "#1e293b"}`,
        borderRadius: 12,
        overflow: "hidden",
        transition: "border-color .2s",
      }}
    >
      <button
        onClick={() => setOpen(!open)}
        data-testid={`faq-toggle-${idx}`}
        style={{
          width: "100%",
          background: "transparent",
          border: "none",
          color: "#e8ecf2",
          padding: "18px 20px",
          textAlign: "left",
          cursor: "pointer",
          fontSize: 15,
          fontWeight: 600,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 12,
        }}
      >
        <span>{q}</span>
        <span
          style={{
            color: "#f5b301",
            fontSize: 20,
            transform: open ? "rotate(45deg)" : "rotate(0)",
            transition: "transform .2s",
            flexShrink: 0,
          }}
        >
          +
        </span>
      </button>
      {open && (
        <div
          style={{
            padding: "0 20px 18px",
            color: "#94a3b8",
            fontSize: 14,
            lineHeight: 1.7,
          }}
        >
          {a}
        </div>
      )}
    </div>
  );
};
