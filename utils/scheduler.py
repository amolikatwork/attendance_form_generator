from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def cleanup_old_files():
    """
    Scheduled job to clean up old upload and output files (older than 7 days).
    """
    from pathlib import Path
    import shutil
    
    cutoff_date = datetime.utcnow() - timedelta(days=7)
    
    # Cleanup uploads
    uploads_dir = Path('uploads')
    if uploads_dir.exists():
        for file in uploads_dir.iterdir():
            if file.is_file() and datetime.fromtimestamp(file.stat().st_mtime) < cutoff_date:
                try:
                    file.unlink()
                    logger.info(f"Deleted old upload: {file}")
                except Exception as e:
                    logger.error(f"Error deleting {file}: {str(e)}")
    
    # Cleanup outputs
    outputs_dir = Path('outputs')
    if outputs_dir.exists():
        for folder in outputs_dir.iterdir():
            if folder.is_dir() and datetime.fromtimestamp(folder.stat().st_mtime) < cutoff_date:
                try:
                    shutil.rmtree(folder)
                    logger.info(f"Deleted old output: {folder}")
                except Exception as e:
                    logger.error(f"Error deleting {folder}: {str(e)}")


def start_scheduler():
    """Start background scheduler."""
    if not scheduler.running:
        # Add job to run cleanup daily at 2 AM
        scheduler.add_job(
            cleanup_old_files,
            'cron',
            hour=2,
            minute=0,
            id='cleanup_old_files',
            name='Cleanup old files'
        )
        
        scheduler.start()
        logger.info("Background scheduler started")


def stop_scheduler():
    """Stop background scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Background scheduler stopped")
