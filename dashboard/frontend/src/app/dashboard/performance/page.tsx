"use client";
import useSWR from "swr";
import { performanceApi } from "@/lib/api";
import { Zap } from "lucide-react";

const fetcher = () => performanceApi.summary().then(r => r.data);

export default function PerformancePage() {
  const { data, isLoading } = useSWR("perf-summary", fetcher);

  if (isLoading) {
    return (
      <div style={{ padding: "2rem 0" }}>
        <div className="loading-bar" style={{ marginBottom: 24, width: "100%" }} />
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-muted)", letterSpacing: "0.1em" }}>
          LOADING PERFORMANCE DATA…
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-8)" }} className="animate-in">
      
      <div className="page-header">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
          <div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 6 }}>
              Module 04 — Infrastructure
            </div>
            <h1 className="page-title">Performance Intelligence</h1>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.08em" }}>
              RECORDS PROCESSED
            </div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 14, color: "var(--text-primary)", fontWeight: 600 }}>
              {String(data?.length ?? 0).padStart(3, "0")}
            </div>
          </div>
        </div>
      </div>

      <div className="kpi-grid animate-in-children">
        {(data ?? []).map((d: any, i: number) => {
          const score = parseFloat(d.avg_score) * 100 || 0;
          const color = score >= 75 ? "var(--success)" : score >= 50 ? "var(--warning)" : "var(--danger)";
          return (
            <div key={i} className="card" style={{ position: "relative" }}>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", marginBottom: 12, letterSpacing: "0.06em", textTransform: "uppercase" }}>
                {d.domain}
              </div>
              <div className="stat-value" style={{ color }}>{score.toFixed(1)}</div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-secondary)", marginTop: 12, display: "flex", justifyContent: "space-between" }}>
                <span>{d.total_pages} PGS</span>
                <span>B:{(parseFloat(d.best_page_score) * 100).toFixed(0)} W:{(parseFloat(d.worst_page_score) * 100).toFixed(0)}</span>
              </div>
            </div>
          );
        })}
        {!data?.length && (
          <div className="card" style={{ gridColumn: "1/-1", textAlign: "center", color: "var(--text-muted)", padding: "2rem", fontFamily: "var(--font-mono)", fontSize: 11 }}>
            NO PERFORMANCE DATA. AWAITING CRAWL RESULTS.
          </div>
        )}
      </div>

      {data?.length > 0 && (
        <div className="card" style={{ padding: 0, overflow: "hidden", border: "1px solid var(--border)" }}>
          <table className="table" style={{ margin: 0 }}>
            <thead>
              <tr>
                <th>DOMAIN</th>
                <th style={{ textAlign: "right" }}>PAGES</th>
                <th style={{ textAlign: "right" }}>AVG_SCORE</th>
                <th style={{ textAlign: "right" }}>MEDIAN</th>
                <th style={{ textAlign: "right", color: "var(--success)" }}>BEST</th>
                <th style={{ textAlign: "right", color: "var(--danger)" }}>WORST</th>
              </tr>
            </thead>
            <tbody>
              {(data ?? []).map((d: any, i: number) => {
                const avg = parseFloat(d.avg_score) * 100 || 0;
                const color = avg >= 75 ? "var(--success)" : avg >= 50 ? "var(--warning)" : "var(--danger)";
                return (
                  <tr key={i}>
                    <td style={{ fontWeight: 600, color: "var(--text-primary)" }}>{d.domain}</td>
                    <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>{d.total_pages}</td>
                    <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontWeight: 700, color }}>{avg.toFixed(1)}</td>
                    <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>{(parseFloat(d.median_score) * 100).toFixed(1)}</td>
                    <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--success)" }}>{(parseFloat(d.best_page_score) * 100).toFixed(1)}</td>
                    <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--danger)" }}>{(parseFloat(d.worst_page_score) * 100).toFixed(1)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
