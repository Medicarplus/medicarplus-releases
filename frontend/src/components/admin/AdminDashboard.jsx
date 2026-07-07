import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
  AdminTokenStore,
  approveRequest,
  generateLicense,
  getStats,
  listLicenses,
  listRequests,
  rejectRequest,
  revokeLicense,
} from "@/lib/licenseApi";

const fmtDate = (iso) => {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("ca-ES", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  } catch (_e) {
    return iso;
  }
};
const statusBadge = (s) => {
  const map = {
    active: { bg: "#065f46", fg: "#d1fae5", label: "ACTIVA" },
    revoked: { bg: "#7f1d1d", fg: "#fee2e2", label: "REVOCADA" },
    expired: { bg: "#78350f", fg: "#fef3c7", label: "EXPIRADA" },
    pending: { bg: "#1e40af", fg: "#dbeafe", label: "PENDENT" },
    approved: { bg: "#065f46", fg: "#d1fae5", label: "APROVADA" },
    rejected: { bg: "#7f1d1d", fg: "#fee2e2", label: "REBUTJADA" },
  };
  const it = map[s] || { bg: "#334155", fg: "#e2e8f0", label: (s || "?").toUpperCase() };
  return (
    <span
      style={{
        background: it.bg,
        color: it.fg,
        padding: "3px 8px",
        borderRadius: 6,
        fontSize: 10,
        letterSpacing: 1,
        fontWeight: 700,
        fontFamily: "'Courier New', monospace",
      }}
    >
      {it.label}
    </span>
  );
};

const copy = async (text) => {
  try {
    await navigator.clipboard.writeText(text);
    toast.success("Copiat al portapapers");
  } catch (_e) {
    toast.error("No s'ha pogut copiar");
  }
};

// ----- New license modal -----
function NewLicenseModal({ open, onClose, onCreated }) {
  const [form, setForm] = useState({
    install_id: "",
    client_name: "",
    client_email: "",
    duration_days: "",
    plan: "STD",
    notes: "",
  });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (open)
      setForm({
        install_id: "",
        client_name: "",
        client_email: "",
        duration_days: "",
        plan: "STD",
        notes: "",
      });
  }, [open]);
  if (!open) return null;
  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      const payload = {
        install_id: form.install_id.trim().toUpperCase(),
        client_name: form.client_name.trim(),
        client_email: form.client_email.trim() || null,
        plan: form.plan,
        notes: form.notes.trim() || null,
      };
      if (form.duration_days) payload.duration_days = parseInt(form.duration_days, 10);
      const lic = await generateLicense(payload);
      toast.success("Llicència creada");
      onCreated(lic);
      onClose();
    } catch (ex) {
      const msg = ex?.response?.data?.detail;
      setErr(typeof msg === "string" ? msg : JSON.stringify(msg) || ex.message);
    } finally {
      setBusy(false);
    }
  };
  const inputStyle = {
    width: "100%",
    padding: "10px 12px",
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
  return (
    <div
      data-testid="new-license-modal"
      onClick={(e) => e.target === e.currentTarget && onClose()}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(15,23,42,0.9)",
        zIndex: 999,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 20,
        backdropFilter: "blur(6px)",
      }}
    >
      <form
        onSubmit={submit}
        style={{
          background: "#1e293b",
          border: "2px solid #f5b301",
          borderRadius: 14,
          padding: 32,
          maxWidth: 560,
          width: "100%",
          color: "#e2e8f0",
          fontFamily: "Georgia, serif",
        }}
      >
        <h2 style={{ margin: "0 0 20px 0", color: "#f5b301" }}>➕ Nova llicència</h2>
        <div style={{ display: "grid", gap: 12 }}>
          <div>
            <label style={labelStyle}>INSTALL ID *</label>
            <input
              data-testid="lic-install-id"
              required
              placeholder="CD-XXXX-XXXX-XXXX-XXXX"
              value={form.install_id}
              onChange={(e) => setForm({ ...form, install_id: e.target.value.toUpperCase() })}
              style={inputStyle}
            />
          </div>
          <div>
            <label style={labelStyle}>CLIENT *</label>
            <input
              data-testid="lic-client-name"
              required
              value={form.client_name}
              onChange={(e) => setForm({ ...form, client_name: e.target.value })}
              style={inputStyle}
            />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 12 }}>
            <div>
              <label style={labelStyle}>EMAIL</label>
              <input
                data-testid="lic-client-email"
                type="email"
                value={form.client_email}
                onChange={(e) => setForm({ ...form, client_email: e.target.value })}
                style={inputStyle}
              />
            </div>
            <div>
              <label style={labelStyle}>PLAN</label>
              <select
                data-testid="lic-plan"
                value={form.plan}
                onChange={(e) => setForm({ ...form, plan: e.target.value })}
                style={inputStyle}
              >
                <option value="TRIAL">TRIAL</option>
                <option value="STD">STD</option>
                <option value="PREMIUM">PREMIUM</option>
                <option value="MASTER">MASTER</option>
              </select>
            </div>
          </div>
          <div>
            <label style={labelStyle}>
              DURADA (dies) — buit = perpètua
            </label>
            <input
              data-testid="lic-duration"
              type="number"
              min="1"
              value={form.duration_days}
              onChange={(e) => setForm({ ...form, duration_days: e.target.value })}
              placeholder="365"
              style={inputStyle}
            />
          </div>
          <div>
            <label style={labelStyle}>NOTES</label>
            <textarea
              data-testid="lic-notes"
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
              rows={2}
              style={{ ...inputStyle, resize: "vertical", fontFamily: "Georgia, serif" }}
            />
          </div>
        </div>
        {err && (
          <div
            data-testid="new-license-error"
            style={{ color: "#ef4444", fontSize: 13, marginTop: 12 }}
          >
            ✗ {err}
          </div>
        )}
        <div
          style={{
            display: "flex",
            gap: 10,
            justifyContent: "flex-end",
            marginTop: 22,
          }}
        >
          <button
            type="button"
            onClick={onClose}
            style={{
              padding: "10px 18px",
              background: "transparent",
              border: "1.5px solid #64748b",
              borderRadius: 8,
              color: "#cbd5e1",
              cursor: "pointer",
              fontFamily: "Georgia, serif",
            }}
          >
            Cancel·la
          </button>
          <button
            data-testid="new-license-submit"
            type="submit"
            disabled={busy}
            style={{
              padding: "10px 22px",
              background: busy ? "#475569" : "linear-gradient(135deg,#f5b301,#d97706)",
              border: "none",
              borderRadius: 8,
              color: "#0f172a",
              cursor: busy ? "wait" : "pointer",
              fontWeight: 700,
              letterSpacing: 1.2,
              fontFamily: "Georgia, serif",
            }}
          >
            {busy ? "Generant…" : "✓ Generar"}
          </button>
        </div>
      </form>
    </div>
  );
}

