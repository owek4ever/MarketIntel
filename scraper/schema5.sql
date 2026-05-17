CREATE EXTENSION IF NOT EXISTS unaccent;

CREATE TABLE target_categories (
    id SERIAL PRIMARY KEY,

    parent_category_id INTEGER REFERENCES target_categories(id),

    category_name VARCHAR(255) NOT NULL UNIQUE,
    normalized_name VARCHAR(255) UNIQUE,

    category_description TEXT,

    category_keywords TEXT,

    relevance_weight NUMERIC(5,2) DEFAULT 1.00,

    is_active BOOLEAN DEFAULT TRUE,

    metadata JSONB,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE OR REPLACE FUNCTION normalize_text(input TEXT)
RETURNS TEXT AS $$
BEGIN
    RETURN trim(
        regexp_replace(
            lower(unaccent(input)),
            '\s+',
            ' ',
            'g'
        )
    );
END;
$$ LANGUAGE plpgsql IMMUTABLE;

CREATE OR REPLACE FUNCTION set_normalized_category_name()
RETURNS TRIGGER AS $$
BEGIN
    NEW.normalized_name := normalize_text(NEW.category_name);
    NEW.updated_at := NOW();

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_set_normalized_category_name
BEFORE INSERT OR UPDATE
ON target_categories
FOR EACH ROW
EXECUTE FUNCTION set_normalized_category_name();

-- =========================================================
-- COMPETITOR MARKET SCORING VIEW
--
-- Scoring dimensions:
-- 1. Category Coverage
-- 2. Category Balance
-- 3. Assortment Score
-- 4. Availability Score
--
-- Final weighted score:
--
-- final_score =
--   40% coverage
--   25% category balance
--   20% assortment
--   15% availability
-- =========================================================


CREATE OR REPLACE MATERIALIZED VIEW competitor_market_scores AS

WITH active_target_categories AS (
    SELECT
        id,
        normalized_name AS normalized_category_name,
        relevance_weight
    FROM target_categories
    WHERE is_active = TRUE
),

     total_target_weight AS (
         SELECT
             COALESCE(SUM(relevance_weight), 0) AS total_weight
         FROM active_target_categories
     ),

-- ---------------------------------------------------------
-- Competitor categories matched against strategic categories
-- ---------------------------------------------------------
     competitor_category_matches AS (
         SELECT DISTINCT
             p.competitor_id,
             tc.normalized_category_name,
             tc.relevance_weight
         FROM products p
                  INNER JOIN active_target_categories tc
                             ON normalize_text(p.category) = tc.normalized_category_name
     ),

-- ---------------------------------------------------------
-- CATEGORY COVERAGE SCORE
-- weighted coverage based on strategic importance
-- ---------------------------------------------------------
     coverage_score AS (
         SELECT
             ccm.competitor_id,

             COALESCE(SUM(ccm.relevance_weight), 0) AS matched_weight,

             ROUND(
                     (
                         COALESCE(SUM(ccm.relevance_weight), 0)
                             /
                         NULLIF(
                                 (SELECT total_weight FROM total_target_weight),
                                 0
                         )
                         ) * 100,
                     2
             ) AS coverage_score

         FROM competitor_category_matches ccm
         GROUP BY ccm.competitor_id
     ),

-- ---------------------------------------------------------
-- CATEGORY BALANCE SCORE
-- weighted product count score, capped at 25 products per target category
-- ---------------------------------------------------------
     category_product_counts AS (
         SELECT
             p.competitor_id,
             tc.normalized_category_name,
             COUNT(*) AS product_count

         FROM products p
                  INNER JOIN active_target_categories tc
                             ON normalize_text(p.category) = tc.normalized_category_name
         GROUP BY p.competitor_id, tc.normalized_category_name
     ),

     category_balance_score AS (
         SELECT
             c.id AS competitor_id,

             ROUND(
                     (
                         SUM(
                             LEAST(
                                 COALESCE(cpc.product_count, 0)::NUMERIC,
                                 25
                             ) * tc.relevance_weight
                         )
                             /
                         NULLIF(
                                 (SELECT total_weight FROM total_target_weight) * 25,
                                 0
                         )
                         ) * 100,
                     2
             ) AS category_balance_score

         FROM competitors c
                  CROSS JOIN active_target_categories tc
                  LEFT JOIN category_product_counts cpc
                            ON c.id = cpc.competitor_id
                                AND tc.normalized_category_name = cpc.normalized_category_name
         GROUP BY c.id
     ),

-- ---------------------------------------------------------
-- ASSORTMENT SCORE
-- product data completeness across relevant products
-- ---------------------------------------------------------
     assortment_score AS (
         SELECT
             p.competitor_id,

             ROUND(
                     AVG(
                         (
                             CASE
                                 WHEN NULLIF(TRIM(p.title), '') IS NOT NULL THEN 20
                                 ELSE 0
                             END
                                 +
                             CASE
                                 WHEN NULLIF(TRIM(p.brand), '') IS NOT NULL THEN 15
                                 ELSE 0
                             END
                                 +
                             CASE
                                 WHEN p.current_price IS NOT NULL THEN 20
                                 ELSE 0
                             END
                                 +
                             CASE
                                 WHEN p.specifications IS NOT NULL
                                     AND p.specifications <> '{}'::jsonb
                                     AND p.specifications <> '[]'::jsonb
                                     THEN 45
                                 ELSE 0
                             END
                         )::NUMERIC
                     ),
                     2
             ) AS assortment_score

         FROM products p
                  INNER JOIN active_target_categories tc
                             ON normalize_text(p.category) = tc.normalized_category_name
         GROUP BY p.competitor_id
     ),

-- ---------------------------------------------------------
-- AVAILABILITY SCORE
-- percentage of products currently in stock
-- ---------------------------------------------------------
     availability_score AS (
         SELECT
             competitor_id,

             ROUND(
                     (
                                 COUNT(*) FILTER (WHERE in_stock = TRUE)::NUMERIC
                             /
                                 NULLIF(COUNT(*), 0)
                         ) * 100,
                     2
             ) AS availability_score

         FROM products
         GROUP BY competitor_id
     )

-- ---------------------------------------------------------
-- FINAL SCORE
-- ---------------------------------------------------------
SELECT
    c.id AS competitor_id,
    c.domain AS competitor_domain,

    COALESCE(cs.coverage_score, 0) AS coverage_score,
    COALESCE(cbs.category_balance_score, 0) AS category_balance_score,
    COALESCE(ass.assortment_score, 0) AS assortment_score,
    COALESCE(avs.availability_score, 0) AS availability_score,

    ROUND(
            (
                COALESCE(cs.coverage_score, 0) * 0.40
                    +
                COALESCE(cbs.category_balance_score, 0) * 0.25
                +
                COALESCE(ass.assortment_score, 0) * 0.20
                +
                    COALESCE(avs.availability_score, 0) * 0.15
                ),
            2
    ) AS final_score

FROM competitors c
         LEFT JOIN coverage_score cs
                   ON c.id = cs.competitor_id
         LEFT JOIN category_balance_score cbs
                   ON c.id = cbs.competitor_id
         LEFT JOIN assortment_score ass
                   ON c.id = ass.competitor_id
         LEFT JOIN availability_score avs
                   ON c.id = avs.competitor_id;
