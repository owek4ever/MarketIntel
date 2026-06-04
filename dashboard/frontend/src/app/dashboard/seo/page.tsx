"use client";
import useSWR from "swr";
import { seoApi } from "@/lib/api";
import { TrendingUp, AlertTriangle } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

const fetchSummary = () => seoApi.summary().then(r => r.data);

const COLORS = ["var(--accent)", "var(--info)", "var(--warning)", "var(--success)", "#a855f7", "#ec4899", "#ef4444"];

export default function SeoPage() {
  const { data, isLoading } = useSWR("seo-summary", fetchSummary);

  if (isLoading) {
    return (
      <div style={{ padding: "2rem 0" }}>
        <div className="loading-bar" style={{ marginBottom: 24, width: "100%" }} />
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-muted)", letterSpacing: "0.1em" }}>
          LOADING SEO INTELLIGENCE…
        </div>
      </div>
    );
  }

  const chart = (data ?? []).map((d: any, i: number) => ({
    domain: d.domain?.split(".")[0] ?? `#${d.competitor_id}`,
    seo: parseFloat(d.avg_seo_score) || 0,
    content: parseFloat(d.avg_content_score) || 0,
    onpage: parseFloat(d.avg_on_page_score) || 0,
    technical: parseFloat(d.avg_technical_score) || 0,
    ux: parseFloat(d.avg_ux_score) || 0,
    color: COLORS[i % COLORS.length],
  }));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-8)" }} className="animate-in">

      <div className="page-header">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
          <div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 6 }}>
              Module 03 — Analysis
            </div>
            <h1 className="page-title">SEO Intelligence</h1>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.08em" }}>
              DOMAINS ANALYZED
            </div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 14, color: "var(--text-primary)", fontWeight: 600 }}>
              {String(data?.length ?? 0).padStart(3, "0")}
            </div>
          </div>
        </div>
      </div>

      {chart.length > 0 && (
        <div className="card" style={{ border: "1px solid var(--border)" }}>
          <div className="card-title">OVERALL SEO SCORE RANKING</div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={chart} margin={{ top: 0, right: 16, left: -10, bottom: 0 }}>
              <XAxis dataKey="domain" tick={{ fill: "var(--text-muted)", fontSize: 10, fontFamily: "var(--font-mono)" }} axisLine={false} tickLine={false} />
              <YAxis domain={[0, 100]} tick={{ fill: "var(--text-muted)", fontSize: 10, fontFamily: "var(--font-mono)" }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ background: "var(--bg-surface)", border: "1px solid var(--border-bright)", borderRadius: 0, fontFamily: "var(--font-mono)", fontSize: 11 }}
                labelStyle={{ color: "var(--text-primary)", marginBottom: 4 }}
                itemStyle={{ color: "var(--accent)" }}
                cursor={{ fill: "var(--bg-hover)" }}
              />
              <Bar dataKey="seo" radius={0} name="SEO_SCORE">
                {chart.map((e: any, i: number) => <Cell key={i} fill={e.color} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="card" style={{ padding: 0, overflow: "hidden", border: "1px solid var(--border)" }}>
        <table className="table" style={{ margin: 0 }}>
          <thead>
            <tr>
              <th>DOMAIN</th>
              <th style={{ textAlign: "right" }}>PAGES</th>
              <th style={{ textAlign: "right" }}>OVERALL</th>
              <th style={{ textAlign: "right" }}>CONTENT</th>
              <th style={{ textAlign: "right" }}>ON-PAGE</th>
              <th style={{ textAlign: "right" }}>TECHNICAL</th>
              <th style={{ textAlign: "right" }}>UX</th>
              <th style={{ textAlign: "right" }}>STD_DEV</th>
            </tr>
          </thead>
          <tbody>
            {(data ?? []).map((d: any, i: number) => {
              const score = parseFloat(d.avg_seo_score) || 0;
              const color = score >= 75 ? "var(--success)" : score >= 50 ? "var(--warning)" : "var(--danger)";
              return (
                <tr key={d.competitor_id}>
                  <td style={{ fontWeight: 600, color: "var(--text-primary)" }}>{d.domain}</td>
                  <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>{d.total_pages}</td>
                  <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", color, fontWeight: 700 }}>{score.toFixed(1)}</td>
                  <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>{parseFloat(d.avg_content_score)?.toFixed(1) ?? "—"}</td>
                  <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>{parseFloat(d.avg_on_page_score)?.toFixed(1) ?? "—"}</td>
                  <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>{parseFloat(d.avg_technical_score)?.toFixed(1) ?? "—"}</td>
                  <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>{parseFloat(d.avg_ux_score)?.toFixed(1) ?? "—"}</td>
                  <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>{parseFloat(d.seo_stddev)?.toFixed(1) ?? "—"}</td>
                </tr>
              );
            })}
            {!data?.length && (
              <tr>
                <td colSpan={8} style={{ textAlign: "center", color: "var(--text-muted)", padding: "2rem", fontFamily: "var(--font-mono)", fontSize: 11 }}>
                  NO SEO DATA. AWAITING CRAWL RESULTS.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
