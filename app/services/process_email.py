import logging
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from app.agent.email_agent import EmailAgent, RankedArticleDetail, EmailDigestResponse
from app.agent.curator_agent import CuratorAgent
from app.profiles.user_profile import USER_PROFILE
from app.database.repository import Repository
from app.services.email import send_email, digest_to_html

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def generate_email_digest(hours: int = 24, top_n: int = 10) -> EmailDigestResponse:
    curator = CuratorAgent(USER_PROFILE)
    email_agent = EmailAgent(USER_PROFILE)
    repo = Repository()

    digests = repo.get_recent_digests(hours=hours)
    total = len(digests)

    if total == 0:
        logger.warning(f"No digests found from the last {hours} hours")
        raise ValueError("No digests available")

    logger.info(f"Ranking {total} digests for email generation")
    ranked_articles = curator.rank_digests(digests)

    if not ranked_articles:
        logger.error("Failed to rank digests")
        raise ValueError("Failed to rank articles")

    logger.info(f"Generating email digest with top {top_n} articles")

    article_details = [
        RankedArticleDetail(
            digest_id=a.digest_id,
            rank=a.rank,
            relevance_score=a.relevance_score,
            reasoning=a.reasoning,
            title=next((d["title"] for d in digests if d["id"] == a.digest_id), ""),
            summary=next((d["summary"] for d in digests if d["id"] == a.digest_id), ""),
            url=next((d["url"] for d in digests if d["id"] == a.digest_id), ""),
            article_type=next((d["article_type"] for d in digests if d["id"] == a.digest_id), "")
        )
        for a in ranked_articles
    ]

    email_digest = email_agent.create_email_digest_response(
        ranked_articles=article_details,
        total_ranked=len(ranked_articles),
        limit=top_n
    )

    logger.info("Email digest generated successfully")
    logger.info(f"\n=== Email Introduction ===")
    logger.info(email_digest.introduction.greeting)
    logger.info(f"\n{email_digest.introduction.introduction}")

    return email_digest


def send_no_updates_email(api_key: str, to_email: str) -> dict:
    today = datetime.now().strftime("%B %d, %Y")
    subject = f"AI News Digest - {today} (No new updates)"
    body_text = (
        f"Hi,\n\nNo new AI articles were found for {today}. "
        f"We'll check again on the next scheduled run.\n\nYour AI News Aggregator"
    )
    body_html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333;">
    <h2 style="color: #6366f1;">📰 AI News Digest — {today}</h2>
    <p>Hi there,</p>
    <p>No new AI articles were found for today. The scrapers came up empty — we'll be back with updates soon.</p>
    <hr style="border: none; border-top: 1px solid #e5e5e5; margin: 20px 0;">
    <p style="color: #9ca3af; font-size: 0.85rem;">Your AI News Aggregator</p>
</body>
</html>"""

    send_email(
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        recipients=[to_email],
        api_key=api_key,
    )
    logger.info("No-updates email sent.")
    return {"success": True, "subject": subject, "articles_count": 0}


def send_digest_email(hours: int = 24, top_n: int = 10) -> dict:
    api_key  = os.environ.get("RESEND_API_KEY")
    to_email = os.environ.get("MY_EMAIL")

    try:
        result = generate_email_digest(hours=hours, top_n=top_n)
        subject = (
            f"Daily AI News Digest - "
            f"{result.introduction.greeting.split('for ')[-1] if 'for ' in result.introduction.greeting else 'Today'}"
        )

        send_email(
            subject=subject,
            body_text=result.to_markdown(),
            body_html=digest_to_html(result),
            recipients=[to_email],
            api_key=api_key,
        )

        logger.info("Email sent successfully!")
        return {"success": True, "subject": subject, "articles_count": len(result.articles)}

    except ValueError as e:
        if "No digests available" in str(e) or "Failed to rank" in str(e):
            logger.warning(f"{e} — sending no-updates email instead")
            return send_no_updates_email(api_key=api_key, to_email=to_email)
        logger.error(f"Error sending email: {e}")
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    result = send_digest_email(hours=240, top_n=10)
    if result["success"]:
        print("\n=== Email Digest Sent ===")
        print(f"Subject: {result['subject']}")
        print(f"Articles: {result['articles_count']}")
    else:
        print(f"Error: {result['error']}")