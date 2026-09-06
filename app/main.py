from pathlib import Path
import subprocess
import uuid
from urllib.parse import urlparse

from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse, PlainTextResponse, Response
from fastapi.templating import Jinja2Templates

app = FastAPI(title="InstaTone")
templates = Jinja2Templates(directory="app/templates")

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {
    ".mp3", ".wav", ".m4a", ".aac",
    ".mp4", ".mov", ".webm", ".mkv"
}


def detect_platform(url: str) -> str:
    try:
        hostname = urlparse(url).hostname

        if not hostname:
            return "Unknown"

        hostname = hostname.lower()

        if "youtube.com" in hostname or "youtu.be" in hostname:
            return "YouTube"

        if "instagram.com" in hostname:
            return "Instagram"

        if "facebook.com" in hostname or "fb.watch" in hostname:
            return "Facebook"

        if "tiktok.com" in hostname:
            return "TikTok"

        if "twitter.com" in hostname or "x.com" in hostname:
            return "X / Twitter"

        if "reddit.com" in hostname:
            return "Reddit"

        if "vimeo.com" in hostname:
            return "Vimeo"

        if "dailymotion.com" in hostname:
            return "Dailymotion"

        return "Other / yt-dlp"

    except Exception:
        return "Unknown"


@app.get("/googlead5e816e80705d3c.html")
async def google_verification():
    return FileResponse(
        str(Path(__file__).resolve().parent / "templates" / "googlead5e816e80705d3c.html"),
        media_type="text/html"
    )


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html"
    )



# ============================================================
# WEBSITE PAGES
# ============================================================

@app.get("/faq", response_class=HTMLResponse)
async def faq_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="faq.html"
    )


@app.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="privacy.html"
    )


@app.get("/terms", response_class=HTMLResponse)
async def terms_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="terms.html"
    )


@app.get("/copyright", response_class=HTMLResponse)
async def copyright_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="copyright.html"
    )


@app.get("/contact", response_class=HTMLResponse)
async def contact_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="contact.html"
    )


# ============================================================
# ABOUT PAGE
# ============================================================

@app.get("/about", response_class=HTMLResponse)
async def about_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="about.html"
    )
# ============================================================
# 404 PAGE
# ============================================================

@app.exception_handler(404)
async def not_found(request: Request, exc):
    return templates.TemplateResponse(
        request=request,
        name="404.html",
        status_code=404
    )


@app.exception_handler(404)
async def not_found(request: Request, exc):
    return templates.TemplateResponse(
        request=request,
        name="404.html",
        status_code=404
    )
# ============================================================
# SEO FILES
# ============================================================

@app.get("/robots.txt")
async def robots_txt():
    return PlainTextResponse(
        """User-agent: *
Allow: /

Sitemap: http://127.0.0.1:8000/sitemap.xml
"""
    )


@app.get("/sitemap.xml")
async def sitemap_xml():
    return Response(
        content="""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">

    <url>
        <loc>http://127.0.0.1:8000/</loc>
    </url>

    <url>
        <loc>http://127.0.0.1:8000/faq</loc>
    </url>

    <url>
        <loc>http://127.0.0.1:8000/privacy</loc>
    </url>

    <url>
        <loc>http://127.0.0.1:8000/terms</loc>
    </url>

    <url>
        <loc>http://127.0.0.1:8000/copyright</loc>
    </url>

    <url>
        <loc>http://127.0.0.1:8000/contact</loc>
    </url>

    <url>
        <loc>http://127.0.0.1:8000/guides/how-to-make-a-ringtone</loc>
    </url>

</urlset>
""",
        media_type="application/xml"
    )
# ============================================================
# LOCAL UPLOAD
# ============================================================

@app.post("/create-ringtone")
async def create_ringtone(
    file: UploadFile = File(...),
    start: float = Form(0),
    duration: float = Form(30)
):
    file_id = uuid.uuid4().hex

    input_ext = Path(
        file.filename or ""
    ).suffix.lower()

    if input_ext not in ALLOWED_EXTENSIONS:
        return {
            "error": "Unsupported file type.",
            "details": (
                "Supported files: MP3, WAV, M4A, AAC, "
                "MP4, MOV, WEBM and MKV."
            )
        }

    input_file = (
        UPLOAD_DIR /
        f"{file_id}{input_ext}"
    )

    output_file = (
        OUTPUT_DIR /
        f"ringtone_{file_id}.mp3"
    )

    try:

        with input_file.open("wb") as buffer:

            while chunk := await file.read(
                1024 * 1024
            ):
                buffer.write(chunk)

    except Exception as e:

        input_file.unlink(
            missing_ok=True
        )

        return {
            "error": "Could not save uploaded file.",
            "details": str(e)
        }

    return process_audio(
        input_file,
        output_file,
        start,
        duration
    )


