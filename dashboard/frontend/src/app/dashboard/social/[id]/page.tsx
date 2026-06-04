"use client";
import useSWR from "swr";
import { useParams } from "next/navigation";
import { socialApi } from "@/lib/api";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from "recharts";

const timeSeriesFetcher = (id: number) => socialApi.timeSeries(id).then(r => r.data);
const postsFetcher = (id: number) => socialApi.posts(id).then(r => r.data);

const PLATFORM_COLORS: Record<string, string> = {
  facebook: "var(--info)", instagram: "#ec4899", tiktok: "var(--success)",
};

export default function SocialDetailPage() {
  const params = useParams();
  const id = parseInt(params.id as string, 10);

  const { data: timeseries, isLoading: tsLoading } = useSWR(["social-timeseries", id], () => timeSeriesFetcher(id));
  const { data: posts, isLoading: postsLoading } = useSWR(["social-posts", id], () => postsFetcher(id));

  // Transform time series data for Recharts (grouping by date)
  const chartData = (timeseries ?? []).reduce((acc: any[], curr: any) => {
    const date = new Date(curr.recorded_at).toLocaleDateString();
    let existing = acc.find(item => item.date === date);
    if (!existing) {
      existing = { date };
      acc.push(existing);
    }
    existing[curr.platform] = parseInt(curr.followers, 10);
    return acc;
  }, []).reverse();

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-8)" }} className="animate-in">
      <div className="page-header">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
          <div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 6 }}>
              Module 05 — Audience / Deep Dive
            </div>
            <h1 className="page-title">Social Detail #{id}</h1>
          </div>
        </div>
      </div>

      <div className="card" style={{ border: "1px solid var(--border)" }}>
        <div className="card-title">FOLLOWER GROWTH TIME SERIES</div>
        {tsLoading ? (
           <div style={{ padding: "1rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: 11 }}>LOADING...</div>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={chartData} margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
              <XAxis dataKey="date" tick={{ fill: "var(--text-muted)", fontSize: 10, fontFamily: "var(--font-mono)" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: "var(--text-muted)", fontSize: 10, fontFamily: "var(--font-mono)" }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: 0, fontFamily: "var(--font-mono)", fontSize: 11 }}
                itemStyle={{ fontSize: 12, fontWeight: "bold" }}
              />
              <Legend wrapperStyle={{ fontFamily: "var(--font-mono)", fontSize: 11 }} />
              {Object.keys(PLATFORM_COLORS).map(platform => (
                <Line key={platform} type="monotone" dataKey={platform} stroke={PLATFORM_COLORS[platform]} dot={false} strokeWidth={2} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

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
              {(posts ?? []).map((p: any) => {
                const color = PLATFORM_COLORS[p.platform] ?? "var(--text-secondary)";
                return (
                  <tr key={p.id}>
                    <td>
                      <span className="badge" style={{ background: "transparent", color, border: `1px solid ${color}` }}>{p.platform}</span>
                    </td>
                    <td style={{ maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      <a href={p.url} target="_blank" rel="noreferrer" style={{ color: "var(--text-primary)", textDecoration: "none" }}>
                        {p.content || "—"}
                      </a>
                    </td>
                    <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>{p.likes ?? 0}</td>
                    <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>{p.comments ?? 0}</td>
                    <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>{p.views ?? "—"}</td>
                    <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>
                      {new Date(p.posted_at).toLocaleDateString()}
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
    </div>
  );
}
