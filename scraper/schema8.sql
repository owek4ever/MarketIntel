CREATE MATERIALIZED VIEW page_performance_scores AS
WITH extracted AS (
    SELECT
        competitor_id,
        domain,

        (technical_metadata->>'ttfb')::FLOAT AS ttfb,
        (technical_metadata->>'first_paint')::FLOAT AS first_paint,
        (technical_metadata->>'dom_interactive')::FLOAT AS dom_interactive,
        (technical_metadata->>'dom_complete')::FLOAT AS dom_complete,
        (technical_metadata->>'page_size')::FLOAT AS page_size,
        (technical_metadata->>'dom_size')::FLOAT AS dom_size,
        (technical_metadata->>'resource_count')::FLOAT AS resource_count,
        (technical_metadata->>'status_code')::INT AS status_code

    FROM pages
    LEFT JOIN public.competitors c on c.id = pages.competitor_id
),

scored AS (
    SELECT
        *,

        -- TTFB score
        CASE
            WHEN ttfb = -1 THEN NULL
            WHEN ttfb <= 200 THEN 1
            WHEN ttfb <= 500 THEN 0.8
            WHEN ttfb <= 1000 THEN 0.6
            WHEN ttfb <= 2000 THEN 0.3
            ELSE 0
        END AS ttfb_score,

        -- First paint
        CASE
            WHEN first_paint = -1 THEN NULL
            WHEN first_paint <= 1000 THEN 1
            WHEN first_paint <= 2000 THEN 0.7
            WHEN first_paint <= 3000 THEN 0.4
            ELSE 0
        END AS fp_score,

        -- DOM interactive
        CASE
            WHEN dom_interactive = -1 THEN NULL
            WHEN dom_interactive <= 1000 THEN 1
            WHEN dom_interactive <= 2000 THEN 0.7
            WHEN dom_interactive <= 4000 THEN 0.4
            ELSE 0
        END AS di_score,

        -- DOM complete
        CASE
            WHEN dom_complete = -1 THEN NULL
            WHEN dom_complete <= 2000 THEN 1
            WHEN dom_complete <= 4000 THEN 0.7
            WHEN dom_complete <= 6000 THEN 0.4
            ELSE 0
        END AS dc_score,

        -- Page size
        CASE
            WHEN page_size = -1 THEN NULL
            WHEN page_size <= 200000 THEN 1
            WHEN page_size <= 500000 THEN 0.7
            WHEN page_size <= 1000000 THEN 0.4
            ELSE 0
        END AS ps_score,

        -- DOM size
        CASE
            WHEN dom_size = -1 THEN NULL
            WHEN dom_size <= 800 THEN 1
            WHEN dom_size <= 1500 THEN 0.7
            WHEN dom_size <= 3000 THEN 0.4
            ELSE 0
        END AS dom_score,

        -- Resources
        CASE
            WHEN resource_count = -1 THEN NULL
            WHEN resource_count <= 30 THEN 1
            WHEN resource_count <= 60 THEN 0.7
            WHEN resource_count <= 100 THEN 0.4
            ELSE 0
        END AS res_score

    FROM extracted
),

final AS (
    SELECT
        competitor_id,
        domain,
        ttfb_score,
        fp_score,
        di_score,
        dc_score,
        ps_score,
        dom_score,
        res_score,
        ROUND((
            COALESCE(ttfb_score, 0) * 0.20 +
            COALESCE(fp_score, 0) * 0.20 +
            COALESCE(di_score, 0) * 0.20 +
            COALESCE(dc_score, 0) * 0.15 +
            COALESCE(ps_score, 0) * 0.10 +
            COALESCE(dom_score, 0) * 0.10 +
            COALESCE(res_score, 0) * 0.05
        )::numeric, 4) AS page_speed_score

    FROM scored
)

SELECT * FROM final;