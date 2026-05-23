import logging
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from app.runner import run_scrapers
from app.services.process_anthropic import process_anthropic_markdown
from app.services.process_youtube import process_youtube_transcripts
from app.services.process_digest import process_digests
from app.services.process_email import send_digest_email

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def run_pipeline(hours: int = 24, top_n: int = 10) -> dict:
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("AI News Aggregator Pipeline")
    logger.info(f"Started at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Scrape window: last {hours}h — top {top_n} articles")
    logger.info("=" * 60)

    results = {
        "start_time": start_time.isoformat(),
        "scraping": {},
        "processing": {},
        "digests": {},
        "email": {},
        "success": False,
    }

    # Step 1 — Scrape
    logger.info("\n[1/5] Scraping sources...")
    scraping = run_scrapers(hours=hours)
    results["scraping"] = {
        "youtube":   len(scraping.get("youtube", [])),
        "anthropic": len(scraping.get("anthropic", [])),
    }
    logger.info(f"✓ YouTube: {results['scraping']['youtube']}  Anthropic: {results['scraping']['anthropic']}")

    # Step 2 — Process Anthropic markdown
    logger.info("\n[2/5] Processing Anthropic markdown...")
    anthropic = process_anthropic_markdown()
    results["processing"]["anthropic"] = anthropic
    logger.info(f"✓ {anthropic['processed']} processed, {anthropic['failed']} failed")

    # Step 3 — Process YouTube transcripts
    logger.info("\n[3/5] Processing YouTube transcripts...")
    youtube = process_youtube_transcripts()
    results["processing"]["youtube"] = youtube
    logger.info(f"✓ {youtube['processed']} processed, {youtube['unavailable']} unavailable")

    # Step 4 — Generate digests
    logger.info("\n[4/5] Generating digests...")
    digest = process_digests()
    results["digests"] = digest
    logger.info(f"✓ {digest['processed']} digests created, {digest['failed']} failed")

    # Step 5 — Send email
    logger.info("\n[5/5] Sending email digest...")
    email = send_digest_email(hours=hours, top_n=top_n)
    results["email"] = email

    if email["success"]:
        logger.info(f"✓ Email sent — {email['articles_count']} articles")
        results["success"] = True
    else:
        logger.error(f"✗ Email failed: {email.get('error', 'unknown')}")

    # Summary
    duration = (datetime.now() - start_time).total_seconds()
    results["duration_seconds"] = duration
    logger.info("\n" + "=" * 60)
    logger.info("Summary")
    logger.info("=" * 60)
    logger.info(f"Duration  : {duration:.1f}s")
    logger.info(f"Scraped   : {results['scraping']}")
    logger.info(f"Processed : {results['processing']}")
    logger.info(f"Digests   : {results['digests']}")
    logger.info(f"Email     : {'✓ Sent' if results['success'] else '✗ Failed'}")
    logger.info("=" * 60)

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AI News Aggregator Pipeline")
    parser.add_argument("--hours", type=int, default=24, help="Scrape window in hours (default: 24)")
    parser.add_argument("--top-n", type=int, default=10, help="Top N articles to include (default: 10)")
    args = parser.parse_args()

    result = run_pipeline(hours=args.hours, top_n=args.top_n)
    sys.exit(0 if result["success"] else 1)