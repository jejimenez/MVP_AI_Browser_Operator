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
app.mount("/static", StaticFiles(directory="app/static"), name="static")

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
    logger.debug("Serving root endpoint")
    return FileResponse("app/static/index.html")

# New endpoint to serve the test webpage
@app.get("/web-app", tags=["Test Page"])
async def serve_test_page():
    file_path = "app/static/web-app.html"
    if os.path.exists(file_path):
        return FileResponse(file_path)
    else:
        logger.error(f"Test page not found at {file_path}")
        return {"error": "Test page not found"}

@app.get("/web-app-v2", tags=["Test Page V2"])
async def serve_test_page_v2():
    logger.debug("Serving test page: web-app-v2.html")
    file_path = "app/static/web-app-v2.html"
    if os.path.exists(file_path):
        return FileResponse(file_path)
    else:
        logger.error(f"Test page not found at {file_path}")
        return {"error": "Test page V2 not found"}