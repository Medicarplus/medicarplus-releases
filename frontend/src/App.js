import { BrowserRouter, Route, Routes } from "react-router-dom";
import "@/App.css";
import AdminPage from "@/pages/AdminPage";
import RequestLicensePage from "@/pages/RequestLicensePage";
import PrivacyPage from "@/pages/PrivacyPage";
import LandingPage from "@/pages/LandingPage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/admin" element={<AdminPage />} />
        <Route path="/request-license" element={<RequestLicensePage />} />
        <Route path="/privacy" element={<PrivacyPage />} />
        <Route path="*" element={<LandingPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
