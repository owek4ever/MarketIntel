"use client";
import useSWR from "swr";
import { competitorsApi } from "@/lib/api";
import Link from "next/link";
import { Globe, ChevronRight } from "lucide-react";

const fetcher = () => competitorsApi.list().then(r => r.data);

function ScoreBar({ value }: { value: number | null }) {
  const v = value ?? 0;
  const color = v >= 75 ? "var(--success)" : v >= 50 ? "var(--warning)" : "var(--danger)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div className="score-bar-track" style={{ flex: 1, marginTop: 0 }}>
        <div className="score-bar-fill" style={{ width: `${Math.min(v, 100)}%`, background: color }} />
      </div>
      <span style={{ fontFamily: "var(--font-mono)", fontSize: 13, color, fontWeight: 600, width: 32, textAlign: "right" }}>
        {v ? v.toFixed(0) : "—"}
      </span>
    </div>
  );
}

export default function CompetitorsPage() {
  const { data, isLoading, error } = useSWR("competitors", fetcher);

  if (isLoading) {
    return (
      <div style={{ padding: "2rem 0" }}>
        <div className="loading-bar" style={{ marginBottom: 24, width: "100%" }} />
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-muted)", letterSpacing: "0.1em" }}>
          LOADING COMPETITOR DB…
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--danger)", padding: "2rem 0", letterSpacing: "0.06em" }}>
        ERR — FAILED TO LOAD COMPETITORS
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-8)" }} className="animate-in">

      <div className="page-header">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
          <div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 6 }}>
              Module 02 — Entities
            </div>
            <h1 className="page-title">Competitor Database</h1>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.08em" }}>
              TRACKED DOMAINS
            </div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 14, color: "var(--text-primary)", fontWeight: 600 }}>
              {String(data?.length ?? 0).padStart(3, "0")}
            </div>
          </div>
        </div>
      </div>

      <div className="card" style={{ padding: 0, overflow: "hidden", border: "1px solid var(--border)" }}>
        <table className="table" style={{ margin: 0 }}>
          <thead>
            <tr>
              <th>Domain</th>
              <th style={{ textAlign: "right" }}>Pages</th>
              <th style={{ textAlign: "right" }}>Products</th>
              <th style={{ minWidth: 120 }}>SEO Index</th>
              <th style={{ minWidth: 120 }}>Perf Index</th>
              <th style={{ minWidth: 120 }}>Social Index</th>
              <th style={{ minWidth: 120 }}>Market Index</th>
              <th style={{ width: 40 }}></th>
            </tr>
          </thead>
          <tbody>
            {(data ?? []).map((c: any) => (
              <tr key={c.id}>
                <td>
                  <div style={{ fontWeight: 600, color: "var(--text-primary)" }}>{c.domain}</div>
                  {c.name && <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>{c.name}</div>}
                </td>
                <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>
                  {c.page_count ?? 0}
                </td>
                <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>
                  {c.product_count ?? 0}
                </td>
                <td><ScoreBar value={c.seo_score} /></td>
                <td><ScoreBar value={c.perf_score ? c.perf_score * 100 : null} /></td>
                <td><ScoreBar value={c.social_score ? c.social_score * 100 : null} /></td>
                <td><ScoreBar value={c.market_score} /></td>
                <td style={{ textAlign: "center" }}>
                  <Link href={`/dashboard/competitors/${c.id}`} style={{ color: "var(--text-muted)" }}>
                    <ChevronRight size={14} />
                  </Link>
                </td>
              </tr>
            ))}
            {data?.length === 0 && (
              <tr>
                <td colSpan={8} style={{ textAlign: "center", color: "var(--text-muted)", padding: "2rem", fontFamily: "var(--font-mono)", fontSize: 11 }}>
                  NO ENTITIES FOUND. ADD URLS VIA CRAWL CONTROL.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
