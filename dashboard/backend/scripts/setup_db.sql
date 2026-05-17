-- PFE2 Database Setup (without timescaledb/pgvector)
CREATE EXTENSION IF NOT EXISTS unaccent;

-- COMPETITORS
CREATE TABLE IF NOT EXISTS competitors (
    id SERIAL PRIMARY KEY,
    domain VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- SCRAPE JOBS
CREATE TABLE IF NOT EXISTS scrape_jobs (
    id BIGSERIAL PRIMARY KEY,
    url_hash VARCHAR(64),
    url TEXT NOT NULL,
    domain VARCHAR(255) NOT NULL,
    priority INTEGER DEFAULT 5,
    retries INTEGER DEFAULT 0,
    status VARCHAR(50) NOT NULL,
    queued_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP WITH TIME ZONE,
    job_type VARCHAR(50) NOT NULL,
    technical_metadata JSONB
);
CREATE INDEX IF NOT EXISTS idx_scrape_jobs_status ON scrape_jobs(status);
CREATE INDEX IF NOT EXISTS idx_scrape_jobs_domain ON scrape_jobs(domain);
CREATE INDEX IF NOT EXISTS idx_scrape_jobs_job_type ON scrape_jobs(job_type);

-- PAGES
CREATE TABLE IF NOT EXISTS pages (
    url_hash VARCHAR(64) PRIMARY KEY,
    competitor_id INTEGER REFERENCES competitors(id) ON DELETE CASCADE,
    url TEXT UNIQUE NOT NULL,
    normalized_url TEXT,
    recent_content_hash VARCHAR(64),
    page_type VARCHAR(50),
    page_metadata JSONB,
    technical_metadata JSONB,
    first_seen_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    next_run_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP + INTERVAL '3 days',
    last_success_at TIMESTAMP WITH TIME ZONE,
    last_failure_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    last_error TEXT DEFAULT NULL
);
CREATE INDEX IF NOT EXISTS idx_pages_competitor ON pages(competitor_id);
CREATE INDEX IF NOT EXISTS idx_pages_next_run ON pages(next_run_at);
CREATE INDEX IF NOT EXISTS idx_pages_type ON pages(page_type);

-- PAGE SNAPSHOTS
CREATE TABLE IF NOT EXISTS page_snapshots (
    id BIGSERIAL PRIMARY KEY,
    page_url_hash VARCHAR(64) REFERENCES pages(url_hash) ON DELETE CASCADE,
    status_code INTEGER,
    final_url TEXT,
    text_hash VARCHAR(64),
    language VARCHAR(10),
    title TEXT,
    meta_description TEXT,
    h1_count INTEGER, h2_count INTEGER, h3_count INTEGER,
    h4_count INTEGER, h5_count INTEGER, h6_count INTEGER,
    h1_contains_primary_keyword BOOLEAN,
    subheadings_contains_primary_keyword BOOLEAN,
    images_count INTEGER,
    not_optimized_images_count INTEGER,
    broken_images_count INTEGER,
    internal_links_count INTEGER,
    external_links_count INTEGER,
    word_count INTEGER,
    paragraphs_count INTEGER,
    avg_paragraph_word_count INTEGER,
    bullet_list_count INTEGER,
    number_list_count INTEGER,
    javascript_files_count INTEGER,
    css_files_count INTEGER,
    inline_styles_count INTEGER,
    primary_keyword VARCHAR(255),
    candidate_primary_keywords TEXT,
    has_breadcrumbs BOOLEAN,
    has_pagination BOOLEAN,
    iframe_count INTEGER,
    visible_text_sample TEXT,
    visible_text_sample_hash VARCHAR(64),
    text_to_html_ratio DECIMAL(10,2),
    avg_sentence_length DECIMAL(10,2),
    flesch_kincaid_grade DECIMAL(10,2),
    mobile_responsive BOOLEAN,
    is_url_seo_friendly BOOLEAN,
    url_seo_issues TEXT,
    headings JSONB,
    seo_flags JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_snapshots_page ON page_snapshots(page_url_hash);

-- PRODUCTS (without vector embedding columns)
CREATE TABLE IF NOT EXISTS products (
    id BIGSERIAL PRIMARY KEY,
    competitor_id INTEGER REFERENCES competitors(id) ON DELETE CASCADE,
    url_hash VARCHAR(64) REFERENCES pages(url_hash) ON DELETE CASCADE,
    title TEXT,
    category VARCHAR(255),
    on_page_category VARCHAR(255),
    brand VARCHAR(255),
    specifications JSONB,
    on_page_details JSONB,
    current_price DECIMAL(10,2),
    in_stock BOOLEAN,
    category_page_hash VARCHAR(64),
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_products_url_hash ON products(url_hash);

-- PRICE HISTORY
CREATE TABLE IF NOT EXISTS price_history (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT REFERENCES products(id) ON DELETE CASCADE,
    price DECIMAL(10,2),
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_price_product_time ON price_history(product_id, recorded_at DESC);

-- STOCK HISTORY
CREATE TABLE IF NOT EXISTS stock_history (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT REFERENCES products(id) ON DELETE CASCADE,
    in_stock BOOLEAN,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_stock_product_time ON stock_history(product_id, recorded_at DESC);

-- SOCIAL
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'social_platform') THEN
        CREATE TYPE social_platform AS ENUM ('facebook','instagram','tiktok');
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS social_accounts (
    id BIGSERIAL PRIMARY KEY,
    competitor_id BIGINT REFERENCES competitors(id) ON DELETE CASCADE,
    platform social_platform NOT NULL,
    external_id VARCHAR(100) NOT NULL,
    username TEXT, display_name TEXT,
    profile_url TEXT UNIQUE,
    profile_image_url TEXT UNIQUE,
    description TEXT, category TEXT,
    email TEXT, phone TEXT,
    is_verified BOOLEAN, is_business BOOLEAN, is_private BOOLEAN,
    follower_count INTEGER, following_count INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    next_crawl_at TIMESTAMP DEFAULT NOW() + INTERVAL '1 week',
    raw_json JSONB,
    UNIQUE(platform, external_id)
);
CREATE INDEX IF NOT EXISTS idx_social_accounts_competitor ON social_accounts(competitor_id);

CREATE TABLE IF NOT EXISTS social_account_links (
    id BIGSERIAL PRIMARY KEY,
    account_id BIGINT REFERENCES social_accounts(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    title TEXT,
    link_type VARCHAR(50),
    UNIQUE(account_id, url)
);

CREATE TABLE IF NOT EXISTS social_posts (
    id BIGSERIAL PRIMARY KEY,
    account_id BIGINT REFERENCES social_accounts(id) ON DELETE CASCADE NOT NULL,
    platform social_platform NOT NULL,
    external_post_id VARCHAR(100) NOT NULL UNIQUE,
    text TEXT, post_url TEXT,
    content_type VARCHAR(50),
    publish_time TIMESTAMP,
    like_count INTEGER, comment_count INTEGER,
    share_count INTEGER, view_count INTEGER,
    raw_json JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(platform, external_post_id)
);
CREATE INDEX IF NOT EXISTS idx_posts_account ON social_posts(account_id);
CREATE INDEX IF NOT EXISTS idx_posts_publish_time ON social_posts(publish_time DESC);
CREATE INDEX IF NOT EXISTS idx_posts_account_time ON social_posts(account_id, publish_time DESC);

CREATE TABLE IF NOT EXISTS social_post_metrics (
    id BIGSERIAL PRIMARY KEY,
    external_post_id VARCHAR(100) REFERENCES social_posts(external_post_id) ON DELETE CASCADE,
    like_count INTEGER, comment_count INTEGER,
    share_count INTEGER, view_count INTEGER,
    snapshot_time TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_post_metrics_time ON social_post_metrics(external_post_id, snapshot_time DESC);

CREATE TABLE IF NOT EXISTS social_account_metrics (
    id BIGSERIAL PRIMARY KEY,
    account_id BIGINT REFERENCES social_accounts(id) ON DELETE CASCADE,
    follower_count INTEGER, following_count INTEGER, like_count INTEGER,
    snapshot_time TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_account_metrics_time ON social_account_metrics(account_id, snapshot_time DESC);

CREATE TABLE IF NOT EXISTS competitor_social_score_history (
    snapshot_date DATE,
    competitor_id INT,
    platform TEXT,
    score NUMERIC,
    engagement_score NUMERIC,
    reach_score NUMERIC,
    activity_score NUMERIC,
    growth_score NUMERIC,
    PRIMARY KEY (snapshot_date, competitor_id, platform)
);

CREATE TABLE IF NOT EXISTS competitor_social_ai_analysis (
    id BIGSERIAL PRIMARY KEY,
    competitor_id INT,
    platform TEXT,
    analysis_date DATE,
    ai_summary JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- TARGET CATEGORIES
CREATE TABLE IF NOT EXISTS target_categories (
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
    RETURN trim(regexp_replace(lower(unaccent(input)), '\s+', ' ', 'g'));
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- SEO SCORES VIEW
CREATE OR REPLACE VIEW page_seo_scores AS
WITH base AS (
    SELECT
        ps.id, ps.page_url_hash,
        COALESCE((ps.seo_flags->'scores'->>'content_score_percent')::NUMERIC, 70) AS content_score,
        COALESCE((ps.seo_flags->'scores'->>'on_page_score_percent')::NUMERIC, 70) AS on_page_score,
        COALESCE((ps.seo_flags->'scores'->>'technical_score_percent')::NUMERIC, 70) AS technical_score,
        COALESCE((ps.seo_flags->'scores'->>'overall_seo_score_percent')::NUMERIC, 70) AS overall_score,
        (
            (CASE WHEN ps.has_breadcrumbs THEN 100 ELSE 60 END) * 0.25 +
            (CASE WHEN (ps.bullet_list_count + ps.number_list_count) > 0 THEN 100 ELSE 70 END) * 0.20 +
            (CASE WHEN ps.avg_paragraph_word_count BETWEEN 40 AND 120 THEN 100 ELSE 50 END) * 0.25 +
            (CASE WHEN ps.internal_links_count > 10 THEN 100 ELSE 70 END) * 0.15 +
            (CASE WHEN ps.external_links_count > 0 THEN 100 ELSE 80 END) * 0.15
        ) AS ux_score
    FROM page_snapshots ps
)
SELECT id, page_url_hash,
    ROUND(content_score,2) AS content_score,
    ROUND(on_page_score,2) AS on_page_score,
    ROUND(technical_score,2) AS technical_score,
    ROUND(overall_score,2) AS overall_score,
    ROUND(ux_score,2) AS ux_score,
    ROUND((overall_score*0.50 + content_score*0.20 + on_page_score*0.15 + technical_score*0.10 + ux_score*0.05),2) AS page_seo_score
FROM base;

-- COMPETITOR SEO SUMMARY (regular materialized view)
CREATE MATERIALIZED VIEW IF NOT EXISTS competitor_seo_summary AS
SELECT
    p.competitor_id,
    c.domain,
    COUNT(*) AS total_pages,
    ROUND(AVG(ps.page_seo_score)::NUMERIC,2) AS avg_seo_score,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ps.page_seo_score)::NUMERIC,2) AS median_seo_score,
    ROUND(AVG(ps.content_score)::NUMERIC,2) AS avg_content_score,
    ROUND(AVG(ps.on_page_score)::NUMERIC,2) AS avg_on_page_score,
    ROUND(AVG(ps.technical_score)::NUMERIC,2) AS avg_technical_score,
    ROUND(AVG(ps.ux_score)::NUMERIC,2) AS avg_ux_score,
    ROUND(STDDEV(ps.page_seo_score)::NUMERIC,2) AS seo_stddev
FROM page_seo_scores ps
JOIN pages p ON ps.page_url_hash = p.url_hash
JOIN competitors c ON c.id = p.competitor_id
GROUP BY p.competitor_id, c.domain
ORDER BY avg_seo_score DESC;

CREATE UNIQUE INDEX IF NOT EXISTS idx_css_competitor ON competitor_seo_summary(competitor_id);

-- COMPETITOR GAP MATRIX
CREATE MATERIALIZED VIEW IF NOT EXISTS competitor_gap_matrix AS
SELECT
    a.domain AS domain_a, a.competitor_id AS competitor_a,
    b.domain AS domain_b, b.competitor_id AS competitor_b,
    (a.avg_seo_score - b.avg_seo_score) AS seo_gap,
    (a.avg_content_score - b.avg_content_score) AS content_gap,
    (a.avg_on_page_score - b.avg_on_page_score) AS on_page_gap,
    (a.avg_technical_score - b.avg_technical_score) AS technical_gap,
    (a.avg_ux_score - b.avg_ux_score) AS ux_gap
FROM competitor_seo_summary a
JOIN competitor_seo_summary b ON a.competitor_id != b.competitor_id;

-- PAGE PERFORMANCE SCORES
CREATE MATERIALIZED VIEW IF NOT EXISTS page_performance_scores AS
WITH extracted AS (
    SELECT p.url_hash,
        p.competitor_id, c.domain,
        (p.technical_metadata->>'ttfb')::FLOAT AS ttfb,
        (p.technical_metadata->>'first_paint')::FLOAT AS first_paint,
        (p.technical_metadata->>'dom_interactive')::FLOAT AS dom_interactive,
        (p.technical_metadata->>'dom_complete')::FLOAT AS dom_complete,
        (p.technical_metadata->>'page_size')::FLOAT AS page_size,
        (p.technical_metadata->>'dom_size')::FLOAT AS dom_size,
        (p.technical_metadata->>'resource_count')::FLOAT AS resource_count
    FROM pages p LEFT JOIN competitors c ON c.id = p.competitor_id
),
scored AS (
    SELECT *, 
        CASE WHEN ttfb<=200 THEN 1 WHEN ttfb<=500 THEN 0.8 WHEN ttfb<=1000 THEN 0.6 WHEN ttfb<=2000 THEN 0.3 ELSE 0 END AS ttfb_score,
        CASE WHEN first_paint<=1000 THEN 1 WHEN first_paint<=2000 THEN 0.7 WHEN first_paint<=3000 THEN 0.4 ELSE 0 END AS fp_score,
        CASE WHEN dom_interactive<=1000 THEN 1 WHEN dom_interactive<=2000 THEN 0.7 WHEN dom_interactive<=4000 THEN 0.4 ELSE 0 END AS di_score,
        CASE WHEN dom_complete<=2000 THEN 1 WHEN dom_complete<=4000 THEN 0.7 WHEN dom_complete<=6000 THEN 0.4 ELSE 0 END AS dc_score,
        CASE WHEN page_size<=200000 THEN 1 WHEN page_size<=500000 THEN 0.7 WHEN page_size<=1000000 THEN 0.4 ELSE 0 END AS ps_score,
        CASE WHEN dom_size<=800 THEN 1 WHEN dom_size<=1500 THEN 0.7 WHEN dom_size<=3000 THEN 0.4 ELSE 0 END AS dom_score,
        CASE WHEN resource_count<=30 THEN 1 WHEN resource_count<=60 THEN 0.7 WHEN resource_count<=100 THEN 0.4 ELSE 0 END AS res_score
    FROM extracted
)
SELECT url_hash, competitor_id, domain,
    ttfb_score, fp_score, di_score, dc_score, ps_score, dom_score, res_score,
    ROUND((COALESCE(ttfb_score,0)*0.20 + COALESCE(fp_score,0)*0.20 + COALESCE(di_score,0)*0.20 +
           COALESCE(dc_score,0)*0.15 + COALESCE(ps_score,0)*0.10 + COALESCE(dom_score,0)*0.10 +
           COALESCE(res_score,0)*0.05)::numeric, 4) AS page_speed_score
FROM scored;

CREATE UNIQUE INDEX IF NOT EXISTS idx_pps_url ON page_performance_scores(url_hash);

-- PAGE OVERALL SCORES
CREATE MATERIALIZED VIEW IF NOT EXISTS page_overall_scores AS
SELECT
    p.url_hash, p.competitor_id,
    seo.overall_score AS seo_score,
    ROUND(perf.page_speed_score * 100, 2) AS page_speed_score,
    ROUND((COALESCE(seo.overall_score, 0)*0.7 + COALESCE(ROUND(perf.page_speed_score*100,2), 0)*0.3)::numeric, 4) AS overall_score
FROM pages p
LEFT JOIN page_seo_scores seo ON seo.page_url_hash = p.url_hash
LEFT JOIN page_performance_scores perf ON perf.url_hash = p.url_hash;

CREATE UNIQUE INDEX IF NOT EXISTS idx_pos_url ON page_overall_scores(url_hash);

-- COMPETITOR PAGE SCORES
CREATE MATERIALIZED VIEW IF NOT EXISTS competitor_page_scores AS
SELECT
    competitor_id,
    COUNT(*) AS total_pages,
    ROUND(AVG(overall_score),4) AS avg_score,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY overall_score)::NUMERIC,4) AS median_score,
    ROUND(MIN(overall_score),4) AS worst_page_score,
    ROUND(MAX(overall_score),4) AS best_page_score
FROM page_overall_scores
GROUP BY competitor_id;

-- PAGE TYPE SCORES
CREATE MATERIALIZED VIEW IF NOT EXISTS page_type_scores AS
SELECT p.competitor_id, p.page_type, AVG(pos.overall_score) AS avg_score
FROM page_overall_scores pos
JOIN pages p USING (url_hash)
GROUP BY p.competitor_id, p.page_type;

-- COMPETITOR MARKET SCORES
CREATE MATERIALIZED VIEW IF NOT EXISTS competitor_market_scores AS
WITH active_tc AS (
    SELECT id, normalize_text(category_name) AS normalized_category_name, relevance_weight
    FROM target_categories WHERE is_active = TRUE
),
total_w AS (SELECT COALESCE(SUM(relevance_weight),0) AS total_weight FROM active_tc),
matches AS (
    SELECT DISTINCT p.competitor_id, tc.normalized_category_name, tc.relevance_weight
    FROM products p
    INNER JOIN active_tc tc ON normalize_text(p.category) = tc.normalized_category_name
),
coverage AS (
    SELECT competitor_id,
        ROUND((COALESCE(SUM(relevance_weight),0) / NULLIF((SELECT total_weight FROM total_w),0))*100,2) AS coverage_score
    FROM matches GROUP BY competitor_id
),
avail AS (
    SELECT competitor_id,
        ROUND((COUNT(*) FILTER (WHERE in_stock=TRUE)::NUMERIC / NULLIF(COUNT(*),0))*100,2) AS availability_score
    FROM products GROUP BY competitor_id
)
SELECT
    c.id AS competitor_id, c.domain AS competitor_domain,
    COALESCE(cv.coverage_score,0) AS coverage_score,
    0::numeric AS category_balance_score,
    0::numeric AS assortment_score,
    COALESCE(av.availability_score,0) AS availability_score,
    ROUND((COALESCE(cv.coverage_score,0)*0.40 + COALESCE(av.availability_score,0)*0.15),2) AS final_score
FROM competitors c
LEFT JOIN coverage cv ON c.id = cv.competitor_id
LEFT JOIN avail av ON c.id = av.competitor_id;

-- COMPETITOR SOCIAL SCORE (simplified without TimescaleDB)
CREATE MATERIALIZED VIEW IF NOT EXISTS competitor_social_score AS
WITH latest_metrics AS (
    SELECT DISTINCT ON (account_id)
        account_id, follower_count
    FROM social_account_metrics
    ORDER BY account_id, snapshot_time DESC
),
engagement AS (
    SELECT sa.id AS account_id, sa.competitor_id, sa.platform,
        ROUND(AVG(COALESCE(sp.like_count,0)+COALESCE(sp.comment_count,0)+COALESCE(sp.share_count,0)),2) AS avg_engagement,
        ROUND(AVG(COALESCE(sp.like_count,0)),2) AS avg_likes_per_post,
        ROUND(AVG(COALESCE(sp.comment_count,0)),2) AS avg_comments_per_post,
        ROUND(AVG(COALESCE(sp.share_count,0)),2) AS avg_shares_per_post,
        ROUND(COUNT(sp.id)::numeric/3.0,2) AS posts_per_month
    FROM social_accounts sa
    LEFT JOIN social_posts sp ON sp.account_id = sa.id
        AND sp.publish_time >= NOW() - INTERVAL '3 months'
    GROUP BY sa.id, sa.competitor_id, sa.platform
)
SELECT
    e.competitor_id, e.platform::text,
    ROUND(AVG(e.avg_engagement / NULLIF(lm.follower_count::numeric,0)),4) AS score,
    ROUND(AVG(e.avg_engagement / NULLIF(lm.follower_count::numeric,0)),4) AS engagement_score,
    0::numeric AS reach_score, 0::numeric AS activity_score, 0::numeric AS growth_score,
    ROUND(AVG(e.posts_per_month),2) AS posts_per_month,
    ROUND(AVG(e.avg_engagement * e.posts_per_month),2) AS engagement_per_month,
    ROUND(AVG(e.avg_engagement / NULLIF(lm.follower_count::numeric,0) * 1000),2) AS engagement_per_1k_followers,
    ROUND(AVG(e.avg_likes_per_post),2) AS avg_likes_per_post,
    ROUND(AVG(e.avg_comments_per_post),2) AS avg_comments_per_post,
    ROUND(AVG(e.avg_shares_per_post),2) AS avg_shares_per_post,
    0 AS follower_growth_absolute,
    0::numeric AS posting_consistency
FROM engagement e
LEFT JOIN latest_metrics lm ON lm.account_id = e.account_id
GROUP BY e.competitor_id, e.platform;

-- COMPETITOR SOCIAL TIME SERIES (from history table)
CREATE MATERIALIZED VIEW IF NOT EXISTS competitor_social_time_series AS
SELECT
    competitor_id, platform, snapshot_date, score,
    score - LAG(score) OVER (PARTITION BY competitor_id,platform ORDER BY snapshot_date) AS score_delta,
    0::numeric AS score_acceleration,
    AVG(score) OVER (PARTITION BY competitor_id,platform ORDER BY snapshot_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS score_7d_avg,
    AVG(score) OVER (PARTITION BY competitor_id,platform ORDER BY snapshot_date ROWS BETWEEN 29 PRECEDING AND CURRENT ROW) AS score_30d_avg,
    0::numeric AS momentum, 0::numeric AS volatility,
    0::numeric AS stability_score, 0::numeric AS composite_score,
    'flat'::text AS trend_direction, 'stable'::text AS momentum_state
FROM competitor_social_score_history;

-- SOCIAL FORECASTS (simplified)
CREATE MATERIALIZED VIEW IF NOT EXISTS competitor_social_forecast_regression AS
SELECT competitor_id, platform, CURRENT_DATE AS forecast_date,
    score AS forecast_score_7d, score AS forecast_score_30d, 0::numeric AS trend_slope
FROM competitor_social_score_history
WHERE (competitor_id, platform, snapshot_date) IN (
    SELECT competitor_id, platform, MAX(snapshot_date)
    FROM competitor_social_score_history GROUP BY competitor_id, platform
);

CREATE MATERIALIZED VIEW IF NOT EXISTS competitor_social_forecast_momentum AS
SELECT competitor_id, platform, snapshot_date, score,
    0::numeric AS momentum, score AS forecast_7d, score AS forecast_30d
FROM competitor_social_score_history
WHERE snapshot_date = CURRENT_DATE;

CREATE MATERIALIZED VIEW IF NOT EXISTS competitor_social_forecast_smoothed AS
SELECT competitor_id, platform, snapshot_date,
    score AS smoothed_score, score AS forecast_7d, score AS forecast_30d
FROM competitor_social_score_history;

-- COMPETITOR ACTION PLAN
CREATE MATERIALIZED VIEW IF NOT EXISTS competitor_action_plan AS
SELECT
    p.competitor_id,
    lower(trim(issue.val)) AS issue,
    COUNT(*) AS total_affected_pages,
    1::numeric AS total_priority,
    0::numeric AS avg_priority,
    'low'::text AS priority_level
FROM page_snapshots ps
JOIN pages p ON ps.page_url_hash = p.url_hash
CROSS JOIN LATERAL jsonb_array_elements_text(
    COALESCE(ps.seo_flags->'scores'->'content_issues','[]'::jsonb) ||
    COALESCE(ps.seo_flags->'scores'->'on_page_issues','[]'::jsonb) ||
    COALESCE(ps.seo_flags->'scores'->'technical_issues','[]'::jsonb)
) AS issue(val)
GROUP BY p.competitor_id, lower(trim(issue.val));

-- DASHBOARD SCHEMA
CREATE SCHEMA IF NOT EXISTS dashboard;

CREATE TABLE IF NOT EXISTS dashboard.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_pwd TEXT NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'analyst' CHECK (role IN ('admin','analyst')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS dashboard.refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES dashboard.users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_rt_user_id ON dashboard.refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_rt_token_hash ON dashboard.refresh_tokens(token_hash);

CREATE TABLE IF NOT EXISTS dashboard.audit_log (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES dashboard.users(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS dashboard.saved_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES dashboard.users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    filters JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
