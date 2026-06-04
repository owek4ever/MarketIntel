"use client";
import useSWR from "swr";
import { useState } from "react";
import { marketApi } from "@/lib/api";
import { ShoppingBag, Search, LayoutDashboard, Box } from "lucide-react";

const fetchScores = () => marketApi.scores().then(r => r.data);
const searchFetcher = ([q, cid]: [string, number | undefined]) => marketApi.search(q, cid).then(r => r.data);

export default function MarketPage() {
  const [tab, setTab] = useState<"overview" | "search">("overview");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
        <ShoppingBag size={22} color="var(--accent)" />
        <div>
          <h1 style={{ margin: 0, fontSize: "1.4rem", fontWeight: 700 }}>Market & Products</h1>
          <p style={{ margin: 0, color: "var(--text-muted)", fontSize: "0.875rem" }}>Coverage, assortment, and availability scores</p>
        </div>
      </div>

      <div style={{ display: "flex", gap: "0.5rem", borderBottom: "1px solid var(--border)", paddingBottom: "0.5rem" }}>
        <button className={`btn ${tab === "overview" ? "btn-primary" : "btn-ghost"}`} onClick={() => setTab("overview")}>
          <LayoutDashboard size={14} /> Score Overview
        </button>
        <button className={`btn ${tab === "search" ? "btn-primary" : "btn-ghost"}`} onClick={() => setTab("search")}>
          <Search size={14} /> Semantic Product Search
        </button>
      </div>

      {tab === "overview" && <ScoresTab />}
      {tab === "search" && <SearchTab />}
    </div>
  );
}

function ScoresTab() {
  const { data, isLoading } = useSWR("market-scores", fetchScores);

  if (isLoading) return <div style={{ color: "var(--text-muted)", padding: "2rem" }}>Loading market data…</div>;

  return (
    <div className="card" style={{ padding: 0, overflow: "hidden" }}>
      <table className="table">
        <thead>
          <tr>
            <th>Domain</th>
            <th>Coverage</th>
            <th>Availability</th>
            <th>Market Score</th>
          </tr>
        </thead>
        <tbody>
          {(data ?? []).map((d: any, i: number) => {
            const score = parseFloat(d.final_score) || 0;
            const color = score >= 75 ? "var(--success)" : score >= 50 ? "var(--warning)" : "var(--danger)";
            return (
              <tr key={i}>
                <td style={{ fontWeight: 600 }}>{d.competitor_domain}</td>
                <td>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <div className="score-bar-track" style={{ width: 80 }}>
                      <div className="score-bar-fill" style={{ width: `${Math.min(parseFloat(d.coverage_score) || 0, 100)}%` }} />
                    </div>
                    <span style={{ fontSize: "0.8rem" }}>{parseFloat(d.coverage_score)?.toFixed(1) ?? "—"}%</span>
                  </div>
                </td>
                <td>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <div className="score-bar-track" style={{ width: 80 }}>
                      <div className="score-bar-fill" style={{ width: `${Math.min(parseFloat(d.availability_score) || 0, 100)}%`, background: "var(--success)" }} />
                    </div>
                    <span style={{ fontSize: "0.8rem" }}>{parseFloat(d.availability_score)?.toFixed(1) ?? "—"}%</span>
                  </div>
                </td>
                <td style={{ fontWeight: 700, color }}>{score.toFixed(1)}</td>
              </tr>
            );
          })}
          {!data?.length && (
            <tr><td colSpan={4} style={{ textAlign: "center", color: "var(--text-muted)", padding: "2rem" }}>
              No market data yet — crawl product pages first.
            </td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function SearchTab() {
  const [query, setQuery] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  
  const { data, isLoading } = useSWR(searchQuery.length >= 2 ? [searchQuery, undefined] : null, searchFetcher);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      <div className="card" style={{ display: "flex", gap: "0.5rem" }}>
        <input 
          className="input" 
          style={{ flex: 1 }} 
          placeholder="Search products (e.g., 'wireless headphones')" 
          value={query} 
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => e.key === "Enter" && setSearchQuery(query)}
        />
        <button className="btn btn-primary" onClick={() => setSearchQuery(query)}>
          Search
        </button>
      </div>

      {isLoading && <div style={{ color: "var(--text-muted)", padding: "1rem" }}>Searching...</div>}

      {data?.results && (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <div style={{ padding: "1rem", fontSize: "0.8rem", color: "var(--text-muted)", borderBottom: "1px solid var(--border)" }}>
            Found {data.results.length} results (Mode: {data.mode})
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Product</th>
                <th>Brand / Category</th>
                <th>Competitor</th>
                <th>Price</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((p: any) => (
                <tr key={p.id}>
                  <td>
                    <div style={{ fontWeight: 600, maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={p.title}>
                      <Box size={14} style={{ display: "inline-block", marginRight: 6, verticalAlign: "text-bottom", color: "var(--text-muted)" }} />
                      {p.title}
                    </div>
                  </td>
                  <td style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>
                    {p.brand ?? "Unknown"} / {p.category ?? "General"}
                  </td>
                  <td><span className="badge badge-blue">{p.competitor_domain}</span></td>
                  <td style={{ fontWeight: 600 }}>{p.current_price ? `$${parseFloat(p.current_price).toFixed(2)}` : "—"}</td>
                  <td>
                    <span className={`badge ${p.in_stock ? "badge-green" : "badge-red"}`}>
                      {p.in_stock ? "In Stock" : "Out of Stock"}
                    </span>
                  </td>
                </tr>
              ))}
              {data.results.length === 0 && (
                <tr><td colSpan={5} style={{ textAlign: "center", padding: "2rem", color: "var(--text-muted)" }}>No products found.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
