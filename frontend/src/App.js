import { useEffect } from "react";
import "@/App.css";

function App() {
  useEffect(() => {
    window.location.replace("/caja_del_dia.html");
  }, []);
  return (
    <div data-testid="redirect-page" style={{
      minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
      background: "#0f1115", color: "#e8ecf2", fontFamily: "Inter, sans-serif"
    }}>
      <div style={{ textAlign: "center" }}>
        <h1 style={{ margin: 0, fontSize: 22 }}>Caja del Día</h1>
        <p style={{ color: "#9aa3b2" }}>Abriendo aplicación...</p>
        <a data-testid="open-app-link" href="/caja_del_dia.html"
           style={{ color: "#f5b301", textDecoration: "underline" }}>
          Abrir manualmente
        </a>
      </div>
    </div>
  );
}

export default App;
