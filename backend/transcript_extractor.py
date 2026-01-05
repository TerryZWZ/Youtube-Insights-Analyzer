import logging
from urllib.parse import urlparse, parse_qs
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
