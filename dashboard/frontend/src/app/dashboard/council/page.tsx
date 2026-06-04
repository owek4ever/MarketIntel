"use client";
import { useState, useEffect, useRef } from "react";
import useSWR from "swr";
import { councilApi, competitorsApi } from "@/lib/api";
import {
  Brain, ChevronDown, RefreshCw, Clock, CheckCircle,
  AlertCircle, Loader, Plus, X,
} from "lucide-react";
import { useToast } from "@/components/ToastProvider";

// ─── Types ─────────────────────────────────────────────────────────────────────

type DomainProfile = "general" | "social" | "market" | "seo";
type SessionStatus = "pending" | "running" | "completed" | "failed";

interface SessionSummary {
  id: string;
  question: string;
  domain_profile: string;
  competitor_id: number | null;
  status: SessionStatus;
  created_at: string;
  completed_at: string | null;
}

interface SessionDetail {
  id: string;
  question: string;
  domain_profile: string;
  competitor_id: number | null;
  status: SessionStatus;
  advisor_responses: Record<string, unknown> | null;
  html_report: string | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

// ─── Constants ─────────────────────────────────────────────────────────────────

const DOMAIN_OPTIONS: { value: DomainProfile; label: string; desc: string }[] = [
  { value: "general", label: "General",      desc: "Pure reasoning — no competitor data injected" },
  { value: "social",  label: "Social Media", desc: "Engagement scores, posts, platform forecasts" },
  { value: "market",  label: "Market",       desc: "Product catalog, pricing, category coverage" },
  { value: "seo",     label: "SEO",          desc: "Page scores, gap matrix, top issues" },
];

const STATUS_CONFIG: Record<SessionStatus, { icon: React.ReactNode; color: string; label: string }> = {
  pending:   { icon: <Clock       size={12} />,                                                  color: "#f59e0b", label: "Pending"   },
  running:   { icon: <Loader      size={12} style={{ animation: "spin 1s linear infinite" }} />, color: "#3b82f6", label: "Running"   },
  completed: { icon: <CheckCircle size={12} />,                                                  color: "#10b981", label: "Completed" },
  failed:    { icon: <AlertCircle size={12} />,                                                  color: "#ef4444", label: "Failed"    },
};

// ─── Fetchers ───────────────────────────────────────────────────────────────────

const fetchSessions    = () => councilApi.listSessions().then(r => r.data);
const fetchCompetitors = () => competitorsApi.list().then(r => r.data as { id: number; domain: string }[]);

// ─── New Session Form ───────────────────────────────────────────────────────────

function NewSessionForm({
  competitors,
  onSubmit,
  onClose,
}: {
  competitors: { id: number; domain: string }[];
  onSubmit: (sessionId: string) => void;
  onClose: () => void;
}) {
  const { toast }                 = useToast();
  const [question, setQuestion]   = useState("");
  const [domain, setDomain]       = useState<DomainProfile>("general");
  const [competitorId, setCompId] = useState<string>("");
  const [busy, setBusy]           = useState(false);

  const needsCompetitor = domain !== "general";
  const charCount       = question.length;

  const handleSubmit = async () => {
    if (charCount < 10)                   { toast("Question must be at least 10 characters", "error"); return; }
    if (needsCompetitor && !competitorId) { toast("Please select a competitor", "error");              return; }
    setBusy(true);
    try {
      const { data } = await councilApi.createSession({
        question,
        domain_profile: domain,
        competitor_id: competitorId ? Number(competitorId) : undefined,
      });
      toast("Council session started — advisors are deliberating", "success");
      onSubmit(data.session_id);
      onClose();
    } catch {
      toast("Failed to start council session", "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      style={{
        position: "fixed", inset: 0, zIndex: 9999,
        background: "rgba(0,0,0,0.78)", backdropFilter: "blur(4px)",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}
      onClick={e => e.target === e.currentTarget && onClose()}
    >
      <div className="card" style={{ width: 520, padding: "var(--sp-8)", maxHeight: "90vh", overflowY: "auto" }}>
        {/* Header */}
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: "var(--sp-6)" }}>
          <div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--accent)", letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 6 }}>
              LLM Council
            </div>
            <h2 style={{ fontSize: 16, fontWeight: 700, margin: 0 }}>Ask the Council</h2>
          </div>
          <button onClick={onClose} style={{ background: "transparent", border: "none", cursor: "pointer", color: "var(--text-muted)", padding: 4 }}>
            <X size={16} />
          </button>
        </div>

