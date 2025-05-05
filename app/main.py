# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.api.routes import api_router
from app.utils.logger import get_logger
from app.utils.config import get_settings

logger = get_logger(__name__)
settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Web Test Automation API"
)

# CORS middleware (adjust origins as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to your frontend domain(s) in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="app"), name="static")

# Mount screenshots directory
screenshots_dir = settings.browser_config.screenshot_dir
if os.path.exists(screenshots_dir):
    app.mount("/screenshots", StaticFiles(directory=screenshots_dir), name="screenshots")
else:
    logger.warning(f"Screenshots directory {screenshots_dir} does not exist")

# Include all API routes
app.include_router(api_router, prefix="/api")

# Root endpoint to serve the HTML file
@app.get("/", tags=["Root"])
async def root():
    return FileResponse("app/index.html")

# Optional: custom exception handlers, startup/shutdown events, etc.
# Example:
# @