CREATE OR REPLACE VIEW page_seo_scores AS
WITH base AS (
    SELECT
        ps.id,
        ps.page_url_hash,

        COALESCE((ps.seo_flags->'scores'->>'content_score_percent')::NUMERIC, 70) AS content_score,
        COALESCE((ps.seo_flags->'scores'->>'on_page_score_percent')::NUMERIC, 70) AS on_page_score,
        COALESCE((ps.seo_flags->'scores'->>'technical_score_percent')::NUMERIC, 70) AS technical_score,
        COALESCE((ps.seo_flags->'scores'->>'overall_seo_score_percent')::NUMERIC, 70) AS overall_score,

        -- UX stays your only custom signal
        (
            (CASE WHEN ps.has_breadcrumbs THEN 100 ELSE 60 END) * 0.25 +
            (CASE WHEN (ps.bullet_list_count + ps.number_list_count) > 0 THEN 100 ELSE 70 END) * 0.20 +
            (CASE WHEN ps.avg_paragraph_word_count BETWEEN 40 AND 120 THEN 100 ELSE 50 END) * 0.25 +
            (CASE WHEN ps.internal_links_count > 10 THEN 100 ELSE 70 END) * 0.15 +
            (CASE WHEN ps.external_links_count > 0 THEN 100 ELSE 80 END) * 0.15
        ) AS ux_score

    FROM page_snapshots ps
)

SELECT
    id,
    page_url_hash,

    ROUND(content_score, 2) AS content_score,
    ROUND(on_page_score, 2) AS on_page_score,
    ROUND(technical_score, 2) AS technical_score,
    ROUND(overall_score, 2) AS overall_score,
    ROUND(ux_score, 2) AS ux_score,

    -- FINAL SCORE (simple weighted aggregation)
    ROUND(
        (
            overall_score * 0.50 +
            content_score * 0.20 +
            on_page_score * 0.15 +
            technical_score * 0.10 +
            ux_score * 0.05
        ),
        2
    ) AS page_seo_score

FROM base;

CREATE OR REPLACE VIEW competitor_seo_summary AS
WITH joined AS (
    SELECT
        p.competitor_id,
        c.domain AS domain,
        ps.page_seo_score,
        ps.content_score,
        ps.on_page_score,
        ps.technical_score,
        ps.ux_score,

        ps.seo_flags

    FROM page_seo_scores ps
    JOIN pages p
    JOIN competitors c ON c.id = p.competitor_id
        ON ps.page_url_hash = p.url_hash
)

SELECT
    competitor_id,
    domain,
    COUNT(*) AS total_pages,

    ROUND(AVG(page_seo_score), 2) AS avg_seo_score,
    ROUND(AVG(content_score), 2) AS avg_content_score,
    ROUND(AVG(on_page_score), 2) AS avg_on_page_score,
    ROUND(AVG(technical_score), 2) AS avg_technical_score,
    ROUND(AVG(ux_score), 2) AS avg_ux_score

FROM joined
GROUP BY competitor_id;

CREATE MATERIALIZED VIEW competitor_seo_summary AS
SELECT
    p.competitor_id,
    c.domain AS domain,
    COUNT(*) AS total_pages,

    ROUND(AVG(ps.page_seo_score)::NUMERIC, 2) AS avg_seo_score,

    ROUND(
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ps.page_seo_score)::NUMERIC,
        2
    ) AS median_seo_score,

    ROUND(AVG(ps.content_score)::NUMERIC, 2) AS avg_content_score,
    ROUND(AVG(ps.on_page_score)::NUMERIC, 2) AS avg_on_page_score,
    ROUND(AVG(ps.technical_score)::NUMERIC, 2) AS avg_technical_score,
    ROUND(AVG(ps.ux_score)::NUMERIC, 2) AS avg_ux_score,

    -- consistency (very useful)
    ROUND(STDDEV(ps.page_seo_score)::NUMERIC, 2) AS seo_stddev

FROM page_seo_scores ps
JOIN pages p ON ps.page_url_hash = p.url_hash
JOIN competitors c ON c.id = p.competitor_id
GROUP BY p.competitor_id
ORDER BY avg_seo_score DESC;

CREATE MATERIALIZED VIEW competitor_gap_matrix AS
SELECT
    a.domain AS domain_a,
    b.domain AS domain_b,

    (a.avg_seo_score - b.avg_seo_score) AS seo_gap,
    (a.avg_content_score - b.avg_content_score) AS content_gap,
    (a.avg_on_page_score - b.avg_on_page_score) AS on_page_gap,
    (a.avg_technical_score - b.avg_technical_score) AS technical_gap,
    (a.avg_ux_score - b.avg_ux_score) AS ux_gap

FROM competitor_seo_summary a
JOIN competitor_seo_summary b
  ON a.competitor_id != b.competitor_id;
