CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS vectorscale CASCADE;

CREATE TABLE competitors (
    id SERIAL PRIMARY KEY,
    domain VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE scrape_jobs (
    id BIGSERIAL PRIMARY KEY,
    url_hash VARCHAR(64),
    url TEXT NOT NULL,
    domain VARCHAR(255) NOT NULL,
    priority INTEGER DEFAULT 5,
    retries INTEGER DEFAULT 0,
    status VARCHAR(50) NOT NULL ,
    queued_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP WITH TIME ZONE,
    job_type VARCHAR(50) NOT NULL,
    technical_metadata JSONB
);

CREATE INDEX idx_scrape_jobs_status ON scrape_jobs(status);
CREATE INDEX idx_scrape_jobs_domain ON scrape_jobs(domain);
CREATE INDEX idx_scrape_jobs_job_type ON scrape_jobs(job_type);
CREATE INDEX idx_scrape_jobs_url_hash ON scrape_jobs(url_hash);

CREATE TABLE pages (
    url_hash VARCHAR(64) PRIMARY KEY,
    competitor_id INTEGER REFERENCES competitors(id) ON DELETE CASCADE,

    url TEXT UNIQUE NOT NULL,
    normalized_url TEXT,
    recent_content_hash VARCHAR(64),

    page_type VARCHAR(50), -- product, category, blog, homepage
    page_metadata JSONB,
    technical_metadata JSONB,

    first_seen_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    next_run_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP + INTERVAL '3 days',

    last_success_at TIMESTAMP WITH TIME ZONE,
    last_failure_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    last_error TEXT DEFAULT NULL
);

CREATE UNIQUE INDEX idx_pages_competitor_content_hash
ON pages (competitor_id, recent_content_hash);
CREATE INDEX idx_pages_competitor ON pages(competitor_id);
CREATE INDEX idx_pages_next_run ON pages(next_run_at);
CREATE INDEX idx_pages_type ON pages(page_type);

CREATE OR REPLACE FUNCTION pages_timestamp_trigger()
RETURNS TRIGGER AS $$
BEGIN
    -- INSERT logic
    IF TG_OP = 'INSERT' THEN
        NEW.first_seen_at := NOW();
    ELSE
        NEW.first_seen_at := OLD.first_seen_at;
    END IF;

    -- Handle last_error → last_error_at
    IF NEW.last_error <> '' THEN
        NEW.last_failure_at := NOW();
    END IF;

    NEW.next_run_at := NEW.last_seen_at + INTERVAL '3 days';

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_pages_timestamps
BEFORE INSERT OR UPDATE ON pages
FOR EACH ROW
EXECUTE FUNCTION pages_timestamp_trigger();

CREATE TABLE page_snapshots (
    id BIGSERIAL PRIMARY KEY,

    page_url_hash VARCHAR(64) REFERENCES pages(url_hash) ON DELETE CASCADE,

    status_code INTEGER,
    final_url TEXT,

    -- Content fingerprinting
    -- content_hash VARCHAR(64),
    text_hash VARCHAR(64),

    language VARCHAR(10),

    -- SEO Core
    title TEXT,
    meta_description TEXT,

    h1_count INTEGER,
    h2_count INTEGER,
    h3_count INTEGER,
    h4_count INTEGER,
    h5_count INTEGER,
    h6_count INTEGER,

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

CREATE INDEX idx_snapshots_page ON page_snapshots(page_url_hash);
CREATE INDEX idx_snapshots_hash ON page_snapshots(text_hash);

CREATE TABLE products (
    id BIGSERIAL PRIMARY KEY,
    competitor_id INTEGER REFERENCES competitors(id) ON DELETE CASCADE,

    url_hash VARCHAR(64) REFERENCES pages(url_hash) ON DELETE CASCADE,

    title TEXT,
    category VARCHAR(255),
    on_page_category VARCHAR(255),
    brand VARCHAR(255),

    specifications JSONB,
    on_page_details JSONB,

    -- title_embedding vector(768),
    description_embedding vector(768),

    current_price DECIMAL(10,2),
    in_stock BOOLEAN,

    category_page_hash VARCHAR(64) REFERENCES pages(url_hash) ON DELETE CASCADE,

    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

--CREATE INDEX idx_products_title_embedding ON products USING hnsw (title_embedding vector_cosine_ops);
CREATE INDEX idx_products_description_embedding ON products USING hnsw (description_embedding vector_cosine_ops);
CREATE UNIQUE INDEX idx_products_url_hash ON products(url_hash);
CREATE INDEX idx_products_category_page ON products(category_page_hash);

CREATE OR REPLACE FUNCTION products_timestamp_trigger()
RETURNS TRIGGER AS $$
BEGIN
    -- INSERT logic
    IF TG_OP = 'INSERT' THEN
        NEW.first_seen_at := NOW();
    ELSE
        NEW.first_seen_at := OLD.first_seen_at;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_products_timestamps
BEFORE INSERT OR UPDATE ON products
FOR EACH ROW
EXECUTE FUNCTION products_timestamp_trigger();

CREATE TABLE price_history (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT REFERENCES products(id) ON DELETE CASCADE,

    price DECIMAL(10,2),
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_price_product_time ON price_history(product_id, recorded_at DESC);

CREATE TABLE stock_history (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT REFERENCES products(id) ON DELETE CASCADE,

    in_stock BOOLEAN,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_stock_product_time ON stock_history(product_id, recorded_at DESC);


-- CREATE TABLE crawls (
--     id BIGSERIAL PRIMARY KEY,
--     competitor_id INTEGER REFERENCES competitors(id) ON DELETE CASCADE,

--     started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
--     finished_at TIMESTAMP WITH TIME ZONE,

--     status VARCHAR(50), -- running, completed, failed
--     total_pages INTEGER DEFAULT 0,

--     metadata JSONB
-- );

-- CREATE INDEX idx_crawls_competitor ON crawls(competitor_id);

-- CREATE TABLE seo_flags (
--     id BIGSERIAL PRIMARY KEY,
--     page_snapshot_id BIGINT REFERENCES page_snapshots(id) ON DELETE CASCADE,

--     has_missing_title BOOLEAN,
--     has_missing_description BOOLEAN,
--     has_multiple_h1 BOOLEAN,
--     has_thin_content BOOLEAN,
--     has_duplicate_title BOOLEAN,

--     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
-- );

-- CREATE INDEX idx_seo_flags_snapshot ON seo_flags(page_snapshot_id);

-- CREATE TABLE page_raw (
--     id BIGSERIAL PRIMARY KEY,
--     page_snapshot_id BIGINT REFERENCES page_snapshots(id) ON DELETE CASCADE,

--     html TEXT,
--     extracted_text TEXT
-- );

-- CREATE TABLE page_links (
--     id BIGSERIAL PRIMARY KEY,

--     from_page_id BIGINT REFERENCES pages(id) ON DELETE CASCADE,
--     to_url TEXT,

--     anchor_text TEXT,
--     is_internal BOOLEAN,

--     crawl_id BIGINT REFERENCES crawls(id) ON DELETE CASCADE
-- );

-- CREATE INDEX idx_links_from ON page_links(from_page_id);

-- CREATE TABLE content_clusters (
--     id BIGSERIAL PRIMARY KEY,
--     content_hash VARCHAR(64) UNIQUE,

--     representative_page_id BIGINT,
--     cluster_size INTEGER DEFAULT 1
-- );

-- CREATE TABLE page_embeddings (
--     id BIGSERIAL PRIMARY KEY,
--     page_id BIGINT REFERENCES pages(id) ON DELETE CASCADE,

--     embedding vector(768), -- smaller for content clustering
--     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
-- );

-- CREATE INDEX idx_page_embeddings ON page_embeddings USING hnsw (embedding vector_cosine_ops);