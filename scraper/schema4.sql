CREATE MATERIALIZED VIEW competitor_social_score AS
WITH latest_account_metrics AS (
    SELECT DISTINCT ON (account_id)
        account_id,
        follower_count,
        snapshot_time
    FROM social_account_metrics
    ORDER BY account_id, snapshot_time DESC
),

post_engagement AS (
    SELECT
        a.id AS account_id,

        ROUND(AVG(
            COALESCE(sp.like_count,0)
          + COALESCE(sp.comment_count,0)
          + COALESCE(sp.share_count,0)
        ), 2) AS avg_engagement,

        ROUND(AVG(COALESCE(sp.like_count,0)), 2) AS avg_likes_per_post,
        ROUND(AVG(COALESCE(sp.comment_count,0)), 2) AS avg_comments_per_post,

        -- NEW
        ROUND(AVG(COALESCE(sp.share_count,0)), 2) AS avg_shares_per_post,

        COUNT(sp.id) AS posts_last_3m

    FROM social_accounts a
    LEFT JOIN social_posts sp
        ON sp.account_id = a.id
       AND sp.publish_time >= NOW() - INTERVAL '3 months'
    GROUP BY a.id
),

activity AS (
    SELECT
        a.id AS account_id,
        ROUND(COUNT(sp.id)::numeric / 3.0, 2) AS posts_per_month
    FROM social_accounts a
    LEFT JOIN social_posts sp
        ON sp.account_id = a.id
       AND sp.publish_time >= NOW() - INTERVAL '3 months'
    GROUP BY a.id
),

growth AS (
    SELECT
        account_id,
        ROUND(
            COALESCE(
                (MAX(follower_count) - MIN(follower_count))::numeric
                / NULLIF(MIN(follower_count), 0),
            0.0)
        , 4) AS growth_rate,

        -- NEW: absolute growth
        (MAX(follower_count) - MIN(follower_count)) AS follower_delta

    FROM social_account_metrics
    WHERE snapshot_time >= NOW() - INTERVAL '3 months'
    GROUP BY account_id
),

account_metrics AS (
    SELECT
        a.id AS account_id,
        a.competitor_id,
        a.platform as platform,

        lam.follower_count,

        LOG(1 + lam.follower_count)::numeric AS reach_score,

        COALESCE(pe.avg_engagement, 0.0) AS avg_engagement,

        ROUND(
            COALESCE(pe.avg_engagement, 0.0)
            / NULLIF(lam.follower_count::numeric, 0),
        6) AS engagement_rate,

        pe.avg_likes_per_post,
        pe.avg_comments_per_post,
        pe.avg_shares_per_post,

        COALESCE(act.posts_per_month, 0.0) AS posts_per_month,
        COALESCE(g.growth_rate, 0.0) AS growth_rate,
        COALESCE(g.follower_delta, 0) AS follower_delta,

        pe.posts_last_3m

    FROM social_accounts a
    JOIN latest_account_metrics lam ON lam.account_id = a.id
    LEFT JOIN post_engagement pe ON pe.account_id = a.id
    LEFT JOIN activity act ON act.account_id = a.id
    LEFT JOIN growth g ON g.account_id = a.id
),

normalized AS (
    SELECT
        *,
        COALESCE(
            (reach_score - MIN(reach_score) OVER(PARTITION BY platform))
            / NULLIF(
                MAX(reach_score) OVER(PARTITION BY platform)
              - MIN(reach_score) OVER(PARTITION BY platform), 0),
        0) AS reach_norm,

        COALESCE(
            (engagement_rate - MIN(engagement_rate) OVER(PARTITION BY platform))
            / NULLIF(
                MAX(engagement_rate) OVER(PARTITION BY platform)
              - MIN(engagement_rate) OVER(PARTITION BY platform), 0),
        0) AS engagement_norm,

        COALESCE(
            (posts_per_month - MIN(posts_per_month) OVER(PARTITION BY platform))
            / NULLIF(
                MAX(posts_per_month) OVER(PARTITION BY platform)
              - MIN(posts_per_month) OVER(PARTITION BY platform), 0),
        0) AS activity_norm,

        COALESCE(
            (growth_rate - MIN(growth_rate) OVER(PARTITION BY platform))
            / NULLIF(
                MAX(growth_rate) OVER(PARTITION BY platform)
              - MIN(growth_rate) OVER(PARTITION BY platform), 0),
        0) AS growth_norm

    FROM account_metrics
),

