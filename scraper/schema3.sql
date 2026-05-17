CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

CREATE TYPE social_platform AS ENUM ('facebook', 'instagram', 'tiktok');

CREATE TABLE social_accounts (
    id BIGSERIAL PRIMARY KEY,

    competitor_id BIGINT REFERENCES competitors(id) ON DELETE CASCADE,

    platform social_platform NOT NULL,

    external_id VARCHAR(100) NOT NULL,
    username TEXT,
    display_name TEXT,

    profile_url TEXT UNIQUE,
    profile_image_url TEXT UNIQUE,

    description TEXT,
    category TEXT,

    -- bio_links TEXT,
    email TEXT,
    phone TEXT,

    is_verified BOOLEAN,
    is_business BOOLEAN,
    is_private BOOLEAN,

    follower_count INTEGER,
    following_count INTEGER,

    -- like_count INTEGER, -- useful for TikTok
    -- post_count INTEGER,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    next_crawl_at TIMESTAMP DEFAULT NOW() + INTERVAL '1 week',

    raw_json JSONB,

    UNIQUE(platform, external_id)
);

CREATE INDEX idx_social_accounts_competitor
ON social_accounts (competitor_id);

CREATE INDEX idx_social_accounts_platform
ON social_accounts (platform);

CREATE INDEX idx_social_accounts_platform_ext
ON social_accounts (platform, external_id);

CREATE TABLE social_account_links (
    id BIGSERIAL PRIMARY KEY,
    account_id BIGINT REFERENCES social_accounts(id) ON DELETE CASCADE,

    url TEXT NOT NULL,
    title TEXT,
    link_type VARCHAR(50), -- 'instagram', 'website', etc.

    UNIQUE(account_id, url)
);

CREATE INDEX idx_links_account
ON social_account_links (account_id);

CREATE TABLE social_posts (
    id BIGSERIAL PRIMARY KEY,

    account_id BIGINT REFERENCES social_accounts(id) ON DELETE CASCADE NOT NULL,

    platform social_platform NOT NULL,

    external_post_id VARCHAR(100) NOT NULL UNIQUE,

    text TEXT,

    post_url TEXT,

    content_type VARCHAR(50),
    -- 'image', 'video', 'carousel', 'reel', 'short', 'text'

    publish_time TIMESTAMP,

    -- is_sponsored BOOLEAN DEFAULT FALSE,

    like_count INTEGER,
    comment_count INTEGER,
    share_count INTEGER,
    view_count INTEGER,

    raw_json JSONB,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(platform, external_post_id)
);

CREATE INDEX idx_posts_account
ON social_posts (account_id);

CREATE INDEX idx_posts_publish_time
ON social_posts (publish_time DESC);

CREATE INDEX idx_posts_platform
ON social_posts (platform);

CREATE INDEX idx_posts_account_time
ON social_posts (account_id, publish_time DESC);

CREATE INDEX idx_posts_engagement
ON social_posts (like_count, comment_count);

CREATE INDEX idx_posts_recent
ON social_posts (publish_time DESC)

CREATE INDEX idx_posts_text_search
ON social_posts
USING GIN (to_tsvector('simple', text));

CREATE INDEX idx_posts_engagement_calc
ON social_posts (
    (COALESCE(like_count,0) + COALESCE(comment_count,0))
);

CREATE TABLE instagram_posts(
    id BIGSERIAL PRIMARY KEY,

    external_post_id VARCHAR(100) REFERENCES social_posts(external_post_id) ON DELETE CASCADE,

    code VARCHAR(20),
    device_timestamp INTEGER,
    taken_at INTEGER,
    media_type VARCHAR(20),
    media_url TEXT,
    thumbnail_url TEXT,

    original_width INTEGER,
    original_height INTEGER,

    music_metadata JSONB,

    caption TEXT,
    caption_metadata JSONB,

    accessibility_caption TEXT,

    product_type VARCHAR(50),

    subscribe_cta_visible BOOLEAN,

    is_paid_partnership BOOLEAN,

    can_viewer_save BOOLEAN,
    can_viewer_reshare BOOLEAN,

    media_language VARCHAR(10),

    has_audio BOOLEAN,
    audio_metadata JSONB,

    location_metadata JSONB,
    play_count INTEGER,

    video_duration_ms DECIMAL,

    user_tags JSONB,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(external_post_id)
);

