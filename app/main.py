from pathlib import Path
import subprocess
import time
import uuid
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

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


def cleanup_old_files(max_age_seconds: int = 1800):
    """Auto-clean files older than 30 minutes to prevent filling disk space."""
    now = time.time()
    for directory in (UPLOAD_DIR, OUTPUT_DIR):
        try:
            for item in directory.iterdir():
                if item.is_file() and (now - item.stat().st_mtime) > max_age_seconds:
                    item.unlink(missing_ok=True)
        except Exception:
            pass


def sanitize_url(url: str) -> str:
    """Strip unnecessary playlist, mix, or tracking query parameters."""
    url = url.strip()
    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()

        if "youtube.com" in hostname or "youtu.be" in hostname:
            qs = parse_qs(parsed.query)
            if "v" in qs:
                clean_query = urlencode({"v": qs["v"][0]})
                return urlunparse((parsed.scheme, parsed.netloc, "/watch", "", clean_query, ""))
            elif "youtu.be" in hostname:
                video_id = parsed.path.strip("/")
                return f"https://www.youtube.com/watch?v={video_id}"
            elif "/shorts/" in parsed.path:
                video_id = parsed.path.split("/shorts/")[1].split("/")[0].split("?")[0]
                return f"https://www.youtube.com/watch?v={video_id}"

        elif "instagram.com" in hostname:
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    except Exception:
        pass
    return url


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

        return "Other / Direct Media"
    except Exception:
        return "Unknown"


@app.get("/googlead5e816e80705d3c.html")
async def google_verification():
    return PlainTextResponse("google-site-verification: googlead5e816e80705d3c.html")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


# ============================================================
# WEBSITE PAGES
# ============================================================

@app.get("/faq", response_class=HTMLResponse)
async def faq_page(request: Request):
    return templates.TemplateResponse(request=request, name="faq.html")


@app.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request):
    return templates.TemplateResponse(request=request, name="privacy.html")


@app.get("/terms", response_class=HTMLResponse)
async def terms_page(request: Request):
    return templates.TemplateResponse(request=request, name="terms.html")


@app.get("/copyright", response_class=HTMLResponse)
async def copyright_page(request: Request):
    return templates.TemplateResponse(request=request, name="copyright.html")


@app.get("/contact", response_class=HTMLResponse)
async def contact_page(request: Request):
    return templates.TemplateResponse(request=request, name="contact.html")


@app.get("/about", response_class=HTMLResponse)
async def about_page(request: Request):
    return templates.TemplateResponse(request=request, name="about.html")


@app.get("/guides/how-to-make-a-ringtone", response_class=HTMLResponse)
async def guide_page(request: Request):
    return templates.TemplateResponse(request=request, name="guide.html")



# ============================================================
# 404 EXCEPTION HANDLER (Single definition)
# ============================================================

@app.exception_handler(404)
async def not_found(request: Request, exc):
    return templates.TemplateResponse(
        request=request,
        name="404.html",
        status_code=404
    )


# ============================================================
# SEO FILES (Dynamic Host / Scheme)
# ============================================================

def get_base_url(request: Request) -> str:
    forwarded_proto = request.headers.get("x-forwarded-proto", "https")
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or "instatone.onrender.com"
    return f"{forwarded_proto}://{host}".rstrip("/")


@app.get("/robots.txt")
async def robots_txt(request: Request):
    base_url = get_base_url(request)
    return PlainTextResponse(
        f"User-agent: *\nAllow: /\n\nSitemap: {base_url}/sitemap.xml\n"
    )


