from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from contextlib import asynccontextmanager

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the scheduler when the application starts
    scheduler.start()
    yield
    # Shutdown the scheduler when the application shuts down
    scheduler.shutdown()


def init_scheduler(app: FastAPI):
    """Initialize the scheduler with the FastAPI application"""
    app.router.lifespan_context = lifespan


def add_cron_job(func, cron_expression: str, **kwargs):
    """
    Add a cron job to the scheduler
    
    Args:
        func: The function to be scheduled
        cron_expression: Cron expression (e.g., "0 0 * * *" for daily at midnight)
        **kwargs: Additional arguments to pass to the scheduler
    """
    scheduler.add_job(
        func,
        CronTrigger.from_crontab(cron_expression),
        **kwargs
    )