account_scores AS (
    SELECT
        *,

        ROUND(
            0.35 * engagement_norm +
            0.25 * reach_norm +
            0.20 * activity_norm +
            0.20 * growth_norm
        , 4) AS account_score,

        ROUND(posts_per_month * avg_engagement, 2) AS engagement_per_month,

        ROUND(
            ((posts_per_month * avg_engagement)
            / NULLIF(follower_count::numeric, 0)) * 1000
        , 2) AS engagement_per_1k_followers,

        ROUND(
            (
                ((posts_per_month * avg_engagement)
                / NULLIF(follower_count::numeric, 0)) * 1000
            ) * growth_rate
        , 4) AS performance_index,

        -- NEW: consistency score (posting regularity proxy)
        ROUND(
            posts_last_3m::numeric / 90.0
        , 4) AS posting_consistency

    FROM normalized
),

competitor_scores AS (
    SELECT
        competitor_id,
        platform,

        ROUND(
            COALESCE(
                SUM(account_score * follower_count)
                / NULLIF(SUM(follower_count), 0),
            0)
        , 4) AS score,

        ROUND(AVG(engagement_norm), 4) AS engagement_score,
        ROUND(AVG(reach_norm), 4) AS reach_score,
        ROUND(AVG(activity_norm), 4) AS activity_score,
        ROUND(AVG(growth_norm), 4) AS growth_score,

        ROUND(AVG(avg_likes_per_post), 2) AS avg_likes_per_post,
        ROUND(AVG(avg_comments_per_post), 2) AS avg_comments_per_post,
        ROUND(AVG(avg_shares_per_post), 2) AS avg_shares_per_post,

        ROUND(
            SUM(posts_per_month * follower_count)
            / NULLIF(SUM(follower_count), 0)
        , 2) AS posts_per_month,

        ROUND(
            SUM(engagement_per_month * follower_count)
            / NULLIF(SUM(follower_count), 0)
        , 2) AS engagement_per_month,

        ROUND(AVG(engagement_per_1k_followers), 2) AS engagement_per_1k_followers,
        ROUND(AVG(performance_index), 4) AS performance_index,

        -- NEW
        SUM(follower_delta) AS follower_growth_absolute,
        ROUND(AVG(posting_consistency), 4) AS posting_consistency

    FROM account_scores
    GROUP BY competitor_id, platform
)

SELECT * FROM competitor_scores;