@app.get("/sitemap.xml")
async def sitemap_xml(request: Request):
    base_url = get_base_url(request)
    pages = ["", "faq", "privacy", "terms", "copyright", "contact", "about", "guides/how-to-make-a-ringtone"]
    url_tags = "\n".join(
        f"    <url>\n        <loc>{base_url}/{p}</loc>\n        <changefreq>weekly</changefreq>\n    </url>"
        for p in pages
    )
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{url_tags}
</urlset>"""
    return Response(content=xml_content, media_type="application/xml")


# ============================================================
# LOCAL UPLOAD
# ============================================================

@app.post("/create-ringtone")
async def create_ringtone(
    file: UploadFile = File(...),
    start: float = Form(0),
    duration: float = Form(30),
    format: str = Form("mp3"),
    fade_in: bool = Form(False),
    fade_out: bool = Form(False),
):
    cleanup_old_files()
    file_id = uuid.uuid4().hex

    input_ext = Path(file.filename or "").suffix.lower()
    if input_ext not in ALLOWED_EXTENSIONS:
        return {
            "error": "Unsupported file type.",
            "details": "Supported files: MP3, WAV, M4A, AAC, MP4, MOV, WEBM and MKV."
        }

    out_format = "m4r" if format.lower() == "m4r" else "mp3"
    input_file = UPLOAD_DIR / f"{file_id}{input_ext}"
    output_file = OUTPUT_DIR / f"ringtone_{file_id}.{out_format}"

    try:
        with input_file.open("wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                buffer.write(chunk)
    except Exception as e:
        input_file.unlink(missing_ok=True)
        return {
            "error": "Could not save uploaded file.",
            "details": str(e)
        }

    return process_audio(
        input_file=input_file,
        output_file=output_file,
        start=start,
        duration=duration,
        format=out_format,
        fade_in=fade_in,
        fade_out=fade_out,
    )


# ============================================================
# DOWNLOAD MEDIA FOR URL PREVIEW
# ============================================================

@app.post("/preview-from-url")
async def preview_from_url(url: str = Form(...)):
    cleanup_old_files()
    url = sanitize_url(url)

    if not url.startswith(("http://", "https://")):
        return {"error": "Please enter a valid URL."}

    platform = detect_platform(url)
    file_id = uuid.uuid4().hex
    output_template = UPLOAD_DIR / f"{file_id}.%(ext)s"

    command = [
        "yt-dlp",
        "--no-playlist",
        "--max-filesize", "50M",
        "--extractor-args", "youtube:player_client=android_vr,web_creator",
        "-f", "bestaudio/best",
        "--no-write-thumbnail",
        "-o", str(output_template),
        url
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=180
        )
    except subprocess.TimeoutExpired:
        return {
            "error": "Download timed out.",
            "platform": platform,
            "details": "The media server took too long to respond."
        }
    except FileNotFoundError:
        return {
            "error": "yt-dlp is not installed.",
            "platform": platform,
            "details": "yt-dlp binary is required for remote audio extraction."
        }
    except Exception as e:
        return {
            "error": "Unexpected download error.",
            "platform": platform,
            "details": str(e)
        }

    if result.returncode != 0:
        error_text = result.stderr.strip() or result.stdout.strip()
        return {
            "error": friendly_download_error(platform, error_text),
            "platform": platform,
            "details": error_text[-2000:]
        }

    downloaded_files = [
        f for f in UPLOAD_DIR.glob(f"{file_id}.*")
        if (
            f.is_file()
            and "%(" not in f.name
            and f.suffix.lower() in ALLOWED_EXTENSIONS
        )
    ]

    if not downloaded_files:
        return {
            "error": "Download completed, but the media file could not be found.",
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
        return {"error": "Invalid filename."}

    file_path = UPLOAD_DIR / safe_filename
    if not file_path.exists():
        return {"error": "Preview file not found."}

    if file_path.suffix.lower() not in ALLOWED_EXTENSIONS:
        return {"error": "Unsupported preview file."}

    media_types = {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
        ".m4r": "audio/x-m4r",
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
    preview_filename: str | None = Form(None),
    format: str = Form("mp3"),
    fade_in: bool = Form(False),
    fade_out: bool = Form(False),
):
    cleanup_old_files()
    url = sanitize_url(url)

    if not url.startswith(("http://", "https://")):
        return {"error": "Please enter a valid URL."}

    platform = detect_platform(url)
    file_id = uuid.uuid4().hex
    out_format = "m4r" if format.lower() == "m4r" else "mp3"
    output_file = OUTPUT_DIR / f"ringtone_{file_id}.{out_format}"

    input_file = None
    if preview_filename:
        safe_filename = Path(preview_filename).name
        candidate = UPLOAD_DIR / safe_filename
        if (
            safe_filename == preview_filename
            and candidate.exists()
            and candidate.suffix.lower() in ALLOWED_EXTENSIONS
        ):
            input_file = candidate

    if input_file is None:
        output_template = UPLOAD_DIR / f"{file_id}.%(ext)s"
        command = [
            "yt-dlp",
            "--no-playlist",
            "--max-filesize", "50M",
            "--extractor-args", "youtube:player_client=android_vr,web_creator",
            "-f", "bestaudio/best",
            "--no-write-thumbnail",
            "-o", str(output_template),
            url
        ]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=180
            )
        except subprocess.TimeoutExpired:
            return {
                "error": "Download timed out.",
                "platform": platform,
                "details": "The media server took too long to respond."
            }
        except FileNotFoundError:
            return {
                "error": "yt-dlp is not installed.",
                "platform": platform,
                "details": "yt-dlp binary is required for remote audio extraction."
            }
        except Exception as e:
            return {
                "error": "Unexpected download error.",
                "platform": platform,
                "details": str(e)
            }

        if result.returncode != 0:
            error_text = result.stderr.strip() or result.stdout.strip()
            return {
                "error": friendly_download_error(platform, error_text),
                "platform": platform,
                "details": error_text[-2000:]
            }

        downloaded_files = [
            f for f in UPLOAD_DIR.glob(f"{file_id}.*")
            if (
                f.is_file()
                and "%(" not in f.name
                and f.suffix.lower() in ALLOWED_EXTENSIONS
            )
        ]

        if not downloaded_files:
            return {
                "error": "Download completed, but the media file could not be found.",
                "platform": platform
            }

        input_file = downloaded_files[0]

    result_data = process_audio(
        input_file=input_file,
        output_file=output_file,
        start=start,
        duration=duration,
        format=out_format,
        fade_in=fade_in,
        fade_out=fade_out,
    )

    if isinstance(result_data, dict):
        result_data["platform"] = platform

    return result_data


# ============================================================
# FRIENDLY YT-DLP ERRORS
# ============================================================

def friendly_download_error(platform: str, error_text: str) -> str:
    error_lower = (error_text or "").lower()

    if "login required" in error_lower or "sign in" in error_lower or "authentication" in error_lower:
        return f"{platform} requires login or authentication for this media."
    if "private" in error_lower or "members-only" in error_lower:
        return f"This {platform} content is private or restricted."
    if "unsupported url" in error_lower or "no suitable extractor" in error_lower:
        return "This URL is not currently supported."
    if "video unavailable" in error_lower or "content is not available" in error_lower:
        return f"The {platform} media is unavailable or was removed."
    if "age-restricted" in error_lower or "age restricted" in error_lower:
        return f"This {platform} media is age-restricted and cannot be processed."
    if "geo" in error_lower or "not available in your country" in error_lower:
        return f"This {platform} media is region-restricted."
    return f"Could not download audio from {platform}. Please try another link or upload a local file."


# ============================================================
# AUDIO PROCESSING (FFMPEG with M4R + FADE EFFECTS)
# ============================================================

def process_audio(
    input_file: Path,
    output_file: Path,
    start: float,
    duration: float,
    format: str = "mp3",
    fade_in: bool = False,
    fade_out: bool = False,
):
    try:
        start = float(start)
    except (TypeError, ValueError):
        start = 0.0

    if start < 0:
        start = 0.0

    try:
        duration = float(duration)
    except (TypeError, ValueError):
        duration = 30.0

    if duration <= 0:
        duration = 30.0

    # iOS iPhone ringtones (.m4r) must not exceed 40 seconds
    max_duration = 40.0 if format == "m4r" else 60.0
    if duration > max_duration:
        duration = max_duration

    command = [
        "ffmpeg",
        "-y",
        "-ss", str(start),
        "-i", str(input_file),
        "-t", str(duration),
        "-vn",
    ]

    audio_filters = []
    if fade_in:
        fade_len = min(1.5, duration / 2.0)
        audio_filters.append(f"afade=t=in:ss=0:d={fade_len:.2f}")
    if fade_out:
        fade_len = min(1.5, duration / 2.0)
        fade_start = max(0.0, duration - fade_len)
        audio_filters.append(f"afade=t=out:st={fade_start:.2f}:d={fade_len:.2f}")

    if audio_filters:
        command.extend(["-af", ",".join(audio_filters)])

    if format == "m4r":
        command.extend(["-c:a", "aac", "-b:a", "192k", str(output_file)])
    else:
        command.extend(["-acodec", "libmp3lame", "-b:a", "192k", str(output_file)])

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=120
        )
    except subprocess.TimeoutExpired:
        input_file.unlink(missing_ok=True)
        return {"error": "Audio processing timed out."}
    except FileNotFoundError:
        input_file.unlink(missing_ok=True)
        return {
            "error": "FFmpeg was not found. Please ensure FFmpeg is installed on the server."
        }
    except Exception as e:
        input_file.unlink(missing_ok=True)
        return {"error": "Unexpected FFmpeg error.", "details": str(e)}

    # Retain input_file only if it belongs to preview, otherwise unlink
    if "_ringtone" in input_file.name:
        input_file.unlink(missing_ok=True)

    if result.returncode != 0:
        return {
            "error": "Audio processing failed.",
            "details": result.stderr[-1000:]
        }

    if not output_file.exists():
        return {"error": "Ringtone file was not created."}

    return {
        "success": True,
        "filename": output_file.name,
        "format": format
    }


# ============================================================
# RINGTONE DOWNLOAD
# ============================================================

@app.get("/download/{filename}")
async def download(filename: str):
    safe_filename = Path(filename).name
    file_path = OUTPUT_DIR / safe_filename

    if not file_path.exists():
        return {"error": "File not found or expired."}

    ext = file_path.suffix.lower()
    media_type = "audio/x-m4r" if ext == ".m4r" else "audio/mpeg"

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=safe_filename
    )
