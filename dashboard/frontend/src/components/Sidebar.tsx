"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  BarChart2, Globe, TrendingUp, Zap, Share2,
  ShoppingBag, Activity, LogOut, FileText, Brain,
} from "lucide-react";

const NAV = [
  { href: "/dashboard",              icon: BarChart2,   label: "Overview",          code: "01" },
  { href: "/dashboard/competitors",  icon: Globe,        label: "Competitors",        code: "02" },
  { href: "/dashboard/seo",          icon: TrendingUp,   label: "SEO",                code: "03" },
  { href: "/dashboard/performance",  icon: Zap,          label: "Performance",        code: "04" },
  { href: "/dashboard/social",       icon: Share2,       label: "Social Media",       code: "05" },
  { href: "/dashboard/market",       icon: ShoppingBag,  label: "Market",             code: "06" },
  { href: "/dashboard/crawl",        icon: Activity,     label: "Crawl Control",      code: "07" },
  { href: "/dashboard/reports",      icon: FileText,     label: "Reports",            code: "08" },
  { href: "/dashboard/council",      icon: Brain,        label: "Council",            code: "09" },
];

export function Sidebar() {
  const path = usePathname();
  const { user, logout } = useAuth();

  return (
    <aside className="sidebar">
      {/* Brand */}
      <div className="sidebar-brand">
        <div className="sidebar-brand-icon">
          <BarChart2 size={14} color="#000" strokeWidth={2.5} />
        </div>
        <div>
          <div className="sidebar-brand-name">PFE2</div>
          <div className="sidebar-brand-sub">Intel Ops</div>
        </div>
      </div>

      {/* Nav label */}
      <div className="sidebar-section-label" style={{ marginBottom: 4 }}>
        Modules
      </div>

      <nav className="sidebar-nav">
        {NAV.map(({ href, icon: Icon, label, code }) => {
          const active = path === href;
          return (
            <Link
              key={href}
              href={href}
              className={`sidebar-item${active ? " active" : ""}`}
            >
              <span style={{
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                color: active ? "var(--accent)" : "var(--text-muted)",
                width: 18,
                flexShrink: 0,
              }}>
                {code}
              </span>
              <Icon size={14} strokeWidth={active ? 2.5 : 1.5} />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* User footer */}
      <div className="sidebar-footer">
        <div className="sidebar-user">
          <div className="sidebar-user-email">{user?.email}</div>
          <div className="sidebar-user-role">{user?.role ?? "analyst"}</div>
        </div>
        <button
          className="sidebar-item btn-danger"
          style={{ width: "100%", border: "none", background: "transparent", textAlign: "left" }}
          onClick={logout}
        >
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, width: 18, color: "var(--text-muted)" }}>—</span>
          <LogOut size={14} strokeWidth={1.5} />
          Sign out
        </button>
      </div>
    </aside>
  );
}
