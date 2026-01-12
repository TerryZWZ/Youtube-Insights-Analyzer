import logging
from urllib.parse import urlparse, parse_qs
from typing import Any, Dict
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
)

# Set up basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_video_id(video_url: str) -> str:
    """
    Extract the video ID from a YouTube URL.
    """
    video_url = str(video_url)
    parsed_url = urlparse(video_url)
    query_params = parse_qs(parsed_url.query)
    video_id = query_params.get("v")

    if video_id:
        return video_id[0]

    raise ValueError("Invalid YouTube URL: Video ID not found.")


def get_transcript(video_url: str) -> str:
    """
    Fetch and return the transcript text for a given YouTube video URL.
    """
    languages = ["en"]
    video_id = extract_video_id(video_url)
    ytt_api = YouTubeTranscriptApi()

    try:
        fetched_transcript = ytt_api.fetch(video_id, languages=languages)
    except (TranscriptsDisabled, NoTranscriptFound):
        transcript_search = ytt_api.list(video_id)

        try:
            generated_transcript = transcript_search.find_generated_transcript(languages)
            fetched_transcript = generated_transcript.fetch()
        except NoTranscriptFound:
            raise ValueError("Transcript not available for this video.")
    except Exception as e:
        raise ValueError("An error occurred while fetching the transcript.") from e

    transcript_text = " ".join(snippet.text for snippet in fetched_transcript)
    return transcript_text


def get_video_metadata(video_url: str) -> Dict[str, Any]:
    """
    Fetch basic YouTube metadata for a given video URL.
    """
    try:
        import yt_dlp  # type: ignore
    except Exception as e:
        logger.warning("yt-dlp unavailable; skipping metadata fetch (%s).", e)
        return {"title": "", "channel": "", "duration_seconds": 0}

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(str(video_url), download=False) or {}

        title = info.get("title") or ""
        channel = (
            info.get("uploader")
            or info.get("channel")
            or info.get("uploader_id")
            or info.get("channel_id")
            or ""
        )
        duration_seconds = int(info.get("duration") or 0)

        # Normalize if the "channel" field ended up being non-string
        if not isinstance(channel, str):
            channel = str(channel)

        return {"title": title, "channel": channel, "duration_seconds": duration_seconds}
    except Exception as e:
        logger.warning("Failed to fetch video metadata; proceeding without it (%s).", e)
        return {"title": "", "channel": "", "duration_seconds": 0}


def get_video_context(video_url: str) -> Dict[str, Any]:
    """
    Fetch transcript plus basic metadata for a given YouTube video URL.
    """
    metadata = get_video_metadata(video_url)
    transcript = get_transcript(video_url)
    return {**metadata, "transcript": transcript}
