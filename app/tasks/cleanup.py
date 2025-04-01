import os
import logging
from datetime import datetime, timedelta
from pathlib import Path

from app.settings import get_settings

logger = logging.getLogger(__name__)


async def cleanup_downloads():
    """
    Clean up old files in the downloads directory.
    Removes files older than the configured age.
    """
    settings = get_settings()
    if not settings.cleanup_downloads_enabled:
        logger.info("Downloads cleanup is disabled")
        return

    downloads_dir = Path("./downloads")
    if not downloads_dir.exists():
        logger.warning("Downloads directory does not exist")
        return

    cutoff_date = datetime.now() - timedelta(days=settings.cleanup_downloads_age_days)
    removed_count = 0

    try:
        for file_path in downloads_dir.rglob("*"):
            if file_path.is_file():
                file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_mtime < cutoff_date:
                    try:
                        file_path.unlink()
                        removed_count += 1
                        logger.debug(f"Removed old file: {file_path}")
                    except Exception as e:
                        logger.error(
                            f"Error removing file {file_path}: {str(e)}")

        logger.info(
            f"Cleanup completed. Removed {removed_count} files older than {settings.cleanup_downloads_age_days} days")
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
