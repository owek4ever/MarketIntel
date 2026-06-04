"use client";
import useSWR from "swr";
import { socialApi } from "@/lib/api";
import { Share2 } from "lucide-react";

const fetcher = () => socialApi.summary().then(r => r.data);

const PLATFORM_COLORS: Record<string, string> = {
  facebook: "var(--info)", instagram: "#ec4899", tiktok: "var(--success)",
};

export default function SocialPage() {
  const { data, isLoading } = useSWR("social-summary", fetcher);

  if (isLoading) {
    return (
      <div style={{ padding: "2rem 0" }}>
        <div className="loading-bar" style={{ marginBottom: 24, width: "100%" }} />
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-muted)", letterSpacing: "0.1em" }}>
          LOADING SOCIAL METRICS…
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
              Module 05 — Audience
            </div>
            <h1 className="page-title">Social Media Intelligence</h1>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.08em" }}>
              ACCOUNTS TRACKED
            </div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 14, color: "var(--text-primary)", fontWeight: 600 }}>
              {String(data?.length ?? 0).padStart(3, "0")}
            </div>
          </div>
        </div>
      </div>

      <div className="kpi-grid animate-in-children">
        {(data ?? []).map((d: any, i: number) => {
          const score = parseFloat(d.score) || 0;
          const color = PLATFORM_COLORS[d.platform] ?? "var(--text-secondary)";
          return (
            <div key={i} className="card">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                <span className="badge" style={{ background: "transparent", color, border: `1px solid ${color}` }}>
                  {d.platform}
                </span>
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)" }}>ID:{String(d.competitor_id).padStart(2, "0")}</span>
              </div>
              <div className="stat-value" style={{ fontSize: 24, color: "var(--text-primary)" }}>{(score * 100).toFixed(2)}%</div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-secondary)", marginTop: 12, display: "flex", justifyContent: "space-between" }}>
                <span>{d.posts_per_month?.toFixed(1) ?? "0"} P/MO</span>
                <span>{d.avg_likes_per_post?.toFixed(0) ?? "0"} LIKES</span>
              </div>
            </div>
          );
        })}
        {!data?.length && (
          <div className="card" style={{ gridColumn: "1/-1", textAlign: "center", color: "var(--text-muted)", padding: "2rem", fontFamily: "var(--font-mono)", fontSize: 11 }}>
            NO SOCIAL ACCOUNTS TRACKED YET.
          </div>
        )}
      </div>

      {data?.length > 0 && (
        <div className="card" style={{ padding: 0, overflow: "hidden", border: "1px solid var(--border)" }}>
          <table className="table" style={{ margin: 0 }}>
            <thead>
              <tr>
                <th>COMPETITOR</th>
                <th>PLATFORM</th>
                <th style={{ textAlign: "right" }}>SCORE</th>
                <th style={{ textAlign: "right" }}>POSTS/MO</th>
                <th style={{ textAlign: "right" }}>AVG_LIKES</th>
                <th style={{ textAlign: "right" }}>AVG_COMMENTS</th>
                <th style={{ textAlign: "right" }}>ENGAGE/1K</th>
              </tr>
            </thead>
            <tbody>
              {(data ?? []).map((d: any, i: number) => {
                const color = PLATFORM_COLORS[d.platform] ?? "var(--text-secondary)";
                return (
                  <tr key={i}>
                    <td style={{ fontWeight: 600, color: "var(--text-primary)" }}>#{String(d.competitor_id).padStart(2, "0")}</td>
                    <td>
                      <span className="badge" style={{ background: "transparent", color, border: `1px solid ${color}` }}>{d.platform}</span>
                    </td>
                    <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontWeight: 700, color: "var(--accent)" }}>{(parseFloat(d.score) * 100).toFixed(3)}%</td>
                    <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>{d.posts_per_month?.toFixed(1) ?? "—"}</td>
                    <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>{d.avg_likes_per_post?.toFixed(0) ?? "—"}</td>
                    <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>{d.avg_comments_per_post?.toFixed(0) ?? "—"}</td>
                    <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>{d.engagement_per_1k_followers?.toFixed(2) ?? "—"}</td>
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