CREATE TABLE competitor_social_score_history (
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

CREATE UNIQUE INDEX idx_ts_competitor_time_unique
ON competitor_social_score_history (competitor_id, snapshot_date DESC, platform);

CREATE MATERIALIZED VIEW competitor_social_time_series AS
WITH base AS (
    SELECT
        *,
        
        -- previous values
        LAG(score) OVER w AS prev_score,
        LAG(score, 2) OVER w AS prev_score_2

    FROM competitor_social_score_history
    WINDOW w AS (
        PARTITION BY competitor_id, platform
        ORDER BY snapshot_date
    )
),

deltas AS (
    SELECT
        *,

        -- 1. Trend (first derivative)
        ROUND(score - prev_score, 4) AS score_delta,

        -- 2. Acceleration (second derivative)
        ROUND(
            (score - prev_score) - (prev_score - prev_score_2),
        4) AS score_acceleration

    FROM base
),

rolling AS (
    SELECT
        *,

        -- 3. Momentum (avg delta over last 7 snapshots)
        ROUND(
            AVG(score_delta) OVER (
                PARTITION BY competitor_id, platform
                ORDER BY snapshot_date
                ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
            ),
        4) AS momentum,

        -- 4. Volatility (stddev of score)
        ROUND(
            STDDEV(score) OVER (
                PARTITION BY competitor_id, platform
                ORDER BY snapshot_date
                ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
            ),
        4) AS volatility,

        -- 5. Rolling average (smoothing)
        ROUND(
            AVG(score) OVER (
                PARTITION BY competitor_id, platform
                ORDER BY snapshot_date
                ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
            ),
        4) AS score_7d_avg,

        -- 6. Longer-term trend (30 periods if available)
        ROUND(
            AVG(score) OVER (
                PARTITION BY competitor_id, platform
                ORDER BY snapshot_date
                ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
            ),
        4) AS score_30d_avg

    FROM deltas
),

final AS (
    SELECT
        *,

        -- 7. Stability score (inverse volatility)
        ROUND(
            1.0 / NULLIF(volatility + 0.0001, 0),
        4) AS stability_score,

        -- 8. Composite "momentum-weighted score"
        ROUND(
            0.6 * score +
            0.25 * COALESCE(momentum, 0) +
            0.15 * (1.0 / NULLIF(volatility + 0.0001, 0)),
        4) AS composite_score,

        -- 9. Direction label
        CASE
            WHEN score_delta > 0.01 THEN 'up'
            WHEN score_delta < -0.01 THEN 'down'
            ELSE 'flat'
        END AS trend_direction,

        -- 10. Momentum label
        CASE
            WHEN momentum > 0.01 THEN 'accelerating'
            WHEN momentum < -0.01 THEN 'declining'
            ELSE 'stable'
        END AS momentum_state

    FROM rolling
)

SELECT * FROM final;

SELECT create_hypertable(
    'competitor_social_score_history',
    'snapshot_date',
    chunk_time_interval => INTERVAL '7 days'
);



CREATE MATERIALIZED VIEW competitor_social_forecast_regression AS
WITH trend AS (
    SELECT
        competitor_id,
        platform,
        snapshot_date,
        score,

        ROW_NUMBER() OVER (
            PARTITION BY competitor_id, platform
            ORDER BY snapshot_date
        ) AS t

    FROM competitor_social_score_history
),

regression AS (
    SELECT
        competitor_id,
        platform,

        REGR_SLOPE(score, t) AS slope,
        REGR_INTERCEPT(score, t) AS intercept

    FROM trend
    GROUP BY competitor_id, platform
)

SELECT
    r.competitor_id,
    r.platform,

    CURRENT_DATE AS forecast_date,

    (r.intercept + r.slope * (MAX(t) + 7))
        AS forecast_score_7d,

    (r.intercept + r.slope * (MAX(t) + 30))
        AS forecast_score_30d,

    r.slope AS trend_slope

FROM regression r
JOIN trend t
    USING (competitor_id, platform)

GROUP BY
    r.competitor_id,
    r.platform,
    r.intercept,
    r.slope;


CREATE MATERIALIZED VIEW competitor_social_forecast_momentum AS
SELECT
    competitor_id,
    platform,
    snapshot_date,
    score,

    momentum,

    score + momentum * 7 AS forecast_7d,
    score + momentum * 30 AS forecast_30d

FROM competitor_social_time_series
WHERE snapshot_date = CURRENT_DATE;


CREATE MATERIALIZED VIEW competitor_social_forecast_smoothed AS
WITH smoothed AS (
    SELECT
        competitor_id,
        platform,
        snapshot_date,
        score,

        AVG(score) OVER (
            PARTITION BY competitor_id, platform
            ORDER BY snapshot_date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS smoothed_score

    FROM competitor_social_score_history
)

SELECT
    competitor_id,
    platform,
    snapshot_date,

    smoothed_score,

    smoothed_score +
    (
        smoothed_score
        - LAG(smoothed_score) OVER w
    ) * 7 AS forecast_7d,

    smoothed_score +
    (
        smoothed_score
        - LAG(smoothed_score) OVER w
    ) * 30 AS forecast_30d

FROM smoothed

WINDOW w AS (
    PARTITION BY competitor_id, platform
    ORDER BY snapshot_date
);

CREATE TABLE competitor_social_ai_analysis (
    id BIGSERIAL PRIMARY KEY,

    competitor_id INT,
    platform TEXT,

    analysis_date DATE,

    ai_summary JSONB,

    created_at TIMESTAMPTZ DEFAULT NOW()
);