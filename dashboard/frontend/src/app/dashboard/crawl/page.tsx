"use client";
import useSWR from "swr";
import { useState } from "react";
import { crawlApi } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Activity, RefreshCw, Plus, AlertTriangle, Database, Zap, Clock, CheckCircle, XCircle, RotateCw, Globe, Server } from "lucide-react";

const fetchStats = () => () => crawlApi.stats().then(r => r.data);
const fetchAggregate = () => () => crawlApi.statsAggregate().then(r => r.data);

const STATUS_COLORS: Record<string, string> = {
  completed: "badge-green", inflight: "badge-blue", queued: "badge-amber",
  failed: "badge-red", retry_scheduled: "badge-amber", pending: "badge-amber",
  in_progress: "badge-blue",
};

function StatCard({ label, value, icon: Icon, color, sub }: { label: string; value: number | string; icon: any; color: string; sub?: string }) {
  return (
    <div className="card" style={{ display: "flex", alignItems: "center", gap: "var(--sp-4)", padding: "var(--sp-5)" }}>
      <div style={{ width: 44, height: 44, borderRadius: 8, background: `color-mix(in srgb, ${color} 15%, transparent)`, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <Icon size={20} style={{ color }} />
      </div>
      <div>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.12em", textTransform: "uppercase" }}>{label}</div>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 24, fontWeight: 700, color: "var(--text-primary)", lineHeight: 1.2 }}>{typeof value === "number" ? value.toLocaleString() : value}</div>
        {sub && <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)" }}>{sub}</div>}
      </div>
    </div>
  );
}

function ProgressBar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = max > 0 ? (value / max) * 100 : 0;
  return (
    <div style={{ width: "100%", height: 6, background: "var(--border)", borderRadius: 3, overflow: "hidden" }}>
      <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 3, transition: "width 0.5s ease" }} />
    </div>
  );
}

