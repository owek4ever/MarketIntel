"use client";
import useSWR from "swr";
import { analyticsApi, competitorsApi, socialApi, marketApi, crawlApi } from "@/lib/api";
import {
  Globe, FileText, ShoppingBag, Activity, AlertTriangle, TrendingUp,
  Users, BarChart3, Share2, Zap, Clock, CheckCircle, XCircle,
  ChevronRight, ArrowUpRight, ArrowDownRight, Minus,
} from "lucide-react";
import Link from "next/link";

const fetcher = (url: string) => {
  const map: Record<string, () => Promise<any>> = {
    overview: () => analyticsApi.overview().then(r => r.data),
    competitors: () => competitorsApi.list().then(r => r.data),
    social: () => socialApi.summary().then(r => r.data),
    market: () => marketApi.scores().then(r => r.data),
    crawlStats: () => crawlApi.stats().then(r => r.data),
    aggStats: () => crawlApi.statsAggregate().then(r => r.data),
  };
  return map[url]();
};

function KpiCard({
  code, label, value, icon: Icon, accentColor, sub, link,
}: {
  code: string; label: string; value: string | number; icon: React.ElementType;
  accentColor: string; sub?: string; link?: string;
}) {
  const inner = (
    <div className="card" style={{ position: "relative", cursor: link ? "pointer" : undefined, transition: "border-color 0.2s" }}>
      <span style={{ position: "absolute", top: 12, right: 14, fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.08em" }}>{code}</span>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
        <div>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 4 }}>{label}</div>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 28, fontWeight: 700, color: "var(--text-primary)", lineHeight: 1.1 }}>{typeof value === "number" ? value.toLocaleString() : value ?? "—"}</div>
          {sub && <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", marginTop: 4 }}>{sub}</div>}
        </div>
        <div style={{ width: 36, height: 36, borderRadius: 8, background: `color-mix(in srgb, ${accentColor} 12%, transparent)`, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
          <Icon size={16} style={{ color: accentColor }} />
        </div>
      </div>
      {link && <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: 2, background: accentColor, opacity: 0.4, borderRadius: "0 0 8px 8px" }} />}
    </div>
  );
  return link ? <Link href={link} style={{ textDecoration: "none" }}>{inner}</Link> : inner;
}

function MiniBar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  return (
    <div style={{ width: "100%", height: 4, background: "var(--border)", borderRadius: 2, overflow: "hidden" }}>
      <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 2 }} />
    </div>
  );
}

function ScoreRing({ label, value, color }: { label: string; value: number | null; color: string }) {
  const pct = value ?? 0;
  const r = 28;
  const circ = 2 * Math.PI * r;
  const offset = circ - (pct / 100) * circ;
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
      <svg width={68} height={68} viewBox="0 0 68 68">
        <circle cx={34} cy={34} r={r} fill="none" stroke="var(--border)" strokeWidth={5} />
        <circle cx={34} cy={34} r={r} fill="none" stroke={color} strokeWidth={5}
          strokeDasharray={circ} strokeDashoffset={offset}
          strokeLinecap="round" transform="rotate(-90 34 34)"
          style={{ transition: "stroke-dashoffset 1s ease" }} />
        <text x={34} y={34} textAnchor="middle" dominantBaseline="central"
          style={{ fontFamily: "var(--font-mono)", fontSize: 13, fontWeight: 700, fill: "var(--text-primary)" }}>
          {pct ? pct.toFixed(0) : "—"}
        </text>
      </svg>
      <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--text-muted)", letterSpacing: "0.08em", textTransform: "uppercase", textAlign: "center" }}>{label}</div>
    </div>
  );
}