# ============================================================
# DOWNLOAD MEDIA FOR URL PREVIEW
# ============================================================

@app.post("/preview-from-url")
async def preview_from_url(
    url: str = Form(...)
):

    url = url.strip()

    if not url.startswith(
        ("http://", "https://")
    ):
        return {
            "error": "Please enter a valid URL."
        }

    platform = detect_platform(url)

    file_id = uuid.uuid4().hex

    output_template = (
        UPLOAD_DIR /
        f"{file_id}.%(ext)s"
    )

    command = [
        "yt-dlp",

        "--no-playlist",

        "-f",
        "bestaudio/best",

        "--no-write-thumbnail",

        "-o",
        str(output_template),

        url
    ]

    try:

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=300
        )

    except subprocess.TimeoutExpired:

        return {
            "error": "Download timed out.",
            "platform": platform,
            "details": (
                "The website took too long to respond."
            )
        }

    except FileNotFoundError:

        return {
            "error": "yt-dlp is not installed.",
            "platform": platform,
            "details": (
                "Install yt-dlp using: "
                "pip install -U yt-dlp"
            )
        }

    except Exception as e:

        return {
            "error": "Unexpected download error.",
            "platform": platform,
            "details": str(e)
        }

    if result.returncode != 0:

        error_text = (
            result.stderr.strip()
            or result.stdout.strip()
        )

        return {
            "error": friendly_download_error(
                platform,
                error_text
            ),
            "platform": platform,
            "details": error_text[-2000:]
        }

    downloaded_files = [
        f
        for f in UPLOAD_DIR.glob(
            f"{file_id}.*"
        )
        if (
            f.is_file()
            and "%(" not in f.name
            and f.suffix.lower()
            in ALLOWED_EXTENSIONS
        )
    ]

    if not downloaded_files:

        return {
            "error": (
                "Download completed, but "
                "the media file could not be found."
            ),
            "platform": platform
        }

    input_file = downloaded_files[0]

    return {
        "success": True,
        "filename": input_file.name,
        "platform": platform
    }


# ============================================================
# SERVE URL PREVIEW FILE
# ============================================================

@app.get("/preview/{filename}")
async def preview_file(filename: str):

    safe_filename = Path(filename).name

    if safe_filename != filename:
        return {
            "error": "Invalid filename."
        }

    file_path = (
        UPLOAD_DIR /
        safe_filename
    )

    if not file_path.exists():
        return {
            "error": "Preview file not found."
        }

    if file_path.suffix.lower() not in ALLOWED_EXTENSIONS:
        return {
            "error": "Unsupported preview file."
        }

    media_types = {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
        ".aac": "audio/aac",
        ".webm": "audio/webm",
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".mkv": "video/x-matroska"
    }

    return FileResponse(
        path=file_path,
        media_type=media_types.get(
            file_path.suffix.lower(),
            "application/octet-stream"
        )
    )


# ============================================================
# CREATE RINGTONE FROM URL
# ============================================================

@app.post("/create-from-url")
async def create_from_url(
    url: str = Form(...),
    start: float = Form(0),
    duration: float = Form(30),
    preview_filename: str | None = Form(None)
):

    url = url.strip()

    if not url.startswith(
        ("http://", "https://")
    ):
        return {
            "error": "Please enter a valid URL."
        }

    platform = detect_platform(url)

    file_id = uuid.uuid4().hex

    output_file = (
        OUTPUT_DIR /
        f"ringtone_{file_id}.mp3"
    )

    # --------------------------------------------------------
    # If the user already loaded a URL preview, reuse it.
    # This avoids downloading the same media twice.
    # --------------------------------------------------------

    input_file = None

    if preview_filename:

        safe_filename = Path(
            preview_filename
        ).name

        candidate = (
            UPLOAD_DIR /
            safe_filename
        )

        if (
            safe_filename == preview_filename
            and candidate.exists()
            and candidate.suffix.lower()
            in ALLOWED_EXTENSIONS
        ):

            input_file = candidate

    # --------------------------------------------------------
    # If no preview file is available, download the URL now.
    # --------------------------------------------------------

    if input_file is None:

        output_template = (
            UPLOAD_DIR /
            f"{file_id}.%(ext)s"
        )

        command = [
            "yt-dlp",

            "--no-playlist",

            "-f",
            "bestaudio/best",

            "--no-write-thumbnail",

            "-o",
            str(output_template),

            url
        ]

        try:

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=300
            )

        except subprocess.TimeoutExpired:

            return {
                "error": "Download timed out.",
                "platform": platform,
                "details": (
                    "The website took too long to respond."
                )
            }

        except FileNotFoundError:

            return {
                "error": "yt-dlp is not installed.",
                "platform": platform,
                "details": (
                    "Install yt-dlp using: "
                    "pip install -U yt-dlp"
                )
            }

        except Exception as e:

            return {
                "error": "Unexpected download error.",
                "platform": platform,
                "details": str(e)
            }

        if result.returncode != 0:

            error_text = (
                result.stderr.strip()
                or result.stdout.strip()
            )

            return {
                "error": friendly_download_error(
                    platform,
                    error_text
                ),
                "platform": platform,
                "details": error_text[-2000:]
            }

        downloaded_files = [
            f
            for f in UPLOAD_DIR.glob(
                f"{file_id}.*"
            )
            if (
                f.is_file()
                and "%(" not in f.name
                and f.suffix.lower()
                in ALLOWED_EXTENSIONS
            )
        ]

        if not downloaded_files:

            return {
                "error": (
                    "Download completed, but "
                    "the media file could not be found."
                ),
                "platform": platform
            }

        input_file = downloaded_files[0]

    result_data = process_audio(
        input_file,
        output_file,
        start,
        duration
    )

    if isinstance(result_data, dict):
        result_data["platform"] = platform

    return result_data


