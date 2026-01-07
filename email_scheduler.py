#!/usr/bin/env python3
"""
Email Scheduler - Runs scheduled email reports
Runs continuously and triggers email reports at specified times (Israel timezone)

Schedule:
- 10:00 AM: Daily reminder for unpaid orders (sent - not paid)
- 10:00 AM: Daily sales report
- 20:00 PM: Daily new orders report (new status)
- Sunday 09:00 AM: Weekly sales summary
"""

import os
import sys
import time
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

ISRAEL_TZ = pytz.timezone('Israel')

def run_daily_reminder():
    """Run daily reminder for unpaid orders at 10:00 AM"""
    logger.info("=" * 50)
    logger.info("Running Daily Reminder for Unpaid Orders...")
    try:
        from daily_reminder import main
        result = main()
        logger.info(f"Daily reminder completed: {result}")
    except Exception as e:
        logger.error(f"Daily reminder failed: {e}")
    logger.info("=" * 50)

def run_daily_sales_report():
    """Run daily sales report at 10:00 AM"""
    logger.info("=" * 50)
    logger.info("Running Daily Sales Report...")
    try:
        from daily_sales_report import main
        result = main()
        logger.info(f"Daily sales report completed: {result}")
    except Exception as e:
        logger.error(f"Daily sales report failed: {e}")
    logger.info("=" * 50)

def run_daily_new_orders_report():
    """Run daily new orders report at 20:00"""
    logger.info("=" * 50)
    logger.info("Running Daily New Orders Report...")
    try:
        from daily_new_orders_report import main
        result = main()
        logger.info(f"Daily new orders report completed: {result}")
    except Exception as e:
        logger.error(f"Daily new orders report failed: {e}")
    logger.info("=" * 50)

def run_weekly_sales_report():
    """Run weekly sales report on Sunday at 09:00"""
    logger.info("=" * 50)
    logger.info("Running Weekly Sales Report...")
    try:
        from weekly_sales_report import main
        result = main()
        logger.info(f"Weekly sales report completed: {result}")
    except Exception as e:
        logger.error(f"Weekly sales report failed: {e}")
    logger.info("=" * 50)

def main():
    """Main scheduler function"""
    logger.info("=" * 60)
    logger.info("Email Scheduler Starting...")
    logger.info(f"Current Israel time: {datetime.now(ISRAEL_TZ).strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    
    scheduler = BlockingScheduler(timezone=ISRAEL_TZ)
    
    scheduler.add_job(
        run_daily_reminder,
        CronTrigger(hour=10, minute=0, timezone=ISRAEL_TZ),
        id='daily_reminder',
        name='Daily Reminder for Unpaid Orders (10:00 AM)',
        replace_existing=True
    )
    
    scheduler.add_job(
        run_daily_sales_report,
        CronTrigger(hour=10, minute=5, timezone=ISRAEL_TZ),
        id='daily_sales_report',
        name='Daily Sales Report (10:05 AM)',
        replace_existing=True
    )
    
    scheduler.add_job(
        run_daily_new_orders_report,
        CronTrigger(hour=20, minute=0, timezone=ISRAEL_TZ),
        id='daily_new_orders_report',
        name='Daily New Orders Report (20:00)',
        replace_existing=True
    )
    
    scheduler.add_job(
        run_weekly_sales_report,
        CronTrigger(day_of_week='sun', hour=9, minute=0, timezone=ISRAEL_TZ),
        id='weekly_sales_report',
        name='Weekly Sales Report (Sunday 09:00)',
        replace_existing=True
    )
    
    logger.info("Scheduled jobs:")
    for job in scheduler.get_jobs():
        logger.info(f"  - {job.name}")
    
    logger.info("=" * 60)
    logger.info("Scheduler is running. Press Ctrl+C to stop.")
    logger.info("=" * 60)
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")
        scheduler.shutdown()

if __name__ == "__main__":
    main()
