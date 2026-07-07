import { useEffect } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import "@/App.css";
import AdminPage from "@/pages/AdminPage";
import RequestLicensePage from "@/pages/RequestLicensePage";
import PrivacyPage from "@/pages/PrivacyPage";

function LegacyRedirect() {
  useEffect(() => {
    window.location.replace("/caja_del_dia.html");
  }, []);
  return (
    <div
      data-testid="redirect-page"
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#0f1115",
        color: "#e8ecf2",
        fontFamily: "Inter, sans-serif",
      }}
    >
      <div style={{ textAlign: "center" }}>
        <h1 style={{ margin: 0, fontSize: 22 }}>Caja del Día</h1>
        <p style={{ color: "#9aa3b2" }}>Abriendo aplicación...</p>
        <a
          data-testid="open-app-link"
          href="/caja_del_dia.html"
          style={{ color: "#f5b301", textDecoration: "underline" }}
        >
          Abrir manualmente
        </a>
      </div>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/admin" element={<AdminPage />} />
        <Route path="/request-license" element={<RequestLicensePage />} />
        <Route path="/privacy" element={<PrivacyPage />} />
        <Route path="*" element={<LegacyRedirect />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