export default function OverviewPage() {
  const { data: overview, isLoading: l1 } = useSWR("overview", () => fetcher("overview"), { refreshInterval: 30000 });
  const { data: competitors } = useSWR("competitors-list", () => fetcher("competitors"), { refreshInterval: 30000 });
  const { data: socialSummary } = useSWR("social-summary", () => fetcher("social"), { refreshInterval: 30000 });
  const { data: marketScores } = useSWR("market-scores", () => fetcher("market"), { refreshInterval: 30000 });
  const { data: crawlStats } = useSWR("crawl-stats-live", () => fetcher("crawlStats"), { refreshInterval: 5000 });
  const { data: aggStats } = useSWR("crawl-agg-stats", () => fetcher("aggStats"), { refreshInterval: 15000 });

  if (l1) {
    return (
      <div style={{ padding: "2rem 0" }}>
        <div className="loading-bar" style={{ marginBottom: 24, width: "100%" }} />
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-muted)", letterSpacing: "0.1em" }}>LOADING COMMAND CENTER...</div>
      </div>
    );
  }

  const k = overview?.kpis ?? {};
  const s = overview?.score_overview ?? {};
  const issues = overview?.critical_issues ?? [];
  const social = socialSummary ?? [];
  const market = marketScores ?? [];
  const recentJobs = aggStats?.recent ?? [];
  const domains = crawlStats?.domains ?? [];

  // Top competitors by composite score
  const topCompetitors = [...(competitors ?? [])]
    .sort((a: any, b: any) => {
      const sa = [a.seo_score, a.perf_score, a.social_score, a.market_score].filter(Boolean).reduce((s: number, v: any) => s + parseFloat(v), 0) / Math.max([a.seo_score, a.perf_score, a.social_score, a.market_score].filter(Boolean).length, 1);
      const sb = [b.seo_score, b.perf_score, b.social_score, b.market_score].filter(Boolean).reduce((s: number, v: any) => s + parseFloat(v), 0) / Math.max([b.seo_score, b.perf_score, b.social_score, b.market_score].filter(Boolean).length, 1);
      return sb - sa;
    })
    .slice(0, 8);

  // Social top performers
  const socialTop = [...social].sort((a: any, b: any) => parseFloat(b.score ?? 0) - parseFloat(a.score ?? 0)).slice(0, 6);

  // Market top
  const marketTop = [...market].sort((a: any, b: any) => (b.final_score ?? 0) - (a.final_score ?? 0)).slice(0, 6);

  const STATUS_COLORS: Record<string, string> = {
    completed: "var(--success)", inflight: "#3b82f6", queued: "#f59e0b",
    failed: "var(--danger)", retry_scheduled: "#f59e0b",
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-6)" }} className="animate-in">

      {/* Header */}
      <div className="page-header">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
          <div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 6 }}>
              Module 01 — Overview
            </div>
            <h1 className="page-title">Command Center</h1>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.08em" }}>AUTO-REFRESH 30s</div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--success)", letterSpacing: "0.08em" }}>● LIVE</div>
          </div>
        </div>
      </div>

      {/* KPI Cards — 2 rows */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: "var(--sp-3)" }}>
        <KpiCard code="K/01" icon={Globe} label="Competitors" value={k.competitors_total ?? 0} accentColor="#3b82f6" sub={`${domains.length} in queue`} link="/dashboard/competitors" />
        <KpiCard code="K/02" icon={FileText} label="Pages" value={k.pages_total ?? 0} accentColor="#8b5cf6" sub="crawled & indexed" link="/dashboard/seo" />
        <KpiCard code="K/03" icon={ShoppingBag} label="Products" value={k.products_total ?? 0} accentColor="#f59e0b" sub="tracked" link="/dashboard/market" />
        <KpiCard code="K/04" icon={Activity} label="In Flight" value={crawlStats?.inflight ?? 0} accentColor="#3b82f6" sub="being scraped now" link="/dashboard/crawl" />
        <KpiCard code="K/05" icon={CheckCircle} label="Completed" value={k.jobs_completed ?? 0} accentColor="#10b981" sub={`${aggStats?.totals?.last_24h ?? 0} last 24h`} link="/dashboard/crawl" />
        <KpiCard code="K/06" icon={XCircle} label="Failed" value={k.jobs_failed ?? 0} accentColor="#ef4444" sub={`${crawlStats?.retry_scheduled ?? 0} retrying`} link="/dashboard/crawl" />
      </div>

      {/* Score Rings + Scraper Status row */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--sp-4)" }}>
        {/* Score Overview as Rings */}
        <div className="card" style={{ padding: "var(--sp-5)" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "var(--sp-5)" }}>
            <div className="card-title" style={{ margin: 0 }}>SCORE DIMENSIONS</div>
            <Link href="/dashboard/compare" style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--accent)", textDecoration: "none", display: "flex", alignItems: "center", gap: 4 }}>
              COMPARE <ChevronRight size={12} />
            </Link>
          </div>
          <div style={{ display: "flex", justifyContent: "space-around" }}>
            <ScoreRing label="SEO" value={s.seo} color="#3b82f6" />
            <ScoreRing label="PERF" value={s.performance ? s.performance * 100 : null} color="#8b5cf6" />
            <ScoreRing label="SOCIAL" value={s.social ? s.social * 100 : null} color="#f59e0b" />
            <ScoreRing label="MARKET" value={s.market} color="#10b981" />
          </div>
        </div>

        {/* Scraper Live Status */}
        <div className="card" style={{ padding: "var(--sp-5)" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "var(--sp-4)" }}>
            <div className="card-title" style={{ margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
              <Zap size={12} style={{ color: "var(--accent)" }} />
              SCRAPER LIVE
            </div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--success)" }}>● ACTIVE</div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "var(--sp-3)", marginBottom: "var(--sp-4)" }}>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 22, fontWeight: 700, color: "#f59e0b" }}>{crawlStats?.queued ?? 0}</div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--text-muted)" }}>QUEUED</div>
            </div>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 22, fontWeight: 700, color: "#3b82f6" }}>{crawlStats?.inflight ?? 0}</div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--text-muted)" }}>INFLIGHT</div>
            </div>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 22, fontWeight: 700, color: "#10b981" }}>{crawlStats?.completed ?? 0}</div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--text-muted)" }}>COMPLETED</div>
            </div>
          </div>
          {/* Top domains in queue */}
          <div style={{ borderTop: "1px solid var(--border)", paddingTop: "var(--sp-3)" }}>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--text-muted)", marginBottom: 6, letterSpacing: "0.1em" }}>TOP DOMAINS</div>
            {domains.slice(0, 4).map((d: any) => (
              <div key={d.domain} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-secondary)", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{d.domain}</span>
                <MiniBar value={d.queued + d.inflight} max={Math.max(...domains.map((x: any) => x.queued + x.inflight), 1)} color={d.inflight > 0 ? "#3b82f6" : "#f59e0b"} />
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", width: 20, textAlign: "right" }}>{d.queued + d.inflight}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Competitor Leaderboard + Social + Market in 3 columns */}
      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr 1fr", gap: "var(--sp-4)" }}>
        {/* Competitor Leaderboard */}
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <div style={{ padding: "var(--sp-4) var(--sp-5)", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div className="card-title" style={{ margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
              <TrendingUp size={12} style={{ color: "var(--accent)" }} />
              COMPETITOR RANKINGS
            </div>
            <Link href="/dashboard/competitors" style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--accent)", textDecoration: "none" }}>
              VIEW ALL <ChevronRight size={10} style={{ display: "inline" }} />
            </Link>
          </div>
          <div style={{ maxHeight: 380, overflowY: "auto" }}>
            {topCompetitors.map((c: any, i: number) => {
              const scores = [c.seo_score, c.perf_score, c.social_score, c.market_score].filter(Boolean).map(Number);
              const avg = scores.length > 0 ? scores.reduce((s: number, v: number) => s + v, 0) / scores.length : 0;
              return (
                <Link key={c.id} href={`/dashboard/competitors/${c.id}`} style={{ textDecoration: "none", color: "inherit" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 20px", borderBottom: "1px solid var(--border)", transition: "background 0.15s", cursor: "pointer" }}
                    onMouseEnter={e => (e.currentTarget.style.background = "var(--bg-surface)")}
                    onMouseLeave={e => (e.currentTarget.style.background = "transparent")}>
                    <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: i < 3 ? "var(--accent)" : "var(--text-muted)", width: 20, textAlign: "center", fontWeight: i < 3 ? 700 : 400 }}>
                      {String(i + 1).padStart(2, "0")}
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--text-primary)" }}>{c.name}</div>
                      <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)" }}>{c.domain}</div>
                    </div>
                    <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                      <div style={{ width: 40, height: 40, borderRadius: 6, background: `conic-gradient(var(--accent) ${avg * 3.6}deg, var(--border) 0deg)`, display: "flex", alignItems: "center", justifyContent: "center" }}>
                        <div style={{ width: 32, height: 32, borderRadius: 4, background: "var(--bg-card)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                          <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, fontWeight: 700, color: "var(--text-primary)" }}>{avg.toFixed(0)}</span>
                        </div>
                      </div>
                    </div>
                    <ChevronRight size={14} style={{ color: "var(--text-muted)" }} />
                  </div>
                </Link>
              );
            })}
          </div>
        </div>

        {/* Social Media Summary */}
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <div style={{ padding: "var(--sp-4) var(--sp-5)", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div className="card-title" style={{ margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
              <Share2 size={12} style={{ color: "#f59e0b" }} />
              SOCIAL LEADERS
            </div>
            <Link href="/dashboard/social" style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--accent)", textDecoration: "none" }}>
              VIEW ALL <ChevronRight size={10} style={{ display: "inline" }} />
            </Link>
          </div>
          <div style={{ maxHeight: 380, overflowY: "auto" }}>
            {socialTop.map((s: any, i: number) => (
              <Link key={`${s.competitor_id}-${s.platform}`} href={`/dashboard/social/${s.competitor_id}`} style={{ textDecoration: "none", color: "inherit" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 20px", borderBottom: "1px solid var(--border)", transition: "background 0.15s", cursor: "pointer" }}
                  onMouseEnter={e => (e.currentTarget.style.background = "var(--bg-surface)")}
                  onMouseLeave={e => (e.currentTarget.style.background = "transparent")}>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-muted)", width: 20, textAlign: "center" }}>{String(i + 1).padStart(2, "0")}</div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--text-primary)" }}>{s.domain}</div>
                    <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", textTransform: "capitalize" }}>{s.platform}</div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 600, color: "#f59e0b" }}>{(parseFloat(s.score ?? 0) * 100).toFixed(1)}%</div>
                    <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--text-muted)" }}>{s.follower_count?.toLocaleString() ?? 0} followers</div>
                  </div>
                </div>
              </Link>
            ))}
            {socialTop.length === 0 && (
              <div style={{ padding: "2rem", textAlign: "center", fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-muted)" }}>NO SOCIAL DATA</div>
            )}
          </div>
        </div>

        {/* Market Overview */}
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <div style={{ padding: "var(--sp-4) var(--sp-5)", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div className="card-title" style={{ margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
              <ShoppingBag size={12} style={{ color: "#10b981" }} />
              MARKET POSITION
            </div>
            <Link href="/dashboard/market" style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--accent)", textDecoration: "none" }}>
              VIEW ALL <ChevronRight size={10} style={{ display: "inline" }} />
            </Link>
          </div>
          <div style={{ maxHeight: 380, overflowY: "auto" }}>
            {marketTop.map((m: any, i: number) => (
              <Link key={m.competitor_id} href={`/dashboard/market`} style={{ textDecoration: "none", color: "inherit" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 20px", borderBottom: "1px solid var(--border)", transition: "background 0.15s", cursor: "pointer" }}
                  onMouseEnter={e => (e.currentTarget.style.background = "var(--bg-surface)")}
                  onMouseLeave={e => (e.currentTarget.style.background = "transparent")}>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-muted)", width: 20, textAlign: "center" }}>{String(i + 1).padStart(2, "0")}</div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--text-primary)" }}>{m.name}</div>
                    <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)" }}>{m.domain}</div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 600, color: "#10b981" }}>{m.final_score?.toFixed(1) ?? "—"}</div>
                    <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--text-muted)" }}>{m.product_count ?? 0} products</div>
                  </div>
                </div>
              </Link>
            ))}
            {marketTop.length === 0 && (
              <div style={{ padding: "2rem", textAlign: "center", fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-muted)" }}>NO MARKET DATA</div>
            )}
          </div>
        </div>
      </div>

      {/* Critical Issues + Recent Activity */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--sp-4)" }}>
        {/* Critical Issues */}
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <div style={{ padding: "var(--sp-4) var(--sp-5)", borderBottom: "1px solid var(--border)" }}>
            <div className="card-title" style={{ margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
              <AlertTriangle size={12} style={{ color: "var(--danger)" }} />
              CRITICAL ISSUES
              {issues.length > 0 && (
                <span style={{ marginLeft: "auto", fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--danger)", background: "color-mix(in srgb, var(--danger) 12%, transparent)", padding: "2px 8px", borderRadius: 4 }}>
                  {issues.length}
                </span>
              )}
            </div>
          </div>
          <div style={{ maxHeight: 300, overflowY: "auto" }}>
            {issues.slice(0, 8).map((i: any, idx: number) => (
              <div key={idx} style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 20px", borderBottom: "1px solid var(--border)" }}>
                <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", width: 20, textAlign: "center" }}>{String(idx + 1).padStart(2, "0")}</div>
                <div style={{ flex: 1, fontSize: 12, color: "var(--text-primary)" }}>{i.issue}</div>
                <span className="badge badge-red" style={{ fontSize: 9 }}>{i.total_affected_pages} pages</span>
              </div>
            ))}
            {issues.length === 0 && (
              <div style={{ padding: "2rem", textAlign: "center", fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-muted)" }}>
                <CheckCircle size={24} style={{ color: "var(--success)", marginBottom: 8 }} />
                <div>NO CRITICAL ISSUES</div>
              </div>
            )}
          </div>
        </div>

        {/* Recent Scrape Activity */}
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <div style={{ padding: "var(--sp-4) var(--sp-5)", borderBottom: "1px solid var(--border)" }}>
            <div className="card-title" style={{ margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
              <Activity size={12} style={{ color: "var(--accent)" }} />
              RECENT ACTIVITY
            </div>
          </div>
          <div style={{ maxHeight: 300, overflowY: "auto" }}>
            {recentJobs.slice(0, 10).map((j: any) => (
              <div key={j.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 20px", borderBottom: "1px solid var(--border)" }}>
                <div style={{ width: 8, height: 8, borderRadius: "50%", background: STATUS_COLORS[j.status] ?? "var(--text-muted)", flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-primary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{j.url}</div>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--text-muted)" }}>{j.domain} · {j.job_type}</div>
                </div>
                <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--text-muted)", whiteSpace: "nowrap" }}>
                  {j.finished_at ? new Date(j.finished_at).toLocaleString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false }) : "—"}
                </div>
              </div>
            ))}
            {recentJobs.length === 0 && (
              <div style={{ padding: "2rem", textAlign: "center", fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-muted)" }}>NO RECENT ACTIVITY</div>
            )}
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="card" style={{ padding: "var(--sp-4) var(--sp-5)", display: "flex", alignItems: "center", gap: "var(--sp-4)" }}>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.1em" }}>QUICK ACTIONS</div>
        <div style={{ display: "flex", gap: "var(--sp-2)", flex: 1 }}>
          <Link href="/dashboard/compare" className="btn btn-ghost" style={{ fontFamily: "var(--font-mono)", fontSize: 11, textDecoration: "none", display: "flex", alignItems: "center", gap: 6 }}>
            <BarChart3 size={12} /> Compare Competitors
          </Link>
          <Link href="/dashboard/crawl" className="btn btn-ghost" style={{ fontFamily: "var(--font-mono)", fontSize: 11, textDecoration: "none", display: "flex", alignItems: "center", gap: 6 }}>
            <Zap size={12} /> View Scraping
          </Link>
          <Link href="/dashboard/reports" className="btn btn-ghost" style={{ fontFamily: "var(--font-mono)", fontSize: 11, textDecoration: "none", display: "flex", alignItems: "center", gap: 6 }}>
            <FileText size={12} /> Generate Report
          </Link>
          <Link href="/dashboard/council" className="btn btn-ghost" style={{ fontFamily: "var(--font-mono)", fontSize: 11, textDecoration: "none", display: "flex", alignItems: "center", gap: 6 }}>
            <Users size={12} /> Ask Council
          </Link>
        </div>
      </div>
    </div>
  );
}