# ============================================================
# FRIENDLY YT-DLP ERRORS
# ============================================================

def friendly_download_error(
    platform: str,
    error_text: str
) -> str:

    error_lower = (
        error_text or ""
    ).lower()

    if (
        "login required" in error_lower
        or "sign in" in error_lower
        or "authentication" in error_lower
    ):
        return (
            f"{platform} requires login or "
            "authentication for this media."
        )

    if (
        "private" in error_lower
        or "members-only" in error_lower
    ):
        return (
            f"This {platform} content "
            "is private or restricted."
        )

    if (
        "unsupported url" in error_lower
        or "no suitable extractor" in error_lower
    ):
        return (
            "This URL is not currently "
            "supported by yt-dlp."
        )

    if (
        "video unavailable" in error_lower
        or "content is not available" in error_lower
    ):
        return (
            f"The {platform} media is unavailable."
        )

    if (
        "age-restricted" in error_lower
        or "age restricted" in error_lower
    ):
        return (
            f"This {platform} media is age-restricted."
        )

    if (
        "geo" in error_lower
        or "not available in your country"
        in error_lower
    ):
        return (
            f"This {platform} media is region restricted."
        )

    return (
        f"Could not download this "
        f"{platform} media."
    )


# ============================================================
# AUDIO PROCESSING
# ============================================================

def process_audio(
    input_file: Path,
    output_file: Path,
    start: float,
    duration: float
):

    try:

        start = float(start)

    except (
        TypeError,
        ValueError
    ):

        start = 0

    if start < 0:
        start = 0

    try:

        duration = float(duration)

    except (
        TypeError,
        ValueError
    ):

        duration = 30

    if duration <= 0:
        duration = 30

    # Maximum ringtone duration = 60 seconds

    if duration > 60:
        duration = 60

    command = [
        "ffmpeg",

        "-y",

        "-ss",
        str(start),

        "-i",
        str(input_file),

        "-t",
        str(duration),

        "-vn",

        "-acodec",
        "libmp3lame",

        "-b:a",
        "192k",

        str(output_file)
    ]

    try:

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=120
        )

    except subprocess.TimeoutExpired:

        input_file.unlink(
            missing_ok=True
        )

        return {
            "error": "Audio processing timed out."
        }

    except FileNotFoundError:

        input_file.unlink(
            missing_ok=True
        )

        return {
            "error": (
                "FFmpeg was not found. "
                "Please check your FFmpeg installation."
            )
        }

    except Exception as e:

        input_file.unlink(
            missing_ok=True
        )

        return {
            "error": "Unexpected FFmpeg error.",
            "details": str(e)
        }

    input_file.unlink(
        missing_ok=True
    )

    if result.returncode != 0:

        return {
            "error": "Audio processing failed.",
            "details": result.stderr[-2000:]
        }

    if not output_file.exists():

        return {
            "error": "Ringtone file was not created."
        }

    return {
        "success": True,
        "filename": output_file.name
    }


# ============================================================
# RINGTONE DOWNLOAD
# ============================================================

@app.get("/download/{filename}")
async def download(filename: str):

    safe_filename = Path(
        filename
    ).name

    file_path = (
        OUTPUT_DIR /
        safe_filename
    )

    if not file_path.exists():

        return {
            "error": "File not found."
        }

    return FileResponse(
        path=file_path,
        media_type="audio/mpeg",
        filename=safe_filename
    )
