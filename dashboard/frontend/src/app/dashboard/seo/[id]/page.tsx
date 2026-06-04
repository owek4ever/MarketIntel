"use client";
import useSWR from "swr";
import { useParams } from "next/navigation";
import { seoApi, competitorsApi, reportsApi } from "@/lib/api";
import { AlertTriangle, CheckCircle, Info, BookmarkPlus } from "lucide-react";
import { useToast } from "@/components/ToastProvider";

const actionPlanFetcher = (id: number) => seoApi.actionPlan(id).then(r => r.data);
const topIssuesFetcher = (id: number) => seoApi.topIssues(id).then(r => r.data);
const compFetcher = (id: number) => competitorsApi.get(id).then(r => r.data);

export default function SeoActionPlanPage() {
  const params = useParams();
  const id = parseInt(params.id as string, 10);
  const { toast } = useToast();

  const { data: comp } = useSWR(["competitor", id], () => compFetcher(id));
  const { data: plan, isLoading: planLoading } = useSWR(["seo-action-plan", id], () => actionPlanFetcher(id));
  const { data: issues, isLoading: issuesLoading } = useSWR(["seo-top-issues", id], () => topIssuesFetcher(id));

  const handleSaveReport = async () => {
    try {
      await reportsApi.create(`SEO Action Plan #${id}`, { path: `/seo/${id}` });
      toast("Report saved successfully", "success");
    } catch {
      toast("Failed to save report", "error");
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-8)" }} className="animate-in">
      <div className="page-header">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
          <div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 6 }}>
              Module 03 — Analysis / Action Plan
            </div>
            <h1 className="page-title">{comp ? comp.domain : "Loading..."}</h1>
          </div>
          <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
            <button className="btn btn-primary" onClick={handleSaveReport} style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <BookmarkPlus size={14} /> Save Report
            </button>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.08em" }}>
                COMPETITOR ID
              </div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 14, color: "var(--text-primary)", fontWeight: 600 }}>
                {String(id).padStart(3, "0")}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem" }}>
        
        {/* Action Plan */}
        <div className="card" style={{ padding: 0, overflow: "hidden", border: "1px solid var(--border)" }}>
          <div className="card-title" style={{ padding: "1rem" }}>PRIORITIZED ACTION PLAN</div>
          {planLoading ? (
            <div style={{ padding: "1rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: 11 }}>LOADING...</div>
          ) : (
            <table className="table" style={{ margin: 0 }}>
              <thead>
                <tr>
                  <th>ISSUE</th>
                  <th style={{ textAlign: "right" }}>PAGES</th>
                  <th style={{ textAlign: "right" }}>PRIORITY</th>
                </tr>
              </thead>
              <tbody>
                {(plan ?? []).map((p: any, i: number) => {
                  const level = p.priority_level;
                  const color = level === "critical" ? "var(--danger)" : level === "high" ? "var(--warning)" : "var(--info)";
                  return (
                    <tr key={i}>
                      <td style={{ color: "var(--text-primary)", fontSize: "0.85rem", whiteSpace: "normal" }}>
                        {p.issue.replace(/_/g, " ")}
                      </td>
                      <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>{p.total_affected_pages}</td>
                      <td style={{ textAlign: "right" }}>
                        <span className="badge" style={{ color: color, borderColor: color, backgroundColor: "transparent" }}>
                          {level.toUpperCase()}
                        </span>
                      </td>
                    </tr>
                  );
                })}
                {!plan?.length && (
                  <tr><td colSpan={3} style={{ textAlign: "center", padding: "1rem", color: "var(--text-muted)" }}>No actions required.</td></tr>
                )}
              </tbody>
            </table>
          )}
        </div>

        {/* Top Issues */}
        <div className="card" style={{ padding: 0, overflow: "hidden", border: "1px solid var(--border)" }}>
          <div className="card-title" style={{ padding: "1rem" }}>TOP DETECTED ISSUES</div>
          {issuesLoading ? (
            <div style={{ padding: "1rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: 11 }}>LOADING...</div>
          ) : (
            <table className="table" style={{ margin: 0 }}>
              <thead>
                <tr>
                  <th>ISSUE</th>
                  <th style={{ textAlign: "right" }}>IMPACT</th>
                  <th style={{ textAlign: "right" }}>COVERAGE</th>
                </tr>
              </thead>
              <tbody>
                {(issues ?? []).map((p: any, i: number) => {
                  return (
                    <tr key={i}>
                      <td style={{ color: "var(--text-primary)", fontSize: "0.85rem", whiteSpace: "normal" }}>
                        {p.issue.replace(/_/g, " ")}
                      </td>
                      <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>
                        {parseFloat(p.total_impact).toFixed(1)}
                      </td>
                      <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>
                        {(parseFloat(p.coverage_ratio) * 100).toFixed(1)}%
                      </td>
                    </tr>
                  );
                })}
                {!issues?.length && (
                  <tr><td colSpan={3} style={{ textAlign: "center", padding: "1rem", color: "var(--text-muted)" }}>No issues found.</td></tr>
                )}
              </tbody>
            </table>
          )}
        </div>

      </div>
    </div>
  );
}
