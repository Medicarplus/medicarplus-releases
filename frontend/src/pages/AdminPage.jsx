import { useState } from "react";
import { Toaster } from "@/components/ui/sonner";
import AdminLogin from "@/components/admin/AdminLogin";
import AdminDashboard from "@/components/admin/AdminDashboard";
import { AdminTokenStore } from "@/lib/licenseApi";

export default function AdminPage() {
  const [authed, setAuthed] = useState(!!AdminTokenStore.get());
  return (
    <>
      {authed ? (
        <AdminDashboard onLogout={() => setAuthed(false)} />
      ) : (
        <AdminLogin onLogin={() => setAuthed(true)} />
      )}
      <Toaster position="top-right" richColors closeButton theme="dark" />
    </>
  );
}