// ----- Post-approval / post-create result modal (shows JWT to copy) -----
function LicenseKeyModal({ data, onClose }) {
  if (!data) return null;
  const info = data.license || data;
  return (
    <div
      data-testid="license-key-modal"
      onClick={(e) => e.target === e.currentTarget && onClose()}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(15,23,42,0.95)",
        zIndex: 1000,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 20,
        backdropFilter: "blur(6px)",
      }}
    >
      <div
        style={{
          background: "#1e293b",
          border: "2px solid #22c55e",
          borderRadius: 14,
          padding: 32,
          maxWidth: 720,
          width: "100%",
          color: "#e2e8f0",
          fontFamily: "Georgia, serif",
        }}
      >
        <h2 style={{ margin: "0 0 6px 0", color: "#22c55e" }}>
          ✓ Llicència generada
        </h2>
        <p style={{ margin: "0 0 20px 0", color: "#94a3b8", fontSize: 13 }}>
          Copia la clau i envia-la al client. També podràs consultar-la després des de la taula.
        </p>
        <div style={{ display: "grid", gap: 10, fontSize: 13 }}>
          <Row label="Client" value={info.client_name} />
          <Row label="Install ID" value={info.install_id} mono />
          <Row label="Plan" value={info.plan} />
          <Row label="Caduca" value={info.expires_at ? fmtDate(info.expires_at) : "Perpètua"} />
          {"email_sent" in data && (
            <Row
              label="Email"
              value={
                data.email_sent
                  ? "✓ Enviat al client"
                  : data.mailer_configured === false
                    ? "⚠ Resend no configurat (envia manualment)"
                    : `✗ ${data.email_error || "no enviat"}`
              }
            />
          )}
        </div>
        <div style={{ marginTop: 20 }}>
          <div
            style={{
              fontSize: 11,
              color: "#f5b301",
              letterSpacing: 1.5,
              fontWeight: 700,
              marginBottom: 8,
            }}
          >
            LICENSE KEY (JWT)
          </div>
          <textarea
            data-testid="license-key-textarea"
            readOnly
            value={info.license_key || ""}
            rows={5}
            style={{
              width: "100%",
              padding: 12,
              background: "#0f172a",
              border: "1.5px dashed #f5b301",
              borderRadius: 8,
              color: "#e2e8f0",
              fontFamily: "'Courier New', monospace",
              fontSize: 11,
              lineHeight: 1.5,
              wordBreak: "break-all",
              resize: "vertical",
              boxSizing: "border-box",
            }}
            onClick={(e) => e.target.select()}
          />
        </div>
        <div
          style={{
            display: "flex",
            gap: 10,
            justifyContent: "flex-end",
            marginTop: 20,
          }}
        >
          <button
            data-testid="license-copy-key"
            onClick={() => copy(info.license_key)}
            style={{
              padding: "10px 22px",
              background: "linear-gradient(135deg,#f5b301,#d97706)",
              border: "none",
              borderRadius: 8,
              color: "#0f172a",
              cursor: "pointer",
              fontWeight: 700,
              letterSpacing: 1.2,
              fontFamily: "Georgia, serif",
            }}
          >
            📋 Copiar JWT
          </button>
          <button
            data-testid="license-email-mailto"
            onClick={() => {
              const email = data?.license?.client_email || data?.request?.email || "";
              const jwt = data?.license?.license_key || "";
              const client = data?.license?.client_name || data?.request?.company_name || "";
              const plan = (data?.license?.plan || "").toUpperCase();
              const expLbl = data?.license?.expires_at
                ? new Date(data.license.expires_at).toLocaleDateString("ca-ES")
                : "perpètua";
              const subject = encodeURIComponent(`La teva llicència MediCar Plus (${plan})`);
              const body = encodeURIComponent(
                `Benvingut/da a MediCar Plus!\n\n` +
                `Aquí tens la teva clau de llicència personal (${plan}, vàlida fins a ${expLbl}):\n\n` +
                `${jwt}\n\n` +
                `📥 DESCARREGA L'APP:\n` +
                `[Enganxa aquí el link de WeTransfer o Google Drive amb el fitxer .exe]\n\n` +
                `📖 GUIA D'INSTAL·LACIÓ (per no perdre't):\n` +
                `https://project-helper-47.preview.emergentagent.com/guia-client-installacio.html\n\n` +
                `Passos ràpids:\n` +
                `1. Descarrega el fitxer del link de dalt\n` +
                `2. Feu doble clic per instal·lar (si Windows avisa, cliqui "Más información" → "Ejecutar de todos modos")\n` +
                `3. Un cop instal·lada, obri l'app i enganxi la clau de dalt\n` +
                `4. Segueixi el wizard per configurar els noms de les seves empreses\n` +
                `5. Ja pot començar a treballar!\n\n` +
                `Dubtes? Escrigui'm a brugulatmarc@gmail.com\n\n` +
                `Salutacions,\nM. Brugulat Lopez\nMediCar Plus`,
              );
              window.location.href = `mailto:${email}?subject=${subject}&body=${body}`;
            }}
            disabled={!(data?.license?.client_email || data?.request?.email)}
            style={{
              padding: "10px 22px",
              background: "linear-gradient(135deg,#059669,#10b981)",
              border: "none",
              borderRadius: 8,
              color: "#fff",
              cursor: "pointer",
              fontWeight: 700,
              letterSpacing: 1.2,
              fontFamily: "Georgia, serif",
            }}
          >
            📧 Enviar per email
          </button>
          <button
            data-testid="license-close-modal"
            onClick={onClose}
            style={{
              padding: "10px 22px",
              background: "transparent",
              border: "1.5px solid #64748b",
              borderRadius: 8,
              color: "#cbd5e1",
              cursor: "pointer",
              fontFamily: "Georgia, serif",
            }}
          >
            Tancar
          </button>
        </div>
      </div>
    </div>
  );
}

