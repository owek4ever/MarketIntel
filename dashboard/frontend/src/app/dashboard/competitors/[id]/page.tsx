"use client";
import useSWR from "swr";
import { useParams } from "next/navigation";
import { competitorsApi } from "@/lib/api";
import { useState } from "react";
import React from "react";
import { Globe, FileText, ShoppingBag, LayoutDashboard, TrendingUp, Download } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { marketApi } from "@/lib/api";

const fetcher = (id: number) => competitorsApi.get(id).then(r => r.data);
const pagesFetcher = (id: number, page: number) => competitorsApi.pages(id, page).then(r => r.data);
const productsFetcher = (id: number, page: number) => competitorsApi.products(id, page).then(r => r.data);

export default function CompetitorDetailPage() {
  const params = useParams();
  const id = parseInt(params.id as string, 10);
  const [tab, setTab] = useState<"overview" | "pages" | "products">("overview");

  const { data, isLoading } = useSWR(["competitor", id], () => fetcher(id));

  if (isLoading) return <div style={{ padding: "2rem", color: "var(--text-muted)" }}>Loading competitor data…</div>;
  if (!data) return <div style={{ padding: "2rem", color: "var(--danger)" }}>Competitor not found.</div>;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
        <Globe size={22} color="var(--accent)" />
        <div>
          <h1 style={{ margin: 0, fontSize: "1.4rem", fontWeight: 700 }}>{data.domain}</h1>
          <p style={{ margin: 0, color: "var(--text-muted)", fontSize: "0.875rem" }}>{data.name || "Unknown Company"}</p>
        </div>
      </div>

      <div style={{ display: "flex", gap: "0.5rem", borderBottom: "1px solid var(--border)", paddingBottom: "0.5rem" }}>
        <button className={`btn ${tab === "overview" ? "btn-primary" : "btn-ghost"}`} onClick={() => setTab("overview")}>
          <LayoutDashboard size={14} /> Overview
        </button>
        <button className={`btn ${tab === "pages" ? "btn-primary" : "btn-ghost"}`} onClick={() => setTab("pages")}>
          <FileText size={14} /> Pages
        </button>
        <button className={`btn ${tab === "products" ? "btn-primary" : "btn-ghost"}`} onClick={() => setTab("products")}>
          <ShoppingBag size={14} /> Products
        </button>
      </div>

      {tab === "overview" && <OverviewTab data={data} />}
      {tab === "pages" && <PagesTab id={id} />}
      {tab === "products" && <ProductsTab id={id} />}
    </div>
  );
}

function OverviewTab({ data }: { data: any }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: "1rem" }}>
      <div className="card">
        <h2 style={{ margin: "0 0 1rem", fontSize: "0.95rem", fontWeight: 600 }}>SEO Summary</h2>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          <ScoreRow label="Avg SEO Score" value={data.avg_seo_score} />
          <ScoreRow label="Content Score" value={data.avg_content_score} />
          <ScoreRow label="On-Page Score" value={data.avg_on_page_score} />
          <ScoreRow label="Technical Score" value={data.avg_technical_score} />
          <ScoreRow label="UX Score" value={data.avg_ux_score} />
        </div>
      </div>
      <div className="card">
        <h2 style={{ margin: "0 0 1rem", fontSize: "0.95rem", fontWeight: 600 }}>Performance & Market</h2>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          <ScoreRow label="Avg Perf Score" value={data.avg_perf_score ? parseFloat(data.avg_perf_score) * 100 : null} />
          <ScoreRow label="Market Score" value={data.market_score} />
          <ScoreRow label="Coverage Score" value={data.coverage_score} />
          <ScoreRow label="Availability Score" value={data.availability_score} />
        </div>
      </div>
    </div>
  );
}

function ScoreRow({ label, value }: { label: string; value: string | number | null }) {
  const v = typeof value === "string" ? parseFloat(value) : value;
  const color = (v ?? 0) >= 75 ? "var(--success)" : (v ?? 0) >= 50 ? "var(--warning)" : "var(--danger)";
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
      <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>{label}</span>
      <span style={{ fontWeight: 600, color: value == null ? "var(--text-muted)" : color }}>
        {value == null ? "—" : v?.toFixed(1)}
      </span>
    </div>
  );
}