        {/* Question textarea */}
        <label style={{ display: "block", marginBottom: "var(--sp-5)" }}>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 6 }}>
            Your Question
          </div>
          <textarea
            value={question}
            onChange={e => setQuestion(e.target.value)}
            placeholder="e.g. Should we prioritize Instagram engagement over TikTok given competitor trends?"
            rows={4}
            maxLength={2000}
            style={{
              width: "100%", boxSizing: "border-box", resize: "vertical",
              background: "var(--bg-secondary)", border: "1px solid var(--border)",
              color: "var(--text-primary)", borderRadius: 6, padding: "10px 12px",
              fontFamily: "var(--font-mono)", fontSize: 12, lineHeight: 1.6,
            }}
          />
          <div style={{ textAlign: "right", fontSize: 10, color: charCount > 1800 ? "var(--danger)" : "var(--text-muted)", marginTop: 4 }}>
            {charCount}/2000
          </div>
        </label>

        {/* Domain profile grid */}
        <div style={{ marginBottom: "var(--sp-5)" }}>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 8 }}>
            Data Context
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
            {DOMAIN_OPTIONS.map(opt => (
              <label key={opt.value} style={{
                display: "flex", alignItems: "flex-start", gap: 8,
                padding: "8px 10px", borderRadius: 6, cursor: "pointer",
                border: `1px solid ${domain === opt.value ? "var(--accent)" : "var(--border)"}`,
                background: domain === opt.value ? "rgba(255,184,0,0.05)" : "transparent",
                transition: "all 0.15s",
              }}>
                <input
                  type="radio" name="domain" value={opt.value}
                  checked={domain === opt.value}
                  onChange={() => { setDomain(opt.value); setCompId(""); }}
                  style={{ marginTop: 2, accentColor: "var(--accent)", flexShrink: 0 }}
                />
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 2 }}>{opt.label}</div>
                  <div style={{ fontSize: 10, color: "var(--text-muted)", lineHeight: 1.4 }}>{opt.desc}</div>
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* Competitor selector */}
        {needsCompetitor && (
          <label style={{ display: "block", marginBottom: "var(--sp-5)" }}>
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

        {/* Buttons */}
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button
            className="btn btn-primary"
            onClick={handleSubmit}
            disabled={busy}
            style={{ display: "flex", alignItems: "center", gap: 6, opacity: busy ? 0.7 : 1 }}
          >
            {busy
              ? <RefreshCw size={13} style={{ animation: "spin 1s linear infinite" }} />
              : <Brain size={13} />}
            {busy ? "Starting…" : "Convene Council"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Session Detail Viewer ──────────────────────────────────────────────────────

function SessionViewer({ sessionId, onClose }: { sessionId: string; onClose: () => void }) {
  const [session,  setSession] = useState<SessionDetail | null>(null);
  const [loadErr,  setLoadErr] = useState<string | null>(null);
  const intervalRef            = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchSession = async () => {
    try {
      const { data } = await councilApi.getSession(sessionId);
      setSession(data);
      if (data.status === "completed" || data.status === "failed") {
        if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null; }
      }
    } catch {
      setLoadErr("Failed to load session");
      if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null; }
    }
  };

  useEffect(() => {
    fetchSession();
    intervalRef.current = setInterval(fetchSession, 3000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  const status = session?.status;
  const cfg    = status ? STATUS_CONFIG[status] : null;

  return (
    <div
      style={{
        position: "fixed", inset: 0, zIndex: 9999,
        background: "rgba(0,0,0,0.88)", backdropFilter: "blur(6px)",
        display: "flex", flexDirection: "column",
      }}
      onClick={e => e.target === e.currentTarget && onClose()}
    >
      <div style={{
        flex: 1, display: "flex", flexDirection: "column",
        margin: 24, borderRadius: 12, overflow: "hidden",
        background: "var(--bg-primary)", border: "1px solid var(--border)",
      }}>
        {/* Toolbar */}
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "14px 24px", borderBottom: "1px solid var(--border)", flexShrink: 0,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <Brain size={16} color="var(--accent)" />
            <div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.1em" }}>
                Council Session
              </div>
              <div style={{ fontSize: 13, fontWeight: 600, marginTop: 2, maxWidth: 560, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {session?.question ?? "Loading…"}
              </div>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            {cfg && (
              <div style={{ display: "flex", alignItems: "center", gap: 6, color: cfg.color, fontFamily: "var(--font-mono)", fontSize: 11 }}>
                {cfg.icon} {cfg.label}
              </div>
            )}
            <button onClick={onClose} style={{ background: "transparent", border: "none", cursor: "pointer", color: "var(--text-muted)", padding: 4 }}>
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
          {loadErr && (
            <div style={{ padding: 32, color: "var(--danger)", fontFamily: "var(--font-mono)", fontSize: 12 }}>{loadErr}</div>
          )}

          {!loadErr && !session && (
            <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
              <RefreshCw size={20} color="var(--text-muted)" style={{ animation: "spin 1s linear infinite" }} />
            </div>
          )}

          {!loadErr && session && (status === "pending" || status === "running") && (
            <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 16 }}>
              <Loader size={36} color="var(--accent)" style={{ animation: "spin 1s linear infinite" }} />
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--text-muted)" }}>Advisors are deliberating…</div>
              <div style={{ fontSize: 11, color: "var(--text-muted)", opacity: 0.55 }}>Typically 30–90 seconds</div>
            </div>
          )}

          {!loadErr && session?.status === "failed" && (
            <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 12 }}>
              <AlertCircle size={36} color="var(--danger)" />
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--danger)" }}>Council session failed</div>
              {session.error_message && (
                <code style={{ fontSize: 11, color: "var(--text-muted)", background: "var(--bg-secondary)", padding: "8px 16px", borderRadius: 6, maxWidth: 500, wordBreak: "break-all" }}>
                  {session.error_message}
                </code>
              )}
            </div>
          )}

          {!loadErr && session?.status === "completed" && session.html_report && (
            <iframe
              srcDoc={session.html_report}
              style={{ flex: 1, border: "none", width: "100%", height: "100%" }}
              sandbox="allow-same-origin allow-scripts"
              title="Council Report"
            />
          )}

          {!loadErr && session?.status === "completed" && !session.html_report && (
            <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: 12 }}>
              Report unavailable
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Main Page ─────────────────────────────────────────────────────────────────

export default function CouncilPage() {
  const { data: sessions = [], isLoading, mutate } =
    useSWR("council-sessions", fetchSessions, { refreshInterval: 5000 });

  const { data: competitors = [] } =
    useSWR("competitors", fetchCompetitors);

  const [showForm,      setShowForm]     = useState(false);
  const [activeSession, setActiveSession] = useState<string | null>(null);

  const stats = {
    total:      sessions.length,
    completed:  sessions.filter(s => s.status === "completed").length,
    inProgress: sessions.filter(s => s.status === "pending" || s.status === "running").length,
    failed:     sessions.filter(s => s.status === "failed").length,
  };

  const handleNewSession = (id: string) => {
    mutate();
    setActiveSession(id);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-8)" }} className="animate-in">
      {/* Page header */}
      <div className="page-header">
        <div>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 6 }}>
            Module 09 — LLM Council
          </div>
          <h1 className="page-title">Council</h1>
        </div>
        <button
          className="btn btn-primary"
          style={{ display: "flex", alignItems: "center", gap: 8 }}
          onClick={() => setShowForm(true)}
        >
          <Plus size={14} />
          Ask the Council
        </button>
      </div>

      {/* Stats row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "var(--sp-4)" }}>
        {[
          { label: "Total Sessions", value: stats.total,      color: "var(--text-primary)" },
          { label: "Completed",       value: stats.completed,  color: "#10b981" },
          { label: "In Progress",     value: stats.inProgress, color: "#3b82f6" },
          { label: "Failed",          value: stats.failed,     color: "#ef4444" },
        ].map(s => (
          <div key={s.label} className="card" style={{ padding: "var(--sp-5)" }}>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 8 }}>
              {s.label}
            </div>
            <div style={{ fontSize: 24, fontWeight: 700, fontFamily: "var(--font-mono)", color: s.color }}>
              {s.value}
            </div>
          </div>
        ))}
      </div>

      {/* Session history */}
      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 20px", borderBottom: "1px solid var(--border)" }}>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em" }}>
            Session History
          </span>
          <button onClick={() => mutate()} style={{ background: "transparent", border: "none", cursor: "pointer", color: "var(--text-muted)" }} title="Refresh">
            <RefreshCw size={13} />
          </button>
        </div>

        {isLoading ? (
          <div style={{ padding: "2rem", textAlign: "center", color: "var(--text-muted)" }}>Loading…</div>
        ) : sessions.length === 0 ? (
          <div style={{ padding: "3rem", textAlign: "center", color: "var(--text-muted)" }}>
            <Brain size={32} style={{ marginBottom: 12, opacity: 0.3, display: "block", margin: "0 auto 12px" }} />
            No sessions yet. Click <strong>Ask the Council</strong> to begin.
          </div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Question</th>
                <th>Domain</th>
                <th>Status</th>
                <th>Created</th>
                <th>Completed</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map(s => {
                const cfg = STATUS_CONFIG[s.status];
                return (
                  <tr key={s.id} style={{ cursor: "pointer" }} onClick={() => setActiveSession(s.id)}>
                    <td style={{ maxWidth: 360 }}>
                      <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontWeight: 500 }}>
                        {s.question}
                      </div>
                    </td>
                    <td>
                      <code style={{ fontSize: 10, color: "var(--text-secondary)", background: "rgba(0,0,0,0.25)", padding: "2px 7px", borderRadius: 4 }}>
                        {s.domain_profile}
                      </code>
                    </td>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: 6, color: cfg.color, fontFamily: "var(--font-mono)", fontSize: 11 }}>
                        {cfg.icon} {cfg.label}
                      </div>
                    </td>
                    <td style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: 11, whiteSpace: "nowrap" }}>
                      {new Date(s.created_at).toLocaleString()}
                    </td>
                    <td style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: 11, whiteSpace: "nowrap" }}>
                      {s.completed_at ? new Date(s.completed_at).toLocaleString() : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Modals */}
      {showForm && (
        <NewSessionForm
          competitors={competitors}
          onSubmit={handleNewSession}
          onClose={() => setShowForm(false)}
        />
      )}
      {activeSession && (
        <SessionViewer
          sessionId={activeSession}
          onClose={() => { setActiveSession(null); mutate(); }}
        />
      )}

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
