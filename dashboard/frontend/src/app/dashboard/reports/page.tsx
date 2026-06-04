"use client";
import { useState } from "react";
import useSWR from "swr";
import { reportsApi, webhooksApi, competitorsApi } from "@/lib/api";
import {
  FileText, Trash2, Plus, Zap, RefreshCw, Radio,
  CheckCircle, Clock, ChevronDown,
} from "lucide-react";
import { useToast } from "@/components/ToastProvider";

// ─── Types ────────────────────────────────────────────────────────────────────

type ReportType = "competitor_platform" | "social_media" | "seo_gap" | "refresh_views";

interface Report {
  id: string;
  title: string;
  filters: Record<string, unknown> | string;
  created_at: string;
}

interface WebhookEvent {
  id: number;
  source: string;
  event: string;
  payload: Record<string, unknown> | string;
  received_at: string;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const REPORT_TYPES: { value: ReportType; label: string; desc: string }[] = [
  { value: "competitor_platform", label: "Competitor Platform Report", desc: "Full page analysis, SEO scores & action plan via n8n" },
  { value: "social_media",        label: "Social Media Report",        desc: "Engagement metrics, forecasts & trend analysis" },
  { value: "seo_gap",             label: "SEO Gap Report",             desc: "Cross-competitor gap matrix & content opportunities" },
  { value: "refresh_views",       label: "Refresh Materialized Views", desc: "Force n8n to re-compute all analytics views" },
];

const EVENT_ICONS: Record<string, React.ReactNode> = {
  "report.completed": <CheckCircle size={12} color="var(--success)" />,
  "crawl.finished":   <CheckCircle size={12} color="var(--accent)" />,
  "views.refreshed":  <RefreshCw  size={12} color="var(--text-muted)" />,
};

// ─── Fetchers ─────────────────────────────────────────────────────────────────

const fetchReports    = () => reportsApi.list().then(r => r.data as Report[]);
const fetchEvents     = () => webhooksApi.events(undefined, 30).then(r => r.data as WebhookEvent[]);
const fetchCompetitors = () => competitorsApi.list().then(r => r.data as { id: number; domain: string }[]);

// ─── Generate Dialog ──────────────────────────────────────────────────────────

function GenerateDialog({
  competitors,
  onClose,
  onSuccess,
}: {
  competitors: { id: number; domain: string }[];
  onClose: () => void;
  onSuccess: () => void;
}) {
  const { toast } = useToast();
  const [type, setType]         = useState<ReportType>("competitor_platform");
  const [competitorId, setCompId] = useState<string>("");
  const [title, setTitle]       = useState("");
  const [busy, setBusy]         = useState(false);

  const needsCompetitor = type !== "refresh_views";

  const handleGenerate = async () => {
    if (needsCompetitor && !competitorId) {
      toast("Please select a competitor", "error");
      return;
    }
    setBusy(true);
    try {
      await reportsApi.generate({
        report_type: type,
        competitor_id: competitorId ? Number(competitorId) : undefined,
        title: title || undefined,
      });
      toast("Report generation triggered — n8n is processing", "success");
      onSuccess();
      onClose();
    } catch {
      toast("Failed to trigger n8n workflow", "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 9999,
      background: "rgba(0,0,0,0.7)", backdropFilter: "blur(4px)",
      display: "flex", alignItems: "center", justifyContent: "center",
    }} onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="card" style={{ width: 480, padding: "var(--sp-8)", position: "relative" }}>
        {/* Header */}
        <div style={{ marginBottom: "var(--sp-6)" }}>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--accent)", letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 6 }}>
            n8n Webhook Trigger
          </div>
          <h2 style={{ fontSize: 16, fontWeight: 700, margin: 0 }}>Generate Report</h2>
        </div>

        {/* Report type picker */}
        <label style={{ display: "block", marginBottom: "var(--sp-4)" }}>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 6 }}>
            Report Type
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {REPORT_TYPES.map(rt => (
              <label key={rt.value} style={{
                display: "flex", alignItems: "flex-start", gap: 10,
                padding: "10px 12px", borderRadius: 6, cursor: "pointer",
                border: `1px solid ${type === rt.value ? "var(--accent)" : "var(--border)"}`,
                background: type === rt.value ? "rgba(255,184,0,0.05)" : "transparent",
                transition: "all 0.15s",
              }}>
                <input
                  type="radio" name="rtype" value={rt.value}
                  checked={type === rt.value}
                  onChange={() => setType(rt.value)}
                  style={{ marginTop: 2, accentColor: "var(--accent)" }}
                />
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 2 }}>{rt.label}</div>
                  <div style={{ fontSize: 11, color: "var(--text-muted)" }}>{rt.desc}</div>
                </div>
              </label>
            ))}
          </div>
        </label>

        {/* Competitor selector (when needed) */}
        {needsCompetitor && (
          <label style={{ display: "block", marginBottom: "var(--sp-4)" }}>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 6 }}>
              Competitor
            </div>
            <div style={{ position: "relative" }}>
              <select
                value={competitorId}
                onChange={e => setCompId(e.target.value)}
                style={{
                  width: "100%", appearance: "none",
                  background: "var(--bg-secondary)", border: "1px solid var(--border)",
                  color: "var(--text-primary)", borderRadius: 6, padding: "8px 32px 8px 12px",
                  fontFamily: "var(--font-mono)", fontSize: 12,
                }}
              >
                <option value="">— Select competitor —</option>
                {competitors.map(c => (
                  <option key={c.id} value={c.id}>{c.domain}</option>
                ))}
              </select>
              <ChevronDown size={14} style={{ position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)", pointerEvents: "none" }} />
            </div>
          </label>
        )}

        {/* Optional custom title */}
        <label style={{ display: "block", marginBottom: "var(--sp-6)" }}>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 6 }}>
            Custom Title (optional)
          </div>
          <input
            type="text" value={title}
            onChange={e => setTitle(e.target.value)}
            placeholder="Leave blank for auto-generated title"
            style={{
              width: "100%", boxSizing: "border-box",
              background: "var(--bg-secondary)", border: "1px solid var(--border)",
              color: "var(--text-primary)", borderRadius: 6, padding: "8px 12px",
              fontFamily: "var(--font-mono)", fontSize: 12,
            }}
          />
        </label>

        {/* Footer buttons */}
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={handleGenerate} disabled={busy}
            style={{ display: "flex", alignItems: "center", gap: 6, opacity: busy ? 0.7 : 1 }}>
            {busy ? <RefreshCw size={13} style={{ animation: "spin 1s linear infinite" }} /> : <Zap size={13} />}
            {busy ? "Triggering…" : "Trigger n8n"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function ReportsPage() {
  const { data: reports, isLoading: loadingReports, mutate: mutateReports } =
    useSWR("saved-reports", fetchReports, { refreshInterval: 15000 });

  const { data: events, isLoading: loadingEvents, mutate: mutateEvents } =
    useSWR("webhook-events", fetchEvents, { refreshInterval: 10000 });

  const { data: competitors = [] } =
    useSWR("competitors", fetchCompetitors);

  const { toast } = useToast();
  const [showDialog, setShowDialog] = useState(false);
  const [activeTab, setActiveTab]   = useState<"reports" | "events">("reports");

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this report?")) return;
    try {
      await reportsApi.delete(id);
      mutateReports();
      toast("Report deleted", "success");
    } catch {
      toast("Failed to delete report", "error");
    }
  };

  const parseFilters = (f: unknown) => {
    if (typeof f === "string") {
      try { return JSON.parse(f); } catch { return {}; }
    }
    return f ?? {};
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-8)" }} className="animate-in">
      {/* Page header */}
      <div className="page-header">
        <div>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 6 }}>
            Module 08 — Reports & Webhooks
          </div>
          <h1 className="page-title">Reports</h1>
        </div>
        <button
          className="btn btn-primary"
          style={{ display: "flex", alignItems: "center", gap: 8 }}
          onClick={() => setShowDialog(true)}
        >
          <Plus size={14} />
          Generate Report
        </button>
      </div>

      {/* Stats row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "var(--sp-4)" }}>
        {[
          { label: "Saved Reports",    value: reports?.length ?? "—",  icon: <FileText size={14} color="var(--accent)" /> },
          { label: "Webhook Events",   value: events?.length  ?? "—",  icon: <Radio    size={14} color="#22d3ee" /> },
          { label: "n8n Base URL",     value: "192.168.1.222:5678",    icon: <Zap      size={14} color="var(--text-muted)" /> },
        ].map(s => (
          <div key={s.label} className="card" style={{ padding: "var(--sp-5)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
              {s.icon}
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.1em" }}>
                {s.label}
              </span>
            </div>
            <div style={{ fontSize: 22, fontWeight: 700, fontFamily: "var(--font-mono)" }}>{s.value}</div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 2, borderBottom: "1px solid var(--border)" }}>
        {(["reports", "events"] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              background: "transparent", border: "none", cursor: "pointer",
              padding: "8px 16px", fontFamily: "var(--font-mono)", fontSize: 11,
              letterSpacing: "0.08em", textTransform: "uppercase",
              color: activeTab === tab ? "var(--text-primary)" : "var(--text-muted)",
              borderBottom: `2px solid ${activeTab === tab ? "var(--accent)" : "transparent"}`,
              marginBottom: -1, transition: "all 0.15s",
            }}
          >
            {tab === "reports" ? "Saved Reports" : "Webhook Events"}
            <span style={{
              marginLeft: 8, padding: "2px 6px", borderRadius: 10,
              background: activeTab === tab ? "var(--accent)" : "var(--bg-secondary)",
              color: activeTab === tab ? "#000" : "var(--text-muted)",
              fontSize: 10, fontWeight: 700,
            }}>
              {tab === "reports" ? (reports?.length ?? 0) : (events?.length ?? 0)}
            </span>
          </button>
        ))}
        <button
          onClick={() => { mutateReports(); mutateEvents(); }}
          style={{ marginLeft: "auto", background: "transparent", border: "none", cursor: "pointer", padding: "8px 12px", color: "var(--text-muted)" }}
          title="Refresh"
        >
          <RefreshCw size={13} />
        </button>
      </div>

      {/* ── Saved Reports tab ── */}
      {activeTab === "reports" && (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          {loadingReports ? (
            <div style={{ padding: "2rem", textAlign: "center", color: "var(--text-muted)" }}>Loading reports…</div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Type</th>
                  <th>Created</th>
                  <th style={{ width: 90 }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {(reports ?? []).map((r) => {
                  const filters = parseFilters(r.filters);
                  const badge = filters.report_type as string | undefined;
                  return (
                    <tr key={r.id}>
                      <td style={{ fontWeight: 600 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <FileText size={13} color="var(--accent)" />
                          {r.title}
                          {filters.auto_generated && (
                            <span style={{ fontSize: 9, padding: "1px 5px", borderRadius: 4, background: "rgba(255,184,0,0.15)", color: "var(--accent)", fontFamily: "var(--font-mono)", letterSpacing: "0.08em" }}>
                              AUTO
                            </span>
                          )}
                        </div>
                      </td>
                      <td>
                        {badge ? (
                          <code style={{ fontSize: 10, color: "var(--text-secondary)", background: "rgba(0,0,0,0.25)", padding: "2px 7px", borderRadius: 4 }}>
                            {badge.replace(/_/g, " ")}
                          </code>
                        ) : "—"}
                      </td>
                      <td style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: 11 }}>
                        {new Date(r.created_at).toLocaleString()}
                      </td>
                      <td>
                        <button
                          className="btn btn-ghost"
                          style={{ padding: "6px", color: "var(--danger)" }}
                          onClick={() => handleDelete(r.id)}
                          title="Delete"
                        >
                          <Trash2 size={13} />
                        </button>
                      </td>
                    </tr>
                  );
                })}
                {reports?.length === 0 && (
                  <tr>
                    <td colSpan={4} style={{ textAlign: "center", padding: "3rem", color: "var(--text-muted)" }}>
                      <FileText size={28} style={{ marginBottom: 12, opacity: 0.3, display: "block", margin: "0 auto 12px" }} />
                      No saved reports yet. Click <strong>Generate Report</strong> to trigger an n8n workflow.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* ── Webhook Events tab ── */}
      {activeTab === "events" && (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          {loadingEvents ? (
            <div style={{ padding: "2rem", textAlign: "center", color: "var(--text-muted)" }}>Loading events…</div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Event</th>
                  <th>Source</th>
                  <th>Payload</th>
                  <th>Received</th>
                </tr>
              </thead>
              <tbody>
                {(events ?? []).map((ev) => {
                  const payload = parseFilters(ev.payload);
                  const icon = EVENT_ICONS[ev.event] ?? <Clock size={12} color="var(--text-muted)" />;
                  return (
                    <tr key={ev.id}>
                      <td>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          {icon}
                          <span style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>{ev.event}</span>
                        </div>
                      </td>
                      <td>
                        <span style={{
                          fontSize: 10, padding: "2px 7px", borderRadius: 4, fontFamily: "var(--font-mono)",
                          background: ev.source === "n8n" ? "rgba(34,211,238,0.12)" : "rgba(255,184,0,0.12)",
                          color: ev.source === "n8n" ? "#22d3ee" : "var(--accent)",
                        }}>
                          {ev.source}
                        </span>
                      </td>
                      <td style={{ maxWidth: 300 }}>
                        <code style={{
                          fontSize: 10, color: "var(--text-secondary)", background: "rgba(0,0,0,0.25)",
                          padding: "2px 6px", borderRadius: 4, display: "block", overflow: "hidden",
                          textOverflow: "ellipsis", whiteSpace: "nowrap",
                        }}>
                          {JSON.stringify(payload)}
                        </code>
                      </td>
                      <td style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: 11, whiteSpace: "nowrap" }}>
                        {new Date(ev.received_at).toLocaleString()}
                      </td>
                    </tr>
                  );
                })}
                {events?.length === 0 && (
                  <tr>
                    <td colSpan={4} style={{ textAlign: "center", padding: "3rem", color: "var(--text-muted)" }}>
                      <Radio size={28} style={{ marginBottom: 12, opacity: 0.3, display: "block", margin: "0 auto 12px" }} />
                      No webhook events received yet.
                      <div style={{ marginTop: 8, fontSize: 11 }}>
                        Configure n8n to POST to{" "}
                        <code style={{ background: "rgba(0,0,0,0.3)", padding: "1px 6px", borderRadius: 3 }}>
                          /api/v1/webhooks/n8n
                        </code>
                        {" "}at the end of each workflow.
                      </div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Generate dialog */}
      {showDialog && (
        <GenerateDialog
          competitors={competitors}
          onClose={() => setShowDialog(false)}
          onSuccess={() => { mutateReports(); mutateEvents(); }}
        />
      )}

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