const Row = ({ label, value, mono }) => (
  <div style={{ display: "grid", gridTemplateColumns: "120px 1fr", gap: 12 }}>
    <div style={{ color: "#f5b301", fontSize: 11, letterSpacing: 1, paddingTop: 2 }}>
      {label.toUpperCase()}
    </div>
    <div style={{ fontFamily: mono ? "'Courier New',monospace" : "Georgia,serif" }}>
      {value || "—"}
    </div>
  </div>
);

// =============================================================================
// Main dashboard
// =============================================================================
export default function AdminDashboard({ onLogout }) {
  const [tab, setTab] = useState("licenses");
  const [licenses, setLicenses] = useState([]);
  const [requests, setRequests] = useState([]);
  const [pendingCount, setPendingCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [keyModal, setKeyModal] = useState(null);
  const [query, setQuery] = useState("");
  const [statsData, setStatsData] = useState(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [lic, req, st] = await Promise.all([listLicenses(), listRequests(), getStats().catch(() => null)]);
      setLicenses(lic.items || []);
      setRequests(req.items || []);
      setPendingCount(req.pending || 0);
      setStatsData(st);
    } catch (ex) {
      if (ex?.response?.status === 401) {
        toast.error("Sessió expirada");
        AdminTokenStore.clear();
        onLogout();
      } else {
        toast.error("Error carregant dades: " + (ex.message || ""));
      }
    } finally {
      setLoading(false);
    }
  }, [onLogout]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const stats = useMemo(() => {
    const s = { total: licenses.length, active: 0, revoked: 0, expired: 0 };
    for (const l of licenses) {
      if (l.status in s) s[l.status]++;
    }
    return s;
  }, [licenses]);

  const filteredLicenses = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return licenses;
    return licenses.filter(
      (l) =>
        l.install_id.toLowerCase().includes(q) ||
        (l.client_name || "").toLowerCase().includes(q) ||
        (l.client_email || "").toLowerCase().includes(q),
    );
  }, [licenses, query]);

  const handleRevoke = async (installId) => {
    const reason = prompt("Motiu de la revocació (opcional):", "revoked_by_admin");
    if (reason === null) return;
    try {
      await revokeLicense(installId, reason || "revoked_by_admin");
      toast.success("Llicència revocada");
      await refresh();
    } catch (ex) {
      toast.error(ex?.response?.data?.detail || ex.message);
    }
  };

  const handleResetHwid = async (installId) => {
    const ok = window.confirm(
      `Desbloquejar el HWID d'aquesta llicència?\n\n` +
      `Fes això només si el client legítim canvia d'ordinador.\n` +
      `La propera vegada que activi la llicència al nou PC, quedarà vinculada al nou maquinari.`,
    );
    if (!ok) return;
    try {
      const { resetHwid } = await import("@/lib/licenseApi");
      const res = await resetHwid(installId);
      toast.success(`HWID desbloquejat (reset #${res.reset_count})`);
      await refresh();
    } catch (ex) {
      toast.error(ex?.response?.data?.detail || ex.message);
    }
  };

  const handleCopyJwt = async (installId) => {
    try {
      const { getLicense } = await import("@/lib/licenseApi");
      const lic = await getLicense(installId);
      if (!lic.license_key) {
        toast.error("Aquesta llicència no té clau (probablement revocada)");
        return;
      }
      await copy(lic.license_key);
    } catch (ex) {
      toast.error(ex?.response?.data?.detail || ex.message);
    }
  };

  const handleApprove = async (req) => {
    // Default de durada segons el pla sol·licitat
    const plan = (req.plan_requested || "").toUpperCase();
    let defaultDays = "365";
    let planLabel = plan;
    if (plan === "TRIAL") { defaultDays = "30"; planLabel = "TRIAL 30 dies"; }
    else if (plan === "STD_MES" || plan === "PREMIUM_MES") { defaultDays = "30"; planLabel = plan + " (mensual)"; }
    else if (plan === "STD_ANY" || plan === "PREMIUM_ANY") { defaultDays = "365"; planLabel = plan + " (anual)"; }
    const installLbl = req.install_id || "(sense Install ID · s'usarà PENDING)";
    const durationRaw = prompt(
      `Aprovar "${req.company_name}"\nPla: ${planLabel}\nInstall ID: ${installLbl}\n\nDurada en dies (buit = perpètua):`,
      defaultDays,
    );
    if (durationRaw === null) return;
    const payload = { send_email: true };
    if (durationRaw.trim()) {
      const n = parseInt(durationRaw, 10);
      if (Number.isNaN(n) || n < 1) {
        toast.error("Durada invàlida");
        return;
      }
      payload.duration_days = n;
    }
    try {
      const res = await approveRequest(req.id, payload);
      setKeyModal(res);
      // auto-copy on approve
      if (res?.license?.license_key) {
        try {
          await navigator.clipboard.writeText(res.license.license_key);
        } catch (_e) {
          // ignore
        }
      }
      toast.success(
        res.email_sent
          ? "Aprovada + email enviat"
          : "Aprovada (JWT copiat, envia manualment)",
      );
      await refresh();
    } catch (ex) {
      toast.error(ex?.response?.data?.detail || ex.message);
    }
  };

  const handleReject = async (req) => {
    const reason = prompt(`Rebutjar "${req.company_name}". Motiu:`, "");
    if (reason === null) return;
    try {
      await rejectRequest(req.id, reason || "rejected_by_admin");
      toast.success("Sol·licitud rebutjada");
      await refresh();
    } catch (ex) {
      toast.error(ex?.response?.data?.detail || ex.message);
    }
  };

  const doLogout = () => {
    AdminTokenStore.clear();
    onLogout();
  };

  const th = {
    textAlign: "left",
    padding: "10px 12px",
    fontSize: 11,
    letterSpacing: 1.2,
    color: "#f5b301",
    borderBottom: "2px solid #334155",
    fontWeight: 700,
  };
  const td = {
    padding: "10px 12px",
    fontSize: 13,
    borderBottom: "1px solid #1e293b",
  };

  return (
    <div
      data-testid="admin-dashboard"
      style={{
        minHeight: "100vh",
        background: "#0f172a",
        color: "#e2e8f0",
        fontFamily: "Georgia, serif",
      }}
    >
      {/* Header */}
      <header
        style={{
          background: "#1e293b",
          borderBottom: "2px solid #f5b301",
          padding: "16px 28px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <div>
          <h1 style={{ margin: 0, color: "#f5b301", fontSize: 22, letterSpacing: 1 }}>
            🔐 MediCar Plus · License Admin
          </h1>
          <p style={{ margin: "3px 0 0", color: "#94a3b8", fontSize: 12 }}>
            Marc Brugulat Lopez
          </p>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <button
            data-testid="admin-refresh"
            onClick={refresh}
            disabled={loading}
            style={{
              padding: "8px 16px",
              background: "transparent",
              border: "1.5px solid #64748b",
              borderRadius: 8,
              color: "#cbd5e1",
              cursor: "pointer",
              fontFamily: "Georgia, serif",
            }}
          >
            {loading ? "⟳ …" : "⟳ Refrescar"}
          </button>
          <button
            data-testid="admin-logout"
            onClick={doLogout}
            style={{
              padding: "8px 16px",
              background: "#7f1d1d",
              border: "none",
              borderRadius: 8,
              color: "#fff",
              cursor: "pointer",
              fontFamily: "Georgia, serif",
            }}
          >
            Sortir
          </button>
        </div>
      </header>

      {/* Stats */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
          gap: 14,
          padding: 24,
        }}
      >
        <StatCard label="Total" value={stats.total} color="#e2e8f0" />
        <StatCard label="Actives" value={stats.active} color="#22c55e" />
        <StatCard label="Revocades" value={stats.revoked} color="#ef4444" />
        <StatCard label="Expirades" value={stats.expired} color="#f59e0b" />
        <StatCard
          label="Sol·licituds pendents"
          value={pendingCount}
          color={pendingCount ? "#3b82f6" : "#64748b"}
          highlight={pendingCount > 0}
        />
      </div>

      {/* Tabs */}
      <div
        style={{
          display: "flex",
          gap: 4,
          padding: "0 24px",
          borderBottom: "1px solid #334155",
        }}
      >
        <TabBtn
          testid="tab-licenses"
          active={tab === "licenses"}
          onClick={() => setTab("licenses")}
        >
          Llicències ({stats.total})
        </TabBtn>
        <TabBtn
          testid="tab-requests"
          active={tab === "requests"}
          onClick={() => setTab("requests")}
        >
          Sol·licituds
          {pendingCount > 0 && (
            <span
              data-testid="pending-badge"
              style={{
                marginLeft: 8,
                background: "#3b82f6",
                color: "#fff",
                fontSize: 10,
                padding: "2px 7px",
                borderRadius: 10,
                fontWeight: 700,
              }}
            >
              {pendingCount}
            </span>
          )}
        </TabBtn>
        <TabBtn
          testid="tab-stats"
          active={tab === "stats"}
          onClick={() => setTab("stats")}
        >
          📊 Estadístiques
        </TabBtn>
      </div>

      {/* Content */}
      <div style={{ padding: 24 }}>
        {tab === "licenses" && (
          <>
            <div
              style={{
                display: "flex",
                gap: 12,
                marginBottom: 16,
                flexWrap: "wrap",
              }}
            >
              <input
                data-testid="license-search"
                placeholder="Cercar per install_id, client o email…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                style={{
                  flex: 1,
                  minWidth: 260,
                  padding: "10px 14px",
                  background: "#1e293b",
                  border: "1.5px solid #334155",
                  borderRadius: 8,
                  color: "#e2e8f0",
                  fontFamily: "'Courier New', monospace",
                  fontSize: 13,
                  boxSizing: "border-box",
                }}
              />
              <button
                data-testid="new-license-open"
                onClick={() => setShowNew(true)}
                style={{
                  padding: "10px 22px",
                  background: "linear-gradient(135deg,#f5b301,#d97706)",
                  border: "none",
                  borderRadius: 8,
                  color: "#0f172a",
                  cursor: "pointer",
                  fontWeight: 700,
                  letterSpacing: 1.2,
                  fontFamily: "Georgia, serif",
                }}
              >
                ➕ Nova llicència
              </button>
            </div>
            <div
              style={{
                background: "#1e293b",
                borderRadius: 12,
                overflow: "hidden",
                border: "1px solid #334155",
              }}
            >
              <div style={{ overflowX: "auto" }}>
                <table
                  data-testid="licenses-table"
                  style={{ width: "100%", borderCollapse: "collapse", minWidth: 900 }}
                >
                  <thead>
                    <tr style={{ background: "#0f172a" }}>
                      <th style={th}>Install ID</th>
                      <th style={th}>Client</th>
                      <th style={th}>Email</th>
                      <th style={th}>Plan</th>
                      <th style={th}>Estat</th>
                      <th style={th}>Creada</th>
                      <th style={th}>Caduca</th>
                      <th style={th}>Verify #</th>
                      <th style={th}>Accions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredLicenses.length === 0 && (
                      <tr>
                        <td colSpan={9} style={{ ...td, textAlign: "center", color: "#64748b", padding: 32 }}>
                          {loading ? "Carregant…" : "Cap llicència"}
                        </td>
                      </tr>
                    )}
                    {filteredLicenses.map((l) => (
                      <tr key={l.id} data-testid={`license-row-${l.install_id}`}>
                        <td style={{ ...td, fontFamily: "'Courier New',monospace", fontSize: 12 }}>
                          {l.install_id}
                        </td>
                        <td style={td}>{l.client_name}</td>
                        <td style={{ ...td, color: "#94a3b8" }}>{l.client_email || "—"}</td>
                        <td style={td}>{l.plan}</td>
                        <td style={td}>{statusBadge(l.status)}</td>
                        <td style={{ ...td, color: "#94a3b8" }}>{fmtDate(l.created_at)}</td>
                        <td style={{ ...td, color: "#94a3b8" }}>
                          {l.expires_at ? fmtDate(l.expires_at) : "Perpètua"}
                        </td>
                        <td style={{ ...td, textAlign: "center" }}>{l.verify_count}</td>
                        <td style={td}>
                          <div style={{ display: "flex", gap: 6 }}>
                            <button
                              data-testid={`copy-jwt-${l.install_id}`}
                              onClick={() => handleCopyJwt(l.install_id)}
                              disabled={l.status !== "active"}
                              title="Copiar JWT"
                              style={actionBtnStyle(l.status !== "active")}
                            >
                              📋
                            </button>
                            <button
                              data-testid={`revoke-${l.install_id}`}
                              onClick={() => handleRevoke(l.install_id)}
                              disabled={l.status !== "active"}
                              title="Revocar"
                              style={{
                                ...actionBtnStyle(l.status !== "active"),
                                background: l.status !== "active" ? "#334155" : "#7f1d1d",
                                color: "#fff",
                              }}
                            >
                              🚫
                            </button>
                            <button
                              data-testid={`reset-hwid-${l.install_id}`}
                              onClick={() => handleResetHwid(l.install_id)}
                              disabled={l.status !== "active" || !l.hwid_lock}
                              title={l.hwid_lock
                                ? `Desbloquejar HWID (client ha canviat d'ordinador)\nHWID actual: ${l.hwid_lock}\nResets previs: ${l.hwid_reset_count || 0}`
                                : "Encara no hi ha HWID vinculat"}
                              style={{
                                ...actionBtnStyle(l.status !== "active" || !l.hwid_lock),
                                background: (l.status !== "active" || !l.hwid_lock) ? "#334155" : "#7c2d12",
                                color: "#fff",
                              }}
                            >
                              🔓
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
        {tab === "requests" && (
          <div
            style={{
              background: "#1e293b",
              borderRadius: 12,
              overflow: "hidden",
              border: "1px solid #334155",
            }}
          >
            <div style={{ overflowX: "auto" }}>
              <table
                data-testid="requests-table"
                style={{ width: "100%", borderCollapse: "collapse", minWidth: 900 }}
              >
                <thead>
                  <tr style={{ background: "#0f172a" }}>
                    <th style={th}>Data</th>
                    <th style={th}>Empresa</th>
                    <th style={th}>Contacte</th>
                    <th style={th}>Email</th>
                    <th style={th}>Install ID</th>
                    <th style={th}>Plan</th>
                    <th style={th}>Estat</th>
                    <th style={th}>Accions</th>
                  </tr>
                </thead>
                <tbody>
                  {requests.length === 0 && (
                    <tr>
                      <td colSpan={8} style={{ ...td, textAlign: "center", color: "#64748b", padding: 32 }}>
                        {loading ? "Carregant…" : "Cap sol·licitud"}
                      </td>
                    </tr>
                  )}
                  {requests.map((r) => (
                    <tr key={r.id} data-testid={`request-row-${r.id}`}>
                      <td style={{ ...td, color: "#94a3b8" }}>{fmtDate(r.created_at)}</td>
                      <td style={td}>{r.company_name}</td>
                      <td style={{ ...td, color: "#cbd5e1" }}>{r.contact_name || "—"}</td>
                      <td style={{ ...td, color: "#94a3b8" }}>{r.email}</td>
                      <td style={{ ...td, fontFamily: "'Courier New',monospace", fontSize: 11 }}>
                        {r.install_id}
                      </td>
                      <td style={td}>{r.plan_requested}</td>
                      <td style={td}>{statusBadge(r.status)}</td>
                      <td style={td}>
                        {r.status === "pending" ? (
                          <div style={{ display: "flex", gap: 6 }}>
                            <button
                              data-testid={`approve-${r.id}`}
                              onClick={() => handleApprove(r)}
                              style={{
                                ...actionBtnStyle(false),
                                background: "#065f46",
                                color: "#d1fae5",
                              }}
                            >
                              ✓ Aprovar
                            </button>
                            <button
                              data-testid={`reject-${r.id}`}
                              onClick={() => handleReject(r)}
                              style={{
                                ...actionBtnStyle(false),
                                background: "#7f1d1d",
                                color: "#fee2e2",
                              }}
                            >
                              ✗ Rebutjar
                            </button>
                          </div>
                        ) : (
                          <span style={{ color: "#64748b", fontSize: 11 }}>
                            {r.processed_at ? fmtDate(r.processed_at) : "—"}
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {tab === "stats" && <StatsPanel data={statsData} onRefresh={refresh} />}
      </div>

      <NewLicenseModal
        open={showNew}
        onClose={() => setShowNew(false)}
        onCreated={(lic) => {
          setKeyModal({ license: lic, email_sent: false, mailer_configured: undefined });
          refresh();
        }}
      />
      <LicenseKeyModal data={keyModal} onClose={() => setKeyModal(null)} />

      <footer
        style={{
          textAlign: "center",
          color: "#475569",
          padding: 20,
          fontSize: 11,
          borderTop: "1px solid #1e293b",
        }}
      >
        Created by Marc Brugulat Lopez · Portal de sol·licitud a{" "}
        <a
          href="/request-license"
          style={{ color: "#f5b301" }}
          data-testid="link-request-portal"
        >
          /request-license
        </a>
      </footer>
    </div>
  );
}

const actionBtnStyle = (disabled) => ({
  padding: "6px 12px",
  background: disabled ? "#334155" : "#1e293b",
  border: "1px solid #475569",
  borderRadius: 6,
  color: disabled ? "#64748b" : "#e2e8f0",
  cursor: disabled ? "not-allowed" : "pointer",
  fontSize: 12,
  fontFamily: "Georgia, serif",
});

const StatCard = ({ label, value, color, highlight }) => (
  <div
    style={{
      background: highlight
        ? "linear-gradient(135deg,#1e40af,#1e293b)"
        : "#1e293b",
      border: `1.5px solid ${highlight ? "#3b82f6" : "#334155"}`,
      borderRadius: 12,
      padding: "18px 20px",
      fontFamily: "Georgia, serif",
    }}
  >
    <div style={{ fontSize: 11, color: "#94a3b8", letterSpacing: 1.2, textTransform: "uppercase" }}>
      {label}
    </div>
    <div style={{ fontSize: 32, color, fontWeight: 700, marginTop: 4 }}>{value}</div>
  </div>
);

const TabBtn = ({ children, active, onClick, testid }) => (
  <button
    data-testid={testid}
    onClick={onClick}
    style={{
      padding: "14px 22px",
      background: "transparent",
      border: "none",
      borderBottom: active ? "3px solid #f5b301" : "3px solid transparent",
      color: active ? "#f5b301" : "#94a3b8",
      cursor: "pointer",
      fontFamily: "Georgia, serif",
      fontSize: 14,
      fontWeight: active ? 700 : 400,
      letterSpacing: 0.5,
    }}
  >
    {children}
  </button>
);

// =============================================================================
// StatsPanel — Panell d'estadístiques agregades
// =============================================================================
const StatsPanel = ({ data, onRefresh }) => {
  if (!data) {
    return (
      <div data-testid="stats-empty" style={{ padding: 40, textAlign: "center", color: "#94a3b8" }}>
        Carregant estadístiques…{" "}
        <button onClick={onRefresh} style={{ marginLeft: 12, padding: "6px 14px", background: "#1e293b", color: "#f5b301", border: "1px solid #f5b301", borderRadius: 6, cursor: "pointer" }}>Reintentar</button>
      </div>
    );
  }
  const { licenses, revenue, requests, activity, top_clients } = data;
  const eur = (n) => new Intl.NumberFormat("ca-ES", { style: "currency", currency: "EUR" }).format(n || 0);
  const pct = (n) => n == null ? "—" : `${Math.round(n * 100)}%`;

  return (
    <div data-testid="stats-panel" style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Ingressos projectats */}
      <section>
        <SectionTitle icon="💰" title="Ingressos projectats" subtitle="Estimació basada en llicències actives" />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 14 }}>
          <BigStat label="MRR" value={eur(revenue.mrr_eur)} hint="Ingressos mensuals recurrents" color="#22c55e" />
          <BigStat label="ARR" value={eur(revenue.arr_eur)} hint="Anualitzat (MRR × 12)" color="#3b82f6" />
          <BigStat label="Clients de pagament" value={Object.values(revenue.by_plan || {}).reduce((a, b) => a + (b.count || 0), 0)} hint="Actives STD + PREMIUM" color="#f5b301" />
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 10, marginTop: 12 }}>
          {Object.entries(revenue.by_plan || {}).map(([k, v]) => (
            <div key={k} style={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 10, padding: "12px 14px", fontFamily: "Georgia, serif" }}>
              <div style={{ fontSize: 11, color: "#94a3b8", letterSpacing: 1, textTransform: "uppercase" }}>{k.replace("_", " ")}</div>
              <div style={{ fontSize: 22, color: "#e2e8f0", fontWeight: 700, marginTop: 4 }}>{v.count} <span style={{ fontSize: 12, color: "#64748b" }}>clients</span></div>
              <div style={{ fontSize: 12, color: "#22c55e", marginTop: 4 }}>{eur(v.monthly_equiv)}/mes equiv.</div>
            </div>
          ))}
        </div>
      </section>

      {/* Llicències */}
      <section>
        <SectionTitle icon="🎫" title="Estat de llicències" />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 10 }}>
          <MiniStat label="Total" value={licenses.total} color="#e2e8f0" />
          <MiniStat label="Actives" value={licenses.active} color="#22c55e" />
          <MiniStat label="Revocades" value={licenses.revoked} color="#ef4444" />
          <MiniStat label="Expirades" value={licenses.expired} color="#f59e0b" />
          <MiniStat label="🔒 Amb HWID" value={licenses.with_hwid_lock} color="#a78bfa" hint={`${licenses.hwid_resets_total} resets totals`} />
          <MiniStat label="Verifies totals" value={licenses.verify_total} color="#38bdf8" />
        </div>
        <div style={{ marginTop: 10, display: "flex", gap: 8, flexWrap: "wrap" }}>
          {Object.entries(licenses.by_plan || {}).map(([plan, count]) => (
            <span key={plan} style={{ background: "#0f172a", border: "1px solid #334155", color: "#e2e8f0", padding: "6px 12px", borderRadius: 20, fontSize: 12, fontFamily: "Georgia, serif" }}>
              <b style={{ color: "#f5b301" }}>{plan}</b>: {count}
            </span>
          ))}
        </div>
      </section>

      {/* Sol·licituds + activitat */}
      <section style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div>
          <SectionTitle icon="📮" title="Sol·licituds" />
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <MiniStat label="Total" value={requests.total} color="#e2e8f0" />
            <MiniStat label="Pendents" value={requests.pending} color={requests.pending > 0 ? "#3b82f6" : "#64748b"} />
            <MiniStat label="Aprovades" value={requests.approved} color="#22c55e" />
            <MiniStat label="Rebutjades" value={requests.rejected} color="#ef4444" />
          </div>
          <div style={{ marginTop: 10, background: "#0f172a", border: "1px solid #334155", borderRadius: 8, padding: 12 }}>
            <div style={{ fontSize: 11, color: "#94a3b8", letterSpacing: 1, textTransform: "uppercase" }}>Taxa de conversió</div>
            <div style={{ fontSize: 26, color: "#22c55e", fontWeight: 700, marginTop: 4 }}>{pct(requests.conversion_rate)}</div>
            <div style={{ fontSize: 11, color: "#64748b", marginTop: 2 }}>aprovades / (aprovades + rebutjades)</div>
          </div>
        </div>
        <div>
          <SectionTitle icon="📈" title="Activitat" />
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <MiniStat label="Noves (7 dies)" value={activity.new_last_7d} color="#f5b301" />
            <MiniStat label="Noves (30 dies)" value={activity.new_last_30d} color="#f5b301" />
          </div>
        </div>
      </section>

      {/* Top clients */}
      {top_clients && top_clients.length > 0 && (
        <section>
          <SectionTitle icon="🏆" title="Top clients per verificacions" subtitle="Els més actius (útil per detectar comportaments anòmals)" />
          <div style={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 10, overflow: "hidden" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13, fontFamily: "Georgia, serif" }}>
              <thead>
                <tr style={{ background: "#1e293b" }}>
                  <th style={{ padding: 10, textAlign: "left", color: "#f5b301", fontSize: 11, letterSpacing: 1 }}>#</th>
                  <th style={{ padding: 10, textAlign: "left", color: "#f5b301", fontSize: 11, letterSpacing: 1 }}>Client</th>
                  <th style={{ padding: 10, textAlign: "left", color: "#f5b301", fontSize: 11, letterSpacing: 1 }}>Install ID</th>
                  <th style={{ padding: 10, textAlign: "left", color: "#f5b301", fontSize: 11, letterSpacing: 1 }}>Plan</th>
                  <th style={{ padding: 10, textAlign: "right", color: "#f5b301", fontSize: 11, letterSpacing: 1 }}>Verifies</th>
                </tr>
              </thead>
              <tbody>
                {top_clients.map((c, i) => (
                  <tr key={c.install_id} style={{ borderTop: "1px solid #1e293b" }}>
                    <td style={{ padding: 10, color: "#94a3b8" }}>{i + 1}</td>
                    <td style={{ padding: 10, color: "#e2e8f0" }}>{c.client_name || "—"}</td>
                    <td style={{ padding: 10, color: "#94a3b8", fontFamily: "'Courier New', monospace", fontSize: 12 }}>{c.install_id}</td>
                    <td style={{ padding: 10, color: "#f5b301" }}>{c.plan}</td>
                    <td style={{ padding: 10, color: "#22c55e", textAlign: "right", fontWeight: 700 }}>{c.verify_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <div style={{ textAlign: "center", color: "#475569", fontSize: 11, paddingTop: 6 }}>
        Generat: {new Date(data.generated_at).toLocaleString("ca-ES")}
      </div>
    </div>
  );
};

const SectionTitle = ({ icon, title, subtitle }) => (
  <div style={{ marginBottom: 10 }}>
    <div style={{ color: "#f5b301", fontSize: 16, fontFamily: "Georgia, serif", fontWeight: 700 }}>
      {icon} {title}
    </div>
    {subtitle && <div style={{ color: "#64748b", fontSize: 12, marginTop: 2 }}>{subtitle}</div>}
  </div>
);

const BigStat = ({ label, value, hint, color }) => (
  <div style={{ background: "linear-gradient(135deg,#1e293b 0%,#0f172a 100%)", border: `1.5px solid ${color}55`, borderRadius: 14, padding: "18px 22px", fontFamily: "Georgia, serif", boxShadow: `0 4px 18px ${color}18` }}>
    <div style={{ fontSize: 11, color: "#94a3b8", letterSpacing: 1.2, textTransform: "uppercase" }}>{label}</div>
    <div style={{ fontSize: 30, color, fontWeight: 700, marginTop: 6 }}>{value}</div>
    {hint && <div style={{ fontSize: 11, color: "#64748b", marginTop: 4 }}>{hint}</div>}
  </div>
);

const MiniStat = ({ label, value, color, hint }) => (
  <div style={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 10, padding: "12px 14px", fontFamily: "Georgia, serif" }}>
    <div style={{ fontSize: 10, color: "#94a3b8", letterSpacing: 1.2, textTransform: "uppercase" }}>{label}</div>
    <div style={{ fontSize: 22, color, fontWeight: 700, marginTop: 4 }}>{value}</div>
    {hint && <div style={{ fontSize: 10, color: "#64748b", marginTop: 2 }}>{hint}</div>}
  </div>
);
