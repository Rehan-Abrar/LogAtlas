"""
main.py — FastAPI application.
Serves the log analysis API and the built React frontend as static files.

Single-command run (after frontend build):
    uvicorn main:app --reload
"""

import os
import sys
import tempfile
import logging
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Add backend dir to path so imports work
sys.path.insert(0, os.path.dirname(__file__))

from parser import parse_log_file
from analyzer import analyze

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Log Analyzer API", version="1.0.0")

# Allow dev server (localhost:5173) during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_FILE_SIZE = 200 * 1024 * 1024  # 200MB


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@app.post("/api/analyze")
async def analyze_log(file: UploadFile = File(...)):
    """
    Accept a log file upload, parse it, and return analysis results.
    Handles files of any size gracefully.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    # Stream to a temp file to avoid loading everything into memory at once
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            suffix=".log",
            delete=False,
            prefix="loganalyzer_"
        ) as tmp:
            tmp_path = tmp.name
            bytes_written = 0
            chunk_size = 64 * 1024  # 64KB chunks

            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > MAX_FILE_SIZE:
                    os.unlink(tmp_path)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Maximum size is {MAX_FILE_SIZE // 1024 // 1024}MB"
                    )
                tmp.write(chunk)

        logger.info(f"Analyzing file: {file.filename} ({bytes_written / 1024:.1f} KB)")

        parse_result = parse_log_file(tmp_path)
        result = analyze(parse_result)
        result["filename"] = file.filename
        result["file_size_kb"] = round(bytes_written / 1024, 1)

        logger.info(
            f"Done: {parse_result.total_lines} lines, "
            f"{len(parse_result.entries)} parsed, "
            f"{parse_result.malformed_count} malformed"
        )

        return JSONResponse(content=result)

    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"File handling error: {str(e)}")
    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
    finally:
        try:
            if 'tmp_path' in locals() and os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass


@app.get("/api/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Serve built React frontend
# ---------------------------------------------------------------------------

FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"

if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/", response_class=FileResponse)
    def serve_index():
        return FileResponse(FRONTEND_DIST / "index.html")

    @app.get("/{full_path:path}", response_class=FileResponse)
    def serve_spa(full_path: str):
        # API routes are handled above; everything else serves index.html
        file_path = FRONTEND_DIST / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIST / "index.html")
else:
    @app.get("/")
    def no_frontend():
        return {
            "message": "Frontend not built. Run: cd frontend && npm install && npm run build",
            "api_docs": "/docs"
        }