CREATE INDEX idx_instagram_posts_post
ON instagram_posts (external_post_id);

-- CREATE INDEX idx_posts_raw_product_type
-- ON social_posts
-- USING GIN (raw_json);

-- CREATE TABLE social_post_media (
--     id BIGSERIAL PRIMARY KEY,

--     post_id BIGINT REFERENCES social_posts(id) ON DELETE CASCADE,

--     media_type VARCHAR(20), -- 'image', 'video'

--     url TEXT NOT NULL,
--     thumbnail_url TEXT,

--     width INTEGER,
--     height INTEGER,

--     duration_seconds NUMERIC,

--     position INTEGER,

--     UNIQUE(post_id, url)
-- );

-- CREATE INDEX idx_media_post
-- ON social_post_media (post_id);

-- CREATE TABLE social_post_comments (
--     id BIGSERIAL PRIMARY KEY,

--     post_id BIGINT REFERENCES social_posts(id) ON DELETE CASCADE,

--     external_comment_id TEXT,

--     author_name TEXT,
--     author_id TEXT,
--     author_username TEXT,

--     text TEXT,

--     like_count INTEGER,

--     publish_time TIMESTAMP,

--     raw_json JSONB
-- );

-- CREATE INDEX idx_comments_post
-- ON social_post_comments (post_id);

-- CREATE INDEX idx_comments_time
-- ON social_post_comments (publish_time DESC);

CREATE TABLE social_post_metrics (
    id BIGSERIAL,

    external_post_id VARCHAR(100) REFERENCES social_posts(external_post_id) ON DELETE CASCADE,

    like_count INTEGER,
    comment_count INTEGER,
    share_count INTEGER,
    view_count INTEGER,

    snapshot_time TIMESTAMP DEFAULT NOW(),
    constraint social_post_metrics_pk PRIMARY KEY (id, snapshot_time)
);

SELECT create_hypertable(
               'social_post_metrics',
               'snapshot_time'
       );

CREATE INDEX idx_post_metrics_post_time
    ON social_post_metrics (external_post_id, snapshot_time DESC);

ALTER TABLE social_post_metrics SET (timescaledb.compress_segmentby = 'external_post_id');

SELECT add_compression_policy(
               'social_post_metrics',
               INTERVAL '7 days'
       );

SELECT add_retention_policy(
               'social_post_metrics',
               INTERVAL '90 days'
       );

CREATE TABLE social_account_metrics (
    id BIGSERIAL,

    account_id BIGINT REFERENCES social_accounts(id) ON DELETE CASCADE,

    follower_count INTEGER,
    following_count INTEGER,
    like_count INTEGER,

    snapshot_time TIMESTAMP DEFAULT NOW(),
    CONSTRAINT social_account_metrics_pk PRIMARY KEY (id, snapshot_time)
);

CREATE INDEX idx_account_metrics_time ON social_account_metrics (account_id, snapshot_time DESC);

SELECT create_hypertable('social_account_metrics', 'snapshot_time');

ALTER TABLE social_account_metrics SET (timescaledb.compress_segmentby = 'account_id');
SELECT add_compression_policy('social_account_metrics', INTERVAL '7 days');

-- CREATE TABLE social_post_analysis (
--     post_id BIGINT PRIMARY KEY REFERENCES social_posts(id) ON DELETE CASCADE,

--     language VARCHAR(10),

--     sentiment_score NUMERIC,

--     content_category VARCHAR(50), 
--     -- 'promotion', 'educational', 'branding', 'entertainment'

--     has_cta BOOLEAN,
--     has_offer BOOLEAN,
--     has_price BOOLEAN,

--     keyword_tags TEXT[],

--     created_at TIMESTAMP DEFAULT NOW()
-- );













CREATE MATERIALIZED VIEW post_daily_metrics
WITH (timescaledb.continuous) AS
SELECT
    post_id,
    time_bucket('1 day', snapshot_time) AS day,
    AVG(like_count) AS avg_likes,
    AVG(comment_count) AS avg_comments,
    AVG(view_count) AS avg_views
FROM social_post_metrics
GROUP BY post_id, day;

SELECT add_continuous_aggregate_policy(
    'post_daily_metrics',
    start_offset => INTERVAL '7 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '30 minutes'
);