function PagesTab({ id }: { id: number }) {
  const [page, setPage] = useState(1);
  const { data, isLoading } = useSWR(["competitor-pages", id, page], () => pagesFetcher(id, page));

  if (isLoading) return <div style={{ padding: "1rem", color: "var(--text-muted)" }}>Loading pages…</div>;

  return (
    <div className="card" style={{ padding: 0, overflow: "hidden" }}>
      <table className="table">
        <thead>
          <tr>
            <th>URL</th>
            <th>Type</th>
            <th>SEO</th>
            <th>Perf</th>
            <th>Overall</th>
          </tr>
        </thead>
        <tbody>
          {(data?.items ?? []).map((p: any) => (
            <tr key={p.url_hash}>
              <td style={{ maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={p.url}>
                {p.url}
              </td>
              <td><span className="badge badge-blue">{p.page_type}</span></td>
              <td style={{ color: "var(--text-muted)" }}>{p.seo_score ? parseFloat(p.seo_score).toFixed(1) : "—"}</td>
              <td style={{ color: "var(--text-muted)" }}>{p.page_speed_score ? (parseFloat(p.page_speed_score) * 100).toFixed(1) : "—"}</td>
              <td style={{ fontWeight: 600 }}>{p.overall_score ? parseFloat(p.overall_score).toFixed(1) : "—"}</td>
            </tr>
          ))}
          {data?.items.length === 0 && <tr><td colSpan={5} style={{ textAlign: "center", padding: "1rem" }}>No pages found.</td></tr>}
        </tbody>
      </table>
      <div style={{ display: "flex", justifyContent: "space-between", padding: "1rem" }}>
        <button className="btn btn-ghost" disabled={page === 1} onClick={() => setPage(p => p - 1)}>Previous</button>
        <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>Page {page}</span>
        <button className="btn btn-ghost" disabled={data?.items.length < data?.page_size} onClick={() => setPage(p => p + 1)}>Next</button>
      </div>
    </div>
  );
}

function ProductsTab({ id }: { id: number }) {
  const [page, setPage] = useState(1);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const { data, isLoading } = useSWR(["competitor-products", id, page], () => productsFetcher(id, page));

  if (isLoading) return <div style={{ padding: "1rem", color: "var(--text-muted)" }}>Loading products…</div>;

  return (
    <div className="card" style={{ padding: 0, overflow: "hidden" }}>
      <table className="table">
        <thead>
          <tr>
            <th>Title</th>
            <th>Brand</th>
            <th>Price</th>
            <th>Status</th>
            <th style={{ width: 50 }}></th>
          </tr>
        </thead>
        <tbody>
          {(data?.items ?? []).map((p: any) => (
            <React.Fragment key={p.id}>
              <tr style={{ cursor: "pointer" }} onClick={() => setExpandedId(expandedId === p.id ? null : p.id)}>
                <td style={{ maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={p.title}>
                  {p.title}
                </td>
                <td style={{ color: "var(--text-muted)" }}>{p.brand ?? "—"}</td>
                <td style={{ fontWeight: 600 }}>{p.current_price ? `$${parseFloat(p.current_price).toFixed(2)}` : "—"}</td>
                <td>
                  <span className={`badge ${p.in_stock ? "badge-green" : "badge-red"}`}>
                    {p.in_stock ? "In Stock" : "Out of Stock"}
                  </span>
                </td>
                <td style={{ textAlign: "center" }}>
                  <TrendingUp size={16} color="var(--text-muted)" />
                </td>
              </tr>
              {expandedId === p.id && (
                <tr>
                  <td colSpan={5} style={{ padding: 0, background: "rgba(0,0,0,0.2)" }}>
                    <PriceChart productId={p.id} />
                  </td>
                </tr>
              )}
            </React.Fragment>
          ))}
          {data?.items.length === 0 && <tr><td colSpan={5} style={{ textAlign: "center", padding: "1rem" }}>No products found.</td></tr>}
        </tbody>
      </table>
      <div style={{ display: "flex", justifyContent: "space-between", padding: "1rem" }}>
        <button className="btn btn-ghost" disabled={page === 1} onClick={() => setPage(p => p - 1)}>Previous</button>
        <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>Page {page}</span>
        <button className="btn btn-ghost" disabled={data?.items.length < data?.page_size} onClick={() => setPage(p => p + 1)}>Next</button>
      </div>
    </div>
  );
}

function PriceChart({ productId }: { productId: number }) {
  const { data, isLoading } = useSWR(["price-history", productId], () => marketApi.priceHistory(productId).then(r => r.data));

  if (isLoading) return <div style={{ padding: "2rem", textAlign: "center", color: "var(--text-muted)", fontSize: 11, fontFamily: "var(--font-mono)" }}>LOADING PRICE HISTORY...</div>;
  if (!data || data.length === 0) return <div style={{ padding: "2rem", textAlign: "center", color: "var(--text-muted)", fontSize: 11, fontFamily: "var(--font-mono)" }}>NO PRICE HISTORY FOUND.</div>;

  const chartData = data.map((d: any) => ({
    date: new Date(d.recorded_at).toLocaleDateString(),
    price: parseFloat(d.price)
  })).reverse();

  return (
    <div style={{ padding: "1.5rem", borderTop: "1px solid var(--border)", borderBottom: "1px solid var(--border)" }}>
      <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", marginBottom: "1rem" }}>PRICE TRACKER</div>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
          <XAxis dataKey="date" tick={{ fill: "var(--text-muted)", fontSize: 10 }} axisLine={false} tickLine={false} />
          <YAxis domain={['auto', 'auto']} tick={{ fill: "var(--text-muted)", fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={(val) => `$${val}`} />
          <Tooltip
            contentStyle={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: 0, fontSize: 12 }}
            itemStyle={{ color: "var(--accent)", fontWeight: "bold" }}
            formatter={(value: any) => [`$${value}`, "Price"]}
          />
          <Line type="stepAfter" dataKey="price" stroke="var(--accent)" strokeWidth={2} dot={{ r: 3, fill: "var(--accent)" }} activeDot={{ r: 5 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
