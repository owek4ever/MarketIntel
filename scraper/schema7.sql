CREATE OR REPLACE VIEW competitor_top_issues AS
WITH expanded AS (
    SELECT
        p.competitor_id,
        ps.page_url_hash,
        LOWER(TRIM(regexp_replace(issue, '(?<=:)\s\d+|\(.*\)$', '', 'g'))) AS normalized_issue,
        substring(issue FROM 'Penalty:\s*([0-9\.]+)')::NUMERIC AS penalty_value,
        substring(issue FROM 'Score:\s*([0-9\.]+)/')::NUMERIC AS score_value,
        substring(issue FROM 'Score:\s*[0-9\.]+/([0-9\.]+)')::NUMERIC AS score_max,
        substring(issue FROM '([0-9]+)')::NUMERIC AS raw_number

    FROM page_snapshots ps
    JOIN pages p ON ps.page_url_hash = p.url_hash

    CROSS JOIN LATERAL jsonb_array_elements_text(
        COALESCE(ps.seo_flags->'scores'->'content_issues', '[]'::jsonb) ||
        COALESCE(ps.seo_flags->'scores'->'on_page_issues', '[]'::jsonb) ||
        COALESCE(ps.seo_flags->'scores'->'technical_issues', '[]'::jsonb)
    ) AS issue
),

scored AS (
    SELECT
        competitor_id,
        page_url_hash,
        normalized_issue,

        CASE
            WHEN penalty_value IS NOT NULL THEN penalty_value
            WHEN score_value IS NOT NULL THEN (score_max - score_value)
            WHEN raw_number IS NOT NULL THEN raw_number
            ELSE 1
        END AS impact

    FROM expanded
),

aggregated AS (
    SELECT
        competitor_id,
        normalized_issue,

        COUNT(*) AS occurrence_count,
        COUNT(DISTINCT page_url_hash) AS affected_pages,
        SUM(impact) AS total_impact,
        AVG(impact) AS avg_impact

    FROM scored
    GROUP BY competitor_id, normalized_issue
),

competitor_pages AS (
    SELECT
        competitor_id,
        COUNT(DISTINCT page_url_hash) AS total_pages
    FROM scored
    GROUP BY competitor_id
),

competitor_impact AS (
    SELECT
        competitor_id,
        SUM(total_impact) AS total_competitor_impact
    FROM aggregated
    GROUP BY competitor_id
),

metrics AS (
    SELECT
        a.*,
        ci.total_competitor_impact,
        cp.total_pages,

        ROUND(
            a.total_impact / NULLIF(ci.total_competitor_impact, 0),
            4
        ) AS impact_ratio,

        ROUND(
            a.affected_pages::NUMERIC / NULLIF(cp.total_pages, 0),
            4
        ) AS coverage_ratio

    FROM aggregated a
    JOIN competitor_impact ci USING (competitor_id)
    JOIN competitor_pages cp USING (competitor_id)
),

prioritized AS (
    SELECT
        *,
        ROUND((impact_ratio * 0.6 + coverage_ratio * 0.4)::NUMERIC * LOG(1 + affected_pages)::NUMERIC, 4) AS priority_score
    FROM metrics
),

ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY competitor_id
            ORDER BY priority_score DESC
        ) AS rank
    FROM prioritized
)

SELECT
    competitor_id,
    normalized_issue AS issue,

    occurrence_count,
    affected_pages,
    ROUND(total_impact, 2) AS total_impact,
    ROUND(avg_impact, 2) AS avg_impact,

    impact_ratio,
    coverage_ratio,
    priority_score,
    rank

FROM ranked
ORDER BY competitor_id, priority_score DESC;

CREATE MATERIALIZED VIEW competitor_action_plan AS
SELECT
    competitor_id,
    issue,

    SUM(priority_score) AS total_priority,
    AVG(priority_score) AS avg_priority,

    SUM(affected_pages) AS total_affected_pages,

    CASE
        WHEN SUM(priority_score) > 0.5 THEN 'critical'
        WHEN SUM(priority_score) > 0.2 THEN 'high'
        WHEN SUM(priority_score) > 0.1 THEN 'medium'
        ELSE 'low'
    END AS priority_level

FROM competitor_top_issues
GROUP BY competitor_id, issue;

