"""Social Intelligence router."""

from fastapi import APIRouter, Depends, Query

from app.db.pool import acquire
from app.dependencies import get_current_user

router = APIRouter(prefix="/social", tags=["social"])


@router.get("/summary")
async def social_summary(user: dict = Depends(get_current_user)):
    """Current social scores per competitor per platform."""
    async with acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                css.competitor_id, c.domain, c.name,
                css.platform,
                css.score, css.engagement_score,
                css.reach_score, css.activity_score, css.growth_score,
                css.posts_per_month, css.engagement_per_month,
                css.engagement_per_1k_followers,
                css.avg_likes_per_post, css.avg_comments_per_post,
                css.avg_shares_per_post,
                css.follower_growth_absolute, css.posting_consistency
            FROM competitor_social_score css
            JOIN competitors c ON c.id = css.competitor_id
            ORDER BY css.score DESC
            """
        )
    return [dict(r) for r in rows]


@router.get("/time-series/{competitor_id}")
async def social_time_series(
    competitor_id: int,
    platform: str | None = None,
    user: dict = Depends(get_current_user),
):
    """Score time series with momentum and trend for a competitor."""
    platform_filter = "AND platform = $2" if platform else ""
    params = [competitor_id]
    if platform:
        params.append(platform)

    async with acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT
                snapshot_date, platform, score,
                score_delta, score_acceleration,
                momentum, volatility, score_7d_avg, score_30d_avg,
                stability_score, composite_score,
                trend_direction, momentum_state
            FROM competitor_social_time_series
            WHERE competitor_id = $1
            {platform_filter}
            ORDER BY platform, snapshot_date ASC
            """,
            *params,
        )
    return [dict(r) for r in rows]


@router.get("/forecast/{competitor_id}")
async def social_forecast(competitor_id: int, user: dict = Depends(get_current_user)):
    """All three forecast models (regression, momentum, smoothed) for a competitor."""
    async with acquire() as conn:
        regression = await conn.fetch(
            """
            SELECT platform, forecast_date, forecast_score_7d,
                   forecast_score_30d, trend_slope
            FROM competitor_social_forecast_regression
            WHERE competitor_id = $1
            """,
            competitor_id,
        )
        momentum = await conn.fetch(
            """
            SELECT platform, snapshot_date, score,
                   momentum, forecast_7d, forecast_30d
            FROM competitor_social_forecast_momentum
            WHERE competitor_id = $1
            """,
            competitor_id,
        )
        smoothed = await conn.fetch(
            """
            SELECT platform, snapshot_date, smoothed_score,
                   forecast_7d, forecast_30d
            FROM competitor_social_forecast_smoothed
            WHERE competitor_id = $1
            ORDER BY platform, snapshot_date DESC
            LIMIT 10
            """,
            competitor_id,
        )

    return {
        "regression": [dict(r) for r in regression],
        "momentum": [dict(r) for r in momentum],
        "smoothed": [dict(r) for r in smoothed],
    }


@router.get("/posts/{competitor_id}")
async def top_posts(
    competitor_id: int,
    platform: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    """Top posts by engagement for a competitor."""
    platform_filter = "AND sp.platform = $3" if platform else ""
    params = [competitor_id, limit]
    if platform:
        params.append(platform)

    async with acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT
                sp.external_post_id, sp.platform,
                sp.text, sp.post_url, sp.content_type,
                sp.publish_time,
                sp.like_count, sp.comment_count,
                sp.share_count, sp.view_count,
                (COALESCE(sp.like_count,0) + COALESCE(sp.comment_count,0)
                 + COALESCE(sp.share_count,0)) AS total_engagement
            FROM social_posts sp
            JOIN social_accounts sa ON sa.id = sp.account_id
            WHERE sa.competitor_id = $1
            {platform_filter}
            ORDER BY total_engagement DESC
            LIMIT $2
            """,
            *params,
        )
    return [dict(r) for r in rows]


@router.get("/ai-analysis/{competitor_id}")
async def ai_analysis(
    competitor_id: int,
    platform: str | None = None,
    user: dict = Depends(get_current_user),
):
    """Latest AI-generated social media analysis for a competitor."""
    platform_filter = "AND platform = $2" if platform else ""
    params = [competitor_id]
    if platform:
        params.append(platform)

    async with acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT id, platform, analysis_date, ai_summary, created_at
            FROM competitor_social_ai_analysis
            WHERE competitor_id = $1
            {platform_filter}
            ORDER BY analysis_date DESC
            LIMIT 5
            """,
            *params,
        )
    return [dict(r) for r in rows]


@router.get("/accounts/{competitor_id}")
async def social_accounts(
    competitor_id: int,
    user: dict = Depends(get_current_user),
):
    """Social media account profiles for a competitor."""
    async with acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                id, platform, username, display_name,
                profile_url, is_verified, is_business,
                follower_count, following_count, updated_at
            FROM social_accounts
            WHERE competitor_id = $1
            ORDER BY platform, follower_count DESC
            """,
            competitor_id,
        )
    return [dict(r) for r in rows]
