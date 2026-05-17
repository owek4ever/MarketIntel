CREATE MATERIALIZED VIEW page_overall_scores AS
SELECT
    p.url_hash,
    p.competitor_id,

    seo.overall_score AS seo_score,
    ROUND(perf.page_speed_score * 100, 2) AS page_speed_score,

    -- weighted final score
    ROUND(
        (
            COALESCE(seo.overall_score, 0) * 0.7 +
            COALESCE(ROUND(perf.page_speed_score * 100, 2), 0) * 0.3
        )::numeric,
        4
    ) AS overall_score

FROM pages p
LEFT JOIN page_seo_scores seo ON seo.page_url_hash = p.url_hash
LEFT JOIN page_performance_scores perf ON perf.url_hash = p.url_hash;

CREATE MATERIALIZED VIEW competitor_page_scores AS
SELECT
    competitor_id,

    COUNT(*) AS total_pages,

    ROUND(AVG(overall_score), 4) AS avg_score,

    ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY overall_score))::NUMERIC, 4) AS median_score,

    ROUND(MIN(overall_score), 4) AS worst_page_score,
    ROUND(MAX(overall_score), 4) AS best_page_score

FROM page_performance_scores
GROUP BY competitor_id;

CREATE MATERIALIZED VIEW page_type_scores AS
SELECT
    p.competitor_id,
    page_type,
    AVG(overall_score)
FROM page_overall_scores pos
JOIN pages p USING (url_hash)
GROUP BY p.competitor_id, page_type;

CREATE MATERIALIZED VIEW competitor_gap_matrix AS
SELECT
    a.domain AS domain_a,
    a.competitor_id AS competitor_a,
    b.domain AS domain_b,
    b.competitor_id AS competitor_b,

    (a.avg_seo_score - b.avg_seo_score) AS seo_gap,
    (a.avg_content_score - b.avg_content_score) AS content_gap,
    (a.avg_on_page_score - b.avg_on_page_score) AS on_page_gap,
    (a.avg_technical_score - b.avg_technical_score) AS technical_gap,
    (a.avg_ux_score - b.avg_ux_score) AS ux_gap

FROM competitor_seo_summary a
JOIN competitor_seo_summary b
  ON a.competitor_id != b.competitor_id;

CREATE INDEX idx_competitor_gap_matrix_a
ON competitor_gap_matrix (competitor_a);

CREATE INDEX idx_competitor_gap_matrix_b
ON competitor_gap_matrix (competitor_b);