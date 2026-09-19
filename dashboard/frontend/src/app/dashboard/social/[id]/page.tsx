"use client";
import useSWR from "swr";
import { useParams } from "next/navigation";
import { socialApi } from "@/lib/api";
import { useState } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend, AreaChart, Area } from "recharts";
import { BadgeCheck, ExternalLink, TrendingUp, BarChart3, Brain, Filter } from "lucide-react";

const PLATFORM_COLORS: Record<string, string> = {
  facebook: "var(--info)", instagram: "#ec4899", tiktok: "var(--success)",
};

export default function SocialDetailPage() {
  const params = useParams();
  const id = parseInt(params.id as string, 10);
  const [platform, setPlatform] = useState<string | undefined>(undefined);
  const [tab, setTab] = useState<"overview" | "forecast" | "accounts" | "ai">("overview");

  const { data: timeseries, isLoading: tsLoading } = useSWR(
    ["social-timeseries", id, platform],
    () => socialApi.timeSeries(id, platform).then(r => r.data)
  );
  const { data: posts, isLoading: postsLoading } = useSWR(
    ["social-posts", id, platform],
    () => socialApi.posts(id, platform).then(r => r.data)
  );
  const { data: forecast } = useSWR(
    ["social-forecast", id],
    () => socialApi.forecast(id).then(r => r.data)
  );
  const { data: accounts } = useSWR(
    ["social-accounts", id],
    () => socialApi.accounts(id).then(r => r.data)
  );
  const { data: aiAnalysis } = useSWR(
    ["social-ai", id],
    () => socialApi.aiAnalysis(id).then(r => r.data)
  );

  const chartData = (timeseries ?? []).reduce((acc: any[], curr: any) => {
    const date = new Date(curr.snapshot_date).toLocaleDateString();
    let existing = acc.find((item: any) => item.date === date);
    if (!existing) {
      existing = { date };
      acc.push(existing);
    }
    existing[curr.platform] = parseFloat(curr.score) * 100;
    return acc;
  }, []).reverse();

  const platforms = [...new Set((timeseries ?? []).map((t: any) => t.platform))] as string[];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-8)" }} className="animate-in">
      <div className="page-header">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
          <div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 6 }}>
              Module 05 — Audience / Deep Dive
            </div>
            <h1 className="page-title">Social Intelligence #{String(id).padStart(2, "0")}</h1>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <Filter size={13} color="var(--text-muted)" />
            <select
              value={platform ?? ""}
              onChange={(e) => setPlatform(e.target.value || undefined)}
              style={{ background: "var(--bg-base)", border: "1px solid var(--border)", color: "var(--text-primary)", padding: "4px 8px", fontSize: 11, fontFamily: "var(--font-mono)", borderRadius: 0 }}
            >
              <option value="">All Platforms</option>
              {platforms.map((p: string) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div style={{ display: "flex", gap: "0.5rem", borderBottom: "1px solid var(--border)", paddingBottom: "0.5rem" }}>
        {(["overview", "forecast", "accounts", "ai"] as const).map(t => (
          <button key={t} className={`btn ${tab === t ? "btn-primary" : "btn-ghost"}`} onClick={() => setTab(t)}>
            {t === "overview" && <BarChart3 size={14} />}
            {t === "forecast" && <TrendingUp size={14} />}
            {t === "accounts" && <BadgeCheck size={14} />}
            {t === "ai" && <Brain size={14} />}
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <>
          {/* Score Time Series Chart */}
          <div className="card" style={{ border: "1px solid var(--border)" }}>
            <div className="card-title">SCORE TIME SERIES</div>
            {tsLoading ? (
              <div style={{ padding: "1rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: 11 }}>LOADING...</div>
            ) : chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={chartData} margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                  <XAxis dataKey="date" tick={{ fill: "var(--text-muted)", fontSize: 10, fontFamily: "var(--font-mono)" }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: "var(--text-muted)", fontSize: 10, fontFamily: "var(--font-mono)" }} axisLine={false} tickLine={false} tickFormatter={(v) => `${v.toFixed(0)}%`} />
                  <Tooltip
                    contentStyle={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: 0, fontFamily: "var(--font-mono)", fontSize: 11 }}
                    formatter={(value: any) => [`${Number(value).toFixed(2)}%`, "Score"]}
                  />
                  <Legend wrapperStyle={{ fontFamily: "var(--font-mono)", fontSize: 11 }} />
                  {platforms.map((p: string) => (
                    <Line key={p} type="monotone" dataKey={p} stroke={PLATFORM_COLORS[p] ?? "var(--text-secondary)"} dot={false} strokeWidth={2} />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ padding: "2rem", textAlign: "center", color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: 11 }}>
                NO TIME SERIES DATA AVAILABLE
              </div>
            )}
          </div>

          {/* Recent Posts */}
          <div className="card" style={{ padding: 0, overflow: "hidden", border: "1px solid var(--border)" }}>
            <div className="card-title" style={{ padding: "1rem" }}>RECENT POSTS</div>
            {postsLoading ? (
              <div style={{ padding: "1rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: 11 }}>LOADING...</div>
            ) : (
              <table className="table" style={{ margin: 0 }}>
                <thead>
                  <tr>
                    <th>PLATFORM</th>
                    <th>CONTENT</th>
                    <th style={{ textAlign: "right" }}>LIKES</th>
                    <th style={{ textAlign: "right" }}>COMMENTS</th>
                    <th style={{ textAlign: "right" }}>VIEWS</th>
                    <th style={{ textAlign: "right" }}>POSTED</th>
                  </tr>
                </thead>
                <tbody>
                  {(posts ?? []).map((p: any, i: number) => {
                    const color = PLATFORM_COLORS[p.platform] ?? "var(--text-secondary)";
                    return (
                      <tr key={i}>
                        <td>
                          <span className="badge" style={{ background: "transparent", color, border: `1px solid ${color}` }}>{p.platform}</span>
                        </td>
                        <td style={{ maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          <a href={p.post_url} target="_blank" rel="noreferrer" style={{ color: "var(--text-primary)", textDecoration: "none" }}>
                            {p.text || "—"}
                          </a>
                        </td>
                        <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>{p.like_count ?? 0}</td>
                        <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>{p.comment_count ?? 0}</td>
                        <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>{p.view_count ?? "—"}</td>
                        <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>
                          {p.publish_time ? new Date(p.publish_time).toLocaleDateString() : "—"}
                        </td>
                      </tr>
                    );
                  })}
                  {!posts?.length && (
                    <tr><td colSpan={6} style={{ textAlign: "center", padding: "1rem", color: "var(--text-muted)" }}>No posts found.</td></tr>
                  )}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}

      {tab === "forecast" && (
        <div className="card" style={{ border: "1px solid var(--border)" }}>
          <div className="card-title">FORECAST MODELS</div>
          {forecast ? (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: "1rem", padding: "1rem" }}>
              {/* Momentum Forecast */}
              {forecast.momentum?.length > 0 && (
                <div style={{ border: "1px solid var(--border)", padding: "1rem" }}>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--accent)", marginBottom: 8, textTransform: "uppercase" }}>Momentum Model</div>
                  {forecast.momentum.slice(0, 5).map((f: any, i: number) => (
                    <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0", borderBottom: "1px solid var(--border)", fontSize: 11, fontFamily: "var(--font-mono)" }}>
                      <span style={{ color: "var(--text-muted)" }}>{f.platform}</span>
                      <span>7d: <span style={{ color: "var(--success)" }}>{(parseFloat(f.forecast_7d) * 100).toFixed(1)}%</span></span>
                    </div>
                  ))}
                </div>
              )}
              {/* Regression Forecast */}
              {forecast.regression?.length > 0 && (
                <div style={{ border: "1px solid var(--border)", padding: "1rem" }}>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--accent)", marginBottom: 8, textTransform: "uppercase" }}>Regression Model</div>
                  {forecast.regression.slice(0, 5).map((f: any, i: number) => (
                    <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0", borderBottom: "1px solid var(--border)", fontSize: 11, fontFamily: "var(--font-mono)" }}>
                      <span style={{ color: "var(--text-muted)" }}>{f.platform}</span>
                      <span>7d: <span style={{ color: "var(--success)" }}>{(parseFloat(f.forecast_score_7d) * 100).toFixed(1)}%</span></span>
                    </div>
                  ))}
                </div>
              )}
              {/* Smoothed Forecast */}
              {forecast.smoothed?.length > 0 && (
                <div style={{ border: "1px solid var(--border)", padding: "1rem" }}>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--accent)", marginBottom: 8, textTransform: "uppercase" }}>Smoothed Model</div>
                  {forecast.smoothed.slice(0, 5).map((f: any, i: number) => (
                    <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0", borderBottom: "1px solid var(--border)", fontSize: 11, fontFamily: "var(--font-mono)" }}>
                      <span style={{ color: "var(--text-muted)" }}>{f.platform}</span>
                      <span>7d: <span style={{ color: "var(--success)" }}>{(parseFloat(f.forecast_7d) * 100).toFixed(1)}%</span></span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div style={{ padding: "2rem", textAlign: "center", color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: 11 }}>
              NO FORECAST DATA AVAILABLE
            </div>
          )}
        </div>
      )}

      {tab === "accounts" && (
        <div className="card" style={{ padding: 0, overflow: "hidden", border: "1px solid var(--border)" }}>
          <div className="card-title" style={{ padding: "1rem" }}>SOCIAL ACCOUNTS</div>
          <table className="table" style={{ margin: 0 }}>
            <thead>
              <tr>
                <th>PLATFORM</th>
                <th>USERNAME</th>
                <th>DISPLAY NAME</th>
                <th style={{ textAlign: "right" }}>FOLLOWERS</th>
                <th style={{ textAlign: "right" }}>FOLLOWING</th>
                <th>VERIFIED</th>
                <th>LINK</th>
              </tr>
            </thead>
            <tbody>
              {(accounts ?? []).map((a: any, i: number) => {
                const color = PLATFORM_COLORS[a.platform] ?? "var(--text-secondary)";
                return (
                  <tr key={i}>
                    <td>
                      <span className="badge" style={{ background: "transparent", color, border: `1px solid ${color}` }}>{a.platform}</span>
                    </td>
                    <td style={{ fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>@{a.username}</td>
                    <td style={{ color: "var(--text-secondary)" }}>{a.display_name ?? "—"}</td>
                    <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontWeight: 600 }}>{a.follower_count?.toLocaleString() ?? "—"}</td>
                    <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>{a.following_count?.toLocaleString() ?? "—"}</td>
                    <td>{a.is_verified ? <BadgeCheck size={14} color="var(--accent)" /> : "—"}</td>
                    <td>
                      <a href={a.profile_url} target="_blank" rel="noreferrer" style={{ color: "var(--accent)" }}>
                        <ExternalLink size={13} />
                      </a>
                    </td>
                  </tr>
                );
              })}
              {!accounts?.length && (
                <tr><td colSpan={7} style={{ textAlign: "center", padding: "1rem", color: "var(--text-muted)" }}>No social accounts found.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {tab === "ai" && (
        <div className="card" style={{ border: "1px solid var(--border)" }}>
          <div className="card-title">AI ANALYSIS</div>
          {aiAnalysis?.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "1rem", padding: "1rem" }}>
              {aiAnalysis.map((a: any, i: number) => (
                <div key={i} style={{ border: "1px solid var(--border)", padding: "1rem" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                    <span className="badge" style={{ background: "transparent", color: PLATFORM_COLORS[a.platform] ?? "var(--text-secondary)", border: `1px solid ${PLATFORM_COLORS[a.platform] ?? "var(--text-secondary)"}` }}>{a.platform}</span>
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)" }}>{a.analysis_date}</span>
                  </div>
                  <div style={{ fontSize: 12, lineHeight: 1.6, color: "var(--text-secondary)" }}>
                    {typeof a.ai_summary === "string" ? a.ai_summary : JSON.stringify(a.ai_summary, null, 2)}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ padding: "2rem", textAlign: "center", color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: 11 }}>
              NO AI ANALYSIS AVAILABLE
            </div>
          )}
        </div>
      )}
    </div>
  );
}
