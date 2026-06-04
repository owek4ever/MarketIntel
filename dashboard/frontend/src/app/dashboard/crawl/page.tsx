"use client";
import useSWR from "swr";
import { useState } from "react";
import { crawlApi } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Activity, RefreshCw, Plus, AlertTriangle } from "lucide-react";

const fetchJobs = (status?: string) => () =>
  crawlApi.jobs(status ? { status } : {}).then(r => r.data);

const STATUS_COLORS: Record<string, string> = {
  completed: "badge-green", in_progress: "badge-blue",
  pending: "badge-amber", failed: "badge-red",
};

export default function CrawlPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [status, setStatus] = useState("");
  const [url, setUrl] = useState("");
  const [triggerMsg, setTriggerMsg] = useState("");

  const { data, isLoading, mutate } = useSWR(
    ["crawl-jobs", status], fetchJobs(status || undefined),
    { refreshInterval: 5000 }
  );

  const { data: health } = useSWR(
    "scraper-health", () => crawlApi.scraperHealth().then(r => r.data),
    { refreshInterval: 10000 }
  );

  async function handleTrigger() {
    if (!url.trim()) return;
    try {
      await crawlApi.triggerUrl(url.trim());
      setTriggerMsg(`SYS_MSG: Queued -> ${url}`);
      setUrl("");
      mutate();
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

  const jobs = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-8)" }} className="animate-in">

      <div className="page-header">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
          <div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 6 }}>
              Module 07 — Execution
            </div>
            <h1 className="page-title">Crawl Control</h1>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.08em" }}>
              SYSTEM STATUS
            </div>
            <div style={{
              fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 600,
              color: health?.scraper_online ? "var(--success)" : "var(--danger)",
              marginTop: 4
            }}>
              {health?.scraper_online ? "● ONLINE" : "○ OFFLINE"}
            </div>
          </div>
        </div>
      </div>

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
            <button className="btn btn-primary" onClick={handleTrigger} style={{ padding: "0 24px" }}>
              DISPATCH
            </button>
            <button className="btn btn-ghost" onClick={handleRefreshViews} style={{ gap: 6, padding: "0 16px" }}>
              <RefreshCw size={14} /> REFRESH VIEWS
            </button>
          </div>
          {triggerMsg && (
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--accent)" }}>
              {triggerMsg}
            </div>
          )}
        </div>
      )}

      <div>
        <div style={{ display: "flex", gap: 1, marginBottom: "var(--sp-4)", background: "var(--border)", border: "1px solid var(--border)" }}>
          {["", "pending", "in_progress", "completed", "failed"].map(s => {
            const active = status === s;
            return (
              <button
                key={s}
                onClick={() => setStatus(s)}
                style={{
                  flex: 1,
                  background: active ? "var(--accent-dim)" : "var(--bg-surface)",
                  color: active ? "var(--accent)" : "var(--text-secondary)",
                  border: "none",
                  padding: "8px 0",
                  fontFamily: "var(--font-mono)",
                  fontSize: 10,
                  fontWeight: 600,
                  letterSpacing: "0.1em",
                  textTransform: "uppercase",
                  cursor: "pointer"
                }}
              >
                {s || "ALL_JOBS"}
              </button>
            );
          })}
        </div>

        <div className="card" style={{ padding: 0, overflow: "hidden", border: "1px solid var(--border)" }}>
          {isLoading ? (
             <div style={{ padding: "3rem 2rem" }}>
               <div className="loading-bar" style={{ marginBottom: 16, width: "100%" }} />
               <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.1em" }}>
                 FETCHING JOB QUEUE…
               </div>
             </div>
          ) : (
            <table className="table" style={{ margin: 0 }}>
              <thead>
                <tr>
                  <th style={{ width: 80 }}>JOB_ID</th>
                  <th>TARGET_URL</th>
                  <th style={{ width: 100 }}>TYPE</th>
                  <th style={{ width: 100 }}>STATUS</th>
                  <th style={{ width: 60, textAlign: "center" }}>PRIORITY</th>
                  <th style={{ width: 140 }}>QUEUED_TS</th>
                  <th style={{ width: 140 }}>FINISHED_TS</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((j: any) => (
                  <tr key={j.id}>
                    <td style={{ fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>{j.id}</td>
                    <td style={{ maxWidth: 280, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "var(--text-primary)" }}>
                      <span title={j.url}>{j.url}</span>
                    </td>
                    <td><span className="badge badge-amber">{j.job_type ?? "—"}</span></td>
                    <td><span className={`badge ${STATUS_COLORS[j.status] ?? "badge-amber"}`}>{j.status}</span></td>
                    <td style={{ textAlign: "center", fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>{j.priority}</td>
                    <td style={{ fontFamily: "var(--font-mono)", color: "var(--text-muted)", fontSize: 11 }}>
                      {j.queued_at ? new Date(j.queued_at).toLocaleString('en-US', { hour12: false }) : "—"}
                    </td>
                    <td style={{ fontFamily: "var(--font-mono)", color: "var(--text-muted)", fontSize: 11 }}>
                      {j.finished_at ? new Date(j.finished_at).toLocaleString('en-US', { hour12: false }) : "—"}
                    </td>
                  </tr>
                ))}
                {jobs.length === 0 && (
                  <tr>
                    <td colSpan={7} style={{ textAlign: "center", color: "var(--text-muted)", padding: "2rem", fontFamily: "var(--font-mono)", fontSize: 11 }}>
                      NO JOBS FOUND IN QUEUE.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
