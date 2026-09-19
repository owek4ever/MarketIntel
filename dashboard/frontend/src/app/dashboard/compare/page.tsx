"use client";
import useSWR from "swr";
import { useState, useMemo } from "react";
import { api, comparisonApi, competitorsApi } from "@/lib/api";
import { GitCompare, BarChart3, TrendingUp, ShoppingBag, Share2, Globe, CheckCircle, XCircle, Minus } from "lucide-react";

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"];

function RadarBar({ label, values, max = 1 }: { label: string; values: (number | null)[]; max?: number }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "140px 1fr", alignItems: "center", gap: "var(--sp-3)", marginBottom: "var(--sp-2)" }}>
      <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-secondary)", textAlign: "right" }}>{label}</div>
      <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
        {values.map((v, i) => {
          const pct = v !== null ? Math.min((v / max) * 100, 100) : 0;
          return (
            <div key={i} style={{ flex: 1, display: "flex", alignItems: "center", gap: 6 }}>
              <div style={{ width: "100%", height: 16, background: "var(--border)", borderRadius: 3, overflow: "hidden" }}>
                <div style={{ width: `${pct}%`, height: "100%", background: COLORS[i], borderRadius: 3, transition: "width 0.5s" }} />
              </div>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: COLORS[i], minWidth: 32 }}>
                {v !== null ? (v * 100).toFixed(0) + "%" : "—"}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ScoreCard({ label, competitors, icon: Icon }: { label: string; competitors: any[]; icon: any }) {
  const values = competitors.map(c => {
    switch (label) {
      case "SEO": return c.avg_seo_score ? parseFloat(c.avg_seo_score) : null;
      case "Performance": return c.perf_score ? parseFloat(c.perf_score) : null;
      case "Social": return c.social_score ? parseFloat(c.social_score) : null;
      case "Market": return c.market_score ? parseFloat(c.market_score) : null;
      case "Composite": return c.composite_score;
      default: return null;
    }
  });
  const max = 1;
  return (
    <div className="card" style={{ padding: "var(--sp-4)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: "var(--sp-3)" }}>
        <Icon size={14} style={{ color: "var(--accent)" }} />
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-muted)", letterSpacing: "0.1em", textTransform: "uppercase" }}>{label}</span>
      </div>
      <div style={{ display: "flex", gap: "var(--sp-2)" }}>
        {competitors.map((c, i) => {
          const v = values[i];
          const best = Math.max(...values.filter(x => x !== null) as number[]);
          const isBest = v === best && v !== null;
          return (
            <div key={c.id} style={{ flex: 1, textAlign: "center" }}>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 20, fontWeight: 700, color: isBest ? "var(--success)" : COLORS[i] }}>
                {v !== null ? (v * 100).toFixed(1) + "%" : "—"}
              </div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--text-muted)", marginTop: 2 }}>{c.domain}</div>
              {isBest && <div style={{ fontFamily: "var(--font-mono)", fontSize: 8, color: "var(--success)" }}>BEST</div>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function ComparePage() {
  const { data: allCompetitors } = useSWR("competitors-list", () => competitorsApi.list().then(r => r.data), { refreshInterval: 30000 });
  const [selected, setSelected] = useState<number[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);

  const idsParam = selected.join(",");
  const { data: comparison, isLoading } = useSWR(
    selected.length >= 2 ? `compare-${idsParam}` : null,
    () => comparisonApi.compare(selected).then(r => r.data),
    { refreshInterval: 10000 }
  );

  const competitors = comparison ?? [];

  function toggle(id: number) {
    setSelected(prev => {
      if (prev.includes(id)) return prev.filter(x => x !== id);
      if (prev.length >= 5) return prev;
      return [...prev, id];
    });
  }

  const selectedComps = (allCompetitors ?? []).filter((c: any) => selected.includes(c.id));

  // Collect all categories across competitors
  const allCategories = useMemo(() => {
    const cats = new Map<string, number[]>();
    competitors.forEach((c: any, i: number) => {
      c.categories?.forEach((cat: any) => {
        if (!cats.has(cat.category)) cats.set(cat.category, new Array(competitors.length).fill(0));
        cats.get(cat.category)![i] = cat.count;
      });
    });
    return Array.from(cats.entries()).sort((a, b) => b[1].reduce((s, v) => s + v, 0) - a[1].reduce((s, v) => s + v, 0)).slice(0, 10);
  }, [competitors]);

  // Collect all social platforms
  const allPlatforms = useMemo(() => {
    const plats = new Map<string, number[]>();
    competitors.forEach((c: any, i: number) => {
      c.social_accounts?.forEach((sa: any) => {
        if (!plats.has(sa.platform)) plats.set(sa.platform, new Array(competitors.length).fill(0));
        plats.get(sa.platform)![i] = sa.followers;
      });
    });
    return Array.from(plats.entries());
  }, [competitors]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-6)" }} className="animate-in">

      {/* Header */}
      <div className="page-header">
        <div>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 6 }}>
            Analysis Module
          </div>
          <h1 className="page-title">Competitor Comparison</h1>
        </div>
      </div>

      {/* Selector */}
      <div className="card" style={{ padding: "var(--sp-4) var(--sp-5)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--sp-4)", flexWrap: "wrap" }}>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-muted)", letterSpacing: "0.1em" }}>
            SELECT COMPETITORS ({selected.length}/5):
          </div>
          <div style={{ position: "relative", flex: 1, minWidth: 300 }}>
            <button
              className="btn btn-ghost"
              onClick={() => setShowDropdown(!showDropdown)}
              style={{ width: "100%", justifyContent: "flex-start", border: "1px solid var(--border)", fontFamily: "var(--font-mono)", fontSize: 11 }}
            >
              {selected.length === 0 ? "Click to select competitors..." : `${selected.length} competitor(s) selected`}
            </button>
            {showDropdown && (
              <div style={{ position: "absolute", top: "100%", left: 0, right: 0, zIndex: 100, background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: 8, maxHeight: 300, overflowY: "auto", marginTop: 4 }}>
                {(allCompetitors ?? []).map((c: any) => {
                  const isSelected = selected.includes(c.id);
                  return (
                    <button
                      key={c.id}
                      onClick={() => toggle(c.id)}
                      style={{
                        display: "flex", alignItems: "center", gap: 8, width: "100%", padding: "8px 12px",
                        background: isSelected ? "var(--accent-dim)" : "transparent",
                        border: "none", cursor: "pointer", textAlign: "left",
                        fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-primary)",
                      }}
                    >
                      <div style={{ width: 16, height: 16, borderRadius: 3, border: `2px solid ${isSelected ? "var(--accent)" : "var(--border)"}`, display: "flex", alignItems: "center", justifyContent: "center", background: isSelected ? "var(--accent)" : "transparent" }}>
                        {isSelected && <CheckCircle size={10} style={{ color: "white" }} />}
                      </div>
                      <span>{c.name}</span>
                      <span style={{ color: "var(--text-muted)", marginLeft: "auto" }}>{c.domain}</span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
          {/* Selected chips */}
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {selectedComps.map((c: any, i: number) => (
              <div key={c.id} style={{ display: "flex", alignItems: "center", gap: 4, padding: "4px 10px", borderRadius: 4, background: COLORS[i] + "20", border: `1px solid ${COLORS[i]}40`, fontFamily: "var(--font-mono)", fontSize: 10, color: COLORS[i] }}>
                {c.domain}
                <button onClick={() => toggle(c.id)} style={{ background: "none", border: "none", cursor: "pointer", color: COLORS[i], padding: 0, display: "flex" }}>
                  <XCircle size={12} />
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>

      {selected.length < 2 && (
        <div className="card" style={{ padding: "var(--sp-8)", textAlign: "center" }}>
          <GitCompare size={40} style={{ color: "var(--text-muted)", marginBottom: "var(--sp-3)" }} />
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--text-muted)" }}>
            Select 2 or more competitors to compare
          </div>
        </div>
      )}

      {isLoading && selected.length >= 2 && (
        <div className="card" style={{ padding: "var(--sp-8)" }}>
          <div className="loading-bar" style={{ width: "100%", marginBottom: 16 }} />
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", textAlign: "center" }}>
            LOADING COMPARISON DATA...
          </div>
        </div>
      )}

      {competitors.length > 0 && (
        <>
          {/* Score Comparison */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "var(--sp-3)" }}>
            <ScoreCard label="SEO" competitors={competitors} icon={TrendingUp} />
            <ScoreCard label="Performance" competitors={competitors} icon={BarChart3} />
            <ScoreCard label="Social" competitors={competitors} icon={Share2} />
            <ScoreCard label="Market" competitors={competitors} icon={ShoppingBag} />
            <ScoreCard label="Composite" competitors={competitors} icon={Globe} />
          </div>

          {/* Detailed Score Bars */}
          <div className="card" style={{ padding: "var(--sp-5)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: "var(--sp-4)" }}>
              <BarChart3 size={14} style={{ color: "var(--accent)" }} />
              <span className="card-title" style={{ margin: 0 }}>DETAILED SCORES</span>
            </div>
            <RadarBar label="SEO Score" values={competitors.map(c => c.avg_seo_score ? parseFloat(c.avg_seo_score) : null)} />
            <RadarBar label="Content" values={competitors.map(c => c.avg_content_score ? parseFloat(c.avg_content_score) : null)} />
            <RadarBar label="On-Page" values={competitors.map(c => c.avg_on_page_score ? parseFloat(c.avg_on_page_score) : null)} />
            <RadarBar label="Technical" values={competitors.map(c => c.avg_technical_score ? parseFloat(c.avg_technical_score) : null)} />
            <RadarBar label="UX Score" values={competitors.map(c => c.avg_ux_score ? parseFloat(c.avg_ux_score) : null)} />
            <RadarBar label="Performance" values={competitors.map(c => c.perf_score ? parseFloat(c.perf_score) : null)} />
            <RadarBar label="Market" values={competitors.map(c => c.market_score ? parseFloat(c.market_score) : null)} />
            <RadarBar label="Social" values={competitors.map(c => c.social_score ? parseFloat(c.social_score) : null)} />
            <RadarBar label="Coverage" values={competitors.map(c => c.coverage_score ? parseFloat(c.coverage_score) : null)} />
            <RadarBar label="Assortment" values={competitors.map(c => c.assortment_score ? parseFloat(c.assortment_score) : null)} />
          </div>

          {/* Price + Products */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--sp-4)" }}>
            <div className="card" style={{ padding: "var(--sp-5)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: "var(--sp-4)" }}>
                <ShoppingBag size={14} style={{ color: "var(--accent)" }} />
                <span className="card-title" style={{ margin: 0 }}>PRICING</span>
              </div>
              <table className="table" style={{ margin: 0 }}>
                <thead>
                  <tr>
                    <th>COMPETITOR</th>
                    <th style={{ textAlign: "right" }}>AVG PRICE</th>
                    <th style={{ textAlign: "right" }}>MIN</th>
                    <th style={{ textAlign: "right" }}>MAX</th>
                    <th style={{ textAlign: "right" }}>PRODUCTS</th>
                  </tr>
                </thead>
                <tbody>
                  {competitors.map((c: any, i: number) => (
                    <tr key={c.id}>
                      <td style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: COLORS[i] }}>{c.domain}</td>
                      <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontSize: 11 }}>
                        {c.price_range?.avg_price ? `$${c.price_range.avg_price}` : "—"}
                      </td>
                      <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--success)" }}>
                        {c.price_range?.min_price ? `$${c.price_range.min_price}` : "—"}
                      </td>
                      <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--danger)" }}>
                        {c.price_range?.max_price ? `$${c.price_range.max_price}` : "—"}
                      </td>
                      <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontSize: 11 }}>
                        {c.product_count ?? 0}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="card" style={{ padding: "var(--sp-5)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: "var(--sp-4)" }}>
                <Share2 size={14} style={{ color: "var(--accent)" }} />
                <span className="card-title" style={{ margin: 0 }}>SOCIAL PRESENCE</span>
              </div>
              <table className="table" style={{ margin: 0 }}>
                <thead>
                  <tr>
                    <th>COMPETITOR</th>
                    {allPlatforms.map(([p]) => (
                      <th key={p} style={{ textAlign: "right", textTransform: "uppercase" }}>{p}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {competitors.map((c: any, i: number) => (
                    <tr key={c.id}>
                      <td style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: COLORS[i] }}>{c.domain}</td>
                      {allPlatforms.map(([platform]) => {
                        const sa = c.social_accounts?.find((s: any) => s.platform === platform);
                        return (
                          <td key={platform} style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontSize: 11 }}>
                            {sa ? (
                              <span style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 4 }}>
                                {sa.followers?.toLocaleString()}
                                {sa.verified && <CheckCircle size={10} style={{ color: "var(--accent)" }} />}
                              </span>
                            ) : "—"}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Category Breakdown */}
          {allCategories.length > 0 && (
            <div className="card" style={{ padding: "var(--sp-5)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: "var(--sp-4)" }}>
                <Globe size={14} style={{ color: "var(--accent)" }} />
                <span className="card-title" style={{ margin: 0 }}>TOP CATEGORIES</span>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-2)" }}>
                {allCategories.map(([category, counts]) => {
                  const maxCount = Math.max(...counts, 1);
                  return (
                    <div key={category} style={{ display: "grid", gridTemplateColumns: "140px 1fr", alignItems: "center", gap: "var(--sp-3)" }}>
                      <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-secondary)", textAlign: "right", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={category}>
                        {category}
                      </div>
                      <div style={{ display: "flex", gap: 4 }}>
                        {counts.map((count, i) => (
                          <div key={i} style={{ flex: 1, display: "flex", alignItems: "center", gap: 4 }}>
                            <div style={{ width: "100%", height: 14, background: "var(--border)", borderRadius: 2, overflow: "hidden" }}>
                              <div style={{ width: `${(count / maxCount) * 100}%`, height: "100%", background: COLORS[i], borderRadius: 2 }} />
                            </div>
                            <span style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: COLORS[i], minWidth: 20 }}>{count}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
