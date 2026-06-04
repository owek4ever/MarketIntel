"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { Sidebar } from "@/components/Sidebar";
import { Chatbox } from "@/components/Chatbox";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.push("/login");
  }, [user, loading, router]);

  if (loading) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 16 }}>
        <div className="loading-bar" style={{ width: 200 }} />
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-muted)", letterSpacing: "0.12em", textTransform: "uppercase" }}>
          Authenticating…
        </div>
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="shell">
      <Sidebar />
      <main className="main-content">{children}</main>
      <Chatbox />
    </div>
  );
}
