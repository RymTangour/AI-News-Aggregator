import logging
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
from main import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def run_daily_pipeline(hours: int = 240, top_n: int = 10, api_key: str = None, email: str = None) -> dict:
    # Re-inject credentials into os.environ for this thread
    if api_key:
        os.environ["RESEND_API_KEY"] = api_key
    if email:
        os.environ["MY_EMAIL"] = email

    from app.runner import run_scrapers
    from app.services.process_anthropic import process_anthropic_markdown
    from app.services.process_youtube import process_youtube_transcripts
    from app.services.process_digest import process_digests
    from app.services.process_email import send_digest_email

    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info(f"Pipeline started at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    results = {
        "start_time": start_time.isoformat(),
        "scraping": {}, "processing": {}, "digests": {}, "email": {},
        "success": False
    }

    try:
        logger.info("[1/5] Scraping articles...")
        scraping_results = run_scrapers(hours=hours)
        results["scraping"] = {
            "youtube":   len(scraping_results.get("youtube", [])),
            "openai":    len(scraping_results.get("openai", [])),
            "anthropic": len(scraping_results.get("anthropic", []))
        }
        logger.info(f"✓ YouTube: {results['scraping']['youtube']}  OpenAI: {results['scraping']['openai']}  Anthropic: {results['scraping']['anthropic']}")

        logger.info("[2/5] Processing Anthropic markdown...")
        anthropic_result = process_anthropic_markdown()
        results["processing"]["anthropic"] = anthropic_result
        logger.info(f"✓ {anthropic_result['processed']} processed, {anthropic_result['failed']} failed")

        logger.info("[3/5] Processing YouTube transcripts...")
        youtube_result = process_youtube_transcripts()
        results["processing"]["youtube"] = youtube_result
        logger.info(f"✓ {youtube_result['processed']} processed, {youtube_result['unavailable']} unavailable")

        logger.info("[4/5] Creating digests...")
        digest_result = process_digests()
        results["digests"] = digest_result
        logger.info(f"✓ {digest_result['processed']} digests, {digest_result['failed']} failed")

        logger.info("[5/5] Sending email digest...")
        email_result = send_digest_email(hours=hours, top_n=top_n)
        results["email"] = email_result

        if email_result["success"]:
            logger.info(f"✓ Email sent with {email_result['articles_count']} articles")
            results["success"] = True
        else:
            logger.error(f"✗ Email failed: {email_result.get('error', 'Unknown')}")

    except Exception as e:
        logger.error(f"Pipeline crashed: {e}", exc_info=True)
        results["error"] = str(e)

    duration = (datetime.now() - start_time).total_seconds()
    results["duration_seconds"] = duration
    logger.info(f"Done in {duration:.1f}s — {'SUCCESS' if results['success'] else 'FAILED'}")
    return results


if __name__ == "__main__":
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.interval import IntervalTrigger
    except ImportError:
        print("APScheduler not installed. Run: pip install apscheduler")
        sys.exit(1)

    api_key  = os.environ.get("RESEND_API_KEY")
    my_email = os.environ.get("MY_EMAIL")

    if not api_key or not my_email:
        logger.error("RESEND_API_KEY and MY_EMAIL must be set.")
        sys.exit(1)

    hours            = int(os.environ.get("PIPELINE_HOURS", "24"))
    top_n            = int(os.environ.get("PIPELINE_TOP_N", "10"))
    interval_minutes = int(os.environ.get("SCHEDULER_INTERVAL_MIN", "1440"))

    logger.info(f"Scheduler starting — every {interval_minutes} min — sending to {my_email}")
    logger.info("Running first pipeline immediately...")
    run_daily_pipeline(hours=hours, top_n=top_n, api_key=api_key, email=my_email)

    scheduler = BlockingScheduler()
    scheduler.add_job(
        func=run_daily_pipeline,
        trigger=IntervalTrigger(minutes=interval_minutes),
        # Pass credentials explicitly into every scheduled run
        kwargs={"hours": hours, "top_n": top_n, "api_key": api_key, "email": my_email},
        id="pipeline_job",
        name="AI digest pipeline",
        replace_existing=True,
    )

    logger.info(f"Next run in {interval_minutes} minute(s). Ctrl+C to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")