export default function CrawlPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [status, setStatus] = useState("");
  const [url, setUrl] = useState("");
  const [triggerMsg, setTriggerMsg] = useState("");

  const { data: frontier, isLoading: loadingFrontier } = useSWR("crawl-stats", fetchStats(), { refreshInterval: 3000 });
  const { data: aggregate } = useSWR("crawl-aggregate", fetchAggregate(), { refreshInterval: 10000 });
  const { data: health } = useSWR("scraper-health", () => crawlApi.scraperHealth().then(r => r.data), { refreshInterval: 10000 });

  async function handleTrigger() {
    if (!url.trim()) return;
    try {
      await crawlApi.triggerUrl(url.trim());
      setTriggerMsg(`SYS_MSG: Queued -> ${url}`);
      setUrl("");
    } catch (e: any) {
      setTriggerMsg("ERR: " + (e.response?.data?.detail ?? e.message));
    }
  }

  async function handleRefreshViews() {
    try {
      await crawlApi.refreshViews();
      setTriggerMsg("SYS_MSG: MatView refresh dispatched.");
    } catch (e: any) {
      setTriggerMsg("ERR: " + (e.response?.data?.detail ?? e.message));
    }
  }

  const f = frontier ?? {};
  const agg = aggregate?.totals ?? {};
  const domains = frontier?.domains ?? [];
  const recentJobs = aggregate?.recent ?? [];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-6)" }} className="animate-in">

      {/* Header */}
      <div className="page-header">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
          <div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 6 }}>
              Module 07 — Execution
            </div>
            <h1 className="page-title">Scraping Dashboard</h1>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.08em" }}>SCRAPER STATUS</div>
            <div style={{
              fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 600,
              color: health?.scraper_online ? "var(--success)" : "var(--danger)", marginTop: 4
            }}>
              {health?.scraper_online ? "● ONLINE" : "○ OFFLINE"}
            </div>
          </div>
        </div>
      </div>

      {/* Summary Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: "var(--sp-3)" }}>
        <StatCard label="QUEUED" value={f.queued ?? 0} icon={Clock} color="#f59e0b" sub="in frontier queue" />
        <StatCard label="INFLIGHT" value={f.inflight ?? 0} icon={Zap} color="#3b82f6" sub="being scraped" />
        <StatCard label="COMPLETED" value={agg.completed ?? f.completed ?? 0} icon={CheckCircle} color="#10b981" sub={`last 24h: ${agg.last_24h ?? 0}`} />
        <StatCard label="FAILED" value={f.failed ?? 0} icon={XCircle} color="#ef4444" sub="dead-letter queue" />
        <StatCard label="RETRY" value={f.retry_scheduled ?? 0} icon={RotateCw} color="#f59e0b" sub="scheduled retries" />
        <StatCard label="DOMAINS" value={f.total_domains_in_queue ?? 0} icon={Globe} color="#8b5cf6" sub={`${f.ready_domains ?? 0} ready`} />
      </div>

      {/* Avg Duration + DB Totals */}
      {agg.avg_duration_seconds && (
        <div className="card" style={{ display: "flex", alignItems: "center", gap: "var(--sp-6)", padding: "var(--sp-4) var(--sp-5)" }}>
          <Database size={16} style={{ color: "var(--text-muted)" }} />
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-muted)" }}>
            AVG SCRAPE DURATION: <span style={{ color: "var(--text-primary)" }}>{Number(agg.avg_duration_seconds).toFixed(1)}s</span>
          </div>
          <div style={{ width: 1, height: 20, background: "var(--border)" }} />
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-muted)" }}>
            TOTAL JOBS: <span style={{ color: "var(--text-primary)" }}>{agg.total ?? 0}</span>
          </div>
          <div style={{ width: 1, height: 20, background: "var(--border)" }} />
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-muted)" }}>
            LAST HOUR: <span style={{ color: "var(--success)" }}>{agg.last_hour ?? 0}</span>
          </div>
        </div>
      )}

      {/* Admin Dispatch */}
      {isAdmin && (
        <div className="card" style={{ display: "flex", flexDirection: "column", gap: "var(--sp-4)", border: "1px solid var(--accent)" }}>
          <div className="card-title" style={{ margin: 0, color: "var(--accent)" }}>&gt; EXECUTE_CRAWL</div>
          <div style={{ display: "flex", gap: "var(--sp-2)" }}>
            <input
              className="input"
              placeholder="TARGET_URL"
              value={url}
              onChange={e => setUrl(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleTrigger()}
              style={{ flex: 1, fontFamily: "var(--font-mono)", border: "1px solid var(--accent-glow)" }}
            />
            <button className="btn btn-primary" onClick={handleTrigger} style={{ padding: "0 24px" }}>DISPATCH</button>
            <button className="btn btn-ghost" onClick={handleRefreshViews} style={{ gap: 6, padding: "0 16px" }}>
              <RefreshCw size={14} /> REFRESH VIEWS
            </button>
          </div>
          {triggerMsg && (
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--accent)" }}>{triggerMsg}</div>
          )}
        </div>
      )}

      {/* Domain Breakdown + Recent Jobs side by side */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--sp-4)" }}>
        {/* Domain Breakdown */}
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <div style={{ padding: "var(--sp-4) var(--sp-5)", borderBottom: "1px solid var(--border)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Globe size={14} style={{ color: "var(--accent)" }} />
              <span className="card-title" style={{ margin: 0 }}>DOMAIN BREAKDOWN</span>
            </div>
          </div>
          <div style={{ maxHeight: 360, overflowY: "auto" }}>
            <table className="table" style={{ margin: 0 }}>
              <thead>
                <tr>
                  <th>DOMAIN</th>
                  <th style={{ width: 70, textAlign: "right" }}>QUEUED</th>
                  <th style={{ width: 70, textAlign: "right" }}>INFLIGHT</th>
                  <th style={{ width: 120 }}>LOAD</th>
                </tr>
              </thead>
              <tbody>
                {domains.length === 0 ? (
                  <tr>
                    <td colSpan={4} style={{ textAlign: "center", color: "var(--text-muted)", padding: "2rem", fontFamily: "var(--font-mono)", fontSize: 11 }}>
                      NO DOMAINS IN QUEUE
                    </td>
                  </tr>
                ) : (
                  domains.map((d: any) => {
                    const maxQ = Math.max(...domains.map((x: any) => x.queued), 1);
                    return (
                      <tr key={d.domain}>
                        <td style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--text-primary)" }}>{d.domain}</td>
                        <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontSize: 12, color: d.queued > 0 ? "#f59e0b" : "var(--text-muted)" }}>{d.queued}</td>
                        <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontSize: 12, color: d.inflight > 0 ? "#3b82f6" : "var(--text-muted)" }}>{d.inflight}</td>
                        <td><ProgressBar value={d.queued + d.inflight} max={maxQ} color={d.inflight > 0 ? "#3b82f6" : "#f59e0b"} /></td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Recent Jobs Feed */}
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <div style={{ padding: "var(--sp-4) var(--sp-5)", borderBottom: "1px solid var(--border)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Activity size={14} style={{ color: "var(--accent)" }} />
              <span className="card-title" style={{ margin: 0 }}>RECENT JOBS</span>
            </div>
          </div>
          <div style={{ maxHeight: 360, overflowY: "auto" }}>
            <table className="table" style={{ margin: 0 }}>
              <thead>
                <tr>
                  <th style={{ width: 50 }}>ID</th>
                  <th>URL</th>
                  <th style={{ width: 80 }}>TYPE</th>
                  <th style={{ width: 80 }}>STATUS</th>
                  <th style={{ width: 100 }}>FINISHED</th>
                </tr>
              </thead>
              <tbody>
                {recentJobs.map((j: any) => (
                  <tr key={j.id}>
                    <td style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-muted)" }}>{j.id}</td>
                    <td style={{ maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontFamily: "var(--font-mono)", fontSize: 11 }}>
                      <span title={j.url}>{j.url}</span>
                    </td>
                    <td><span className="badge badge-amber" style={{ fontSize: 9 }}>{j.job_type ?? "—"}</span></td>
                    <td><span className={`badge ${STATUS_COLORS[j.status] ?? "badge-amber"}`} style={{ fontSize: 9 }}>{j.status}</span></td>
                    <td style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)" }}>
                      {j.finished_at ? new Date(j.finished_at).toLocaleString("en-US", { hour12: false }) : "—"}
                    </td>
                  </tr>
                ))}
                {recentJobs.length === 0 && (
                  <tr>
                    <td colSpan={5} style={{ textAlign: "center", color: "var(--text-muted)", padding: "2rem", fontFamily: "var(--font-mono)", fontSize: 11 }}>
                      NO RECENT JOBS
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Domain Progress Bars (full width) */}
      {domains.length > 0 && (
        <div className="card" style={{ padding: "var(--sp-5)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: "var(--sp-4)" }}>
            <Server size={14} style={{ color: "var(--accent)" }} />
            <span className="card-title" style={{ margin: 0 }}>SCRAPING PROGRESS</span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-3)" }}>
            {domains.slice(0, 12).map((d: any) => {
              const maxQ = Math.max(...domains.map((x: any) => x.queued + x.inflight), 1);
              const total = d.queued + d.inflight;
              return (
                <div key={d.domain} style={{ display: "grid", gridTemplateColumns: "160px 1fr 60px", alignItems: "center", gap: "var(--sp-3)" }}>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-secondary)" }}>{d.domain}</div>
                  <ProgressBar value={total} max={maxQ} color={d.inflight > 0 ? "#3b82f6" : d.queued > 0 ? "#f59e0b" : "#10b981"} />
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, textAlign: "right", color: "var(--text-muted)" }}>
                    {d.inflight > 0 && <span style={{ color: "#3b82f6" }}>{d.inflight} active</span>}
                    {d.inflight > 0 && d.queued > 0 && <span>, </span>}
                    {d.queued > 0 && <span style={{ color: "#f59e0b" }}>{d.queued} pending</span>}
                    {d.inflight === 0 && d.queued === 0 && <span style={{ color: "var(--success)" }}>done</span>}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
