"use client";
import useSWR from "swr";
import { analyticsApi } from "@/lib/api";
import { Globe, FileText, ShoppingBag, Activity, AlertTriangle, TrendingUp } from "lucide-react";

const fetcher = () => analyticsApi.overview().then(r => r.data);

function KpiCard({
  code,
  label,
  value,
  icon: Icon,
  accentColor = "var(--accent)",
}: {
  code: string;
  label: string;
  value: string | number;
  icon: React.ElementType;
  accentColor?: string;
}) {
  return (
    <div className="card" style={{ position: "relative" }}>
      {/* Module code — top-right corner */}
      <span style={{
        position: "absolute", top: 12, right: 14,
        fontFamily: "var(--font-mono)", fontSize: 10,
        color: "var(--text-muted)", letterSpacing: "0.08em",
      }}>
        {code}
      </span>

      <div className="stat-accent-icon">
        <Icon size={12} color={accentColor} strokeWidth={2} />
      </div>

      <div className="stat-label">{label}</div>
      <div className="stat-value">{value ?? "—"}</div>
    </div>
  );
}

function ScoreRow({ label, value }: { label: string; value: number | null }) {
  const pct = value ?? 0;
  const color = pct >= 75 ? "var(--success)" : pct >= 50 ? "var(--warning)" : "var(--danger)";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>{label}</span>
        <span style={{
          fontFamily: "var(--font-mono)", fontSize: 14,
          fontWeight: 600, color,
        }}>
          {pct ? pct.toFixed(1) : "—"}
        </span>
      </div>
      <div className="score-bar-track">
        <div className="score-bar-fill" style={{
          width: `${Math.min(pct, 100)}%`,
          background: color,
        }} />
      </div>
    </div>
  );
}

export default function OverviewPage() {
  const { data, error, isLoading } = useSWR("overview", fetcher, { refreshInterval: 30000 });

  if (isLoading) {
    return (
      <div style={{ padding: "2rem 0" }}>
        <div className="loading-bar" style={{ marginBottom: 24, width: "100%" }} />
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-muted)", letterSpacing: "0.1em" }}>
          LOADING OVERVIEW…
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--danger)", padding: "2rem 0", letterSpacing: "0.06em" }}>
        ERR — FAILED TO LOAD OVERVIEW
      </div>
    );
  }

  const k = data?.kpis ?? {};
  const s = data?.score_overview ?? {};
  const issues = data?.critical_issues ?? [];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-8)" }} className="animate-in">

      {/* Page header */}
      <div className="page-header">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
          <div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 6 }}>
              Module 01 — Overview
            </div>
            <h1 className="page-title">Command Center</h1>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.08em" }}>
              AUTO-REFRESH 30s
            </div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--accent)", letterSpacing: "0.08em" }}>
              ● LIVE
            </div>
          </div>
        </div>
      </div>

      {/* KPI Grid — cells share borders for a dense data-terminal feel */}
      <div className="kpi-grid animate-in-children">
        <KpiCard code="K/01" icon={Globe}         label="Competitors"     value={k.competitors_total ?? 0} accentColor="var(--accent)" />
        <KpiCard code="K/02" icon={FileText}       label="Pages Crawled"  value={k.pages_total ?? 0}       accentColor="var(--info)" />
        <KpiCard code="K/03" icon={ShoppingBag}    label="Products"       value={k.products_total ?? 0}     accentColor="var(--warning)" />
        <KpiCard code="K/04" icon={Activity}       label="Active Jobs"    value={k.jobs_active ?? 0}        accentColor="var(--success)" />
        <KpiCard code="K/05" icon={AlertTriangle}  label="Failed Jobs"    value={k.jobs_failed ?? 0}        accentColor="var(--danger)" />
        <KpiCard code="K/06" icon={TrendingUp}     label="Completed Jobs" value={k.jobs_completed ?? 0}     accentColor="var(--info)" />
      </div>

      {/* Score Overview */}
      <div className="card">
        <div className="card-title">Score Overview — All Competitors</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: "var(--sp-5)" }}>
          <ScoreRow label="Avg SEO Score"         value={s.seo} />
          <ScoreRow label="Avg Performance Score" value={s.performance ? s.performance * 100 : null} />
          <ScoreRow label="Avg Social Score"      value={s.social ? s.social * 100 : null} />
          <ScoreRow label="Avg Market Score"      value={s.market} />
        </div>
      </div>

      {/* Critical Issues */}
      {issues.length > 0 && (
        <div className="card">
          <div className="card-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <AlertTriangle size={11} color="var(--danger)" />
            Critical SEO Issues
            <span style={{ marginLeft: "auto", fontFamily: "var(--font-mono)", color: "var(--danger)" }}>
              {issues.length}
            </span>
          </div>
          <div className="table-container">
            <table className="table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Issue</th>
                  <th>Competitor</th>
                  <th style={{ textAlign: "right" }}>Pages Affected</th>
                </tr>
              </thead>
              <tbody>
                {issues.slice(0, 8).map((i: any, idx: number) => (
                  <tr key={idx}>
                    <td style={{ fontFamily: "var(--font-mono)", color: "var(--text-muted)", fontSize: 11 }}>
                      {String(idx + 1).padStart(2, "0")}
                    </td>
                    <td style={{ color: "var(--text-primary)", maxWidth: 320, whiteSpace: "normal" }}>{i.issue}</td>
                    <td>
                      <span className="badge badge-amber">{i.competitor_id}</span>
                    </td>
                    <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--danger)", fontWeight: 600, fontSize: 13 }}>
                      {i.total_affected_pages}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
