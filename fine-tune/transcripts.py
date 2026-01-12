import argparse, json
from pathlib import Path
from youtube_transcript_api import YouTubeTranscriptApi
import yt_dlp

def fetch_metadata(video_id: str) -> dict:
    url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {"quiet": True, "skip_download": True}

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    return {
        "video_id": video_id,
        "title": info.get("title", ""),
        "channel": info.get("uploader", ""),
        "duration_seconds": int(info.get("duration") or 0),
        "url": url,
    }

def fetch_transcript(video_id: str) -> list[dict]:
    segments = YouTubeTranscriptApi.get_transcript(video_id)

    return [
        {
            "start": float(s.get("start", 0.0)),
            "duration": float(s.get("duration", 0.0)),
            "text": (s.get("text") or "").replace("\n", " ").strip(),
        }
        for s in segments
        if (s.get("text") or "").strip()
    ]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input_csv", required=True)
    ap.add_argument("--out_jsonl", required=True)
    args = ap.parse_args()

    out_path = Path(args.out_jsonl)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(args.input_csv, "r", encoding="utf-8") as f:
        video_ids = [ln.strip() for ln in f.read().splitlines()[1:] if ln.strip() and not ln.startswith("#")]

    with open(out_path, "w", encoding="utf-8") as w:
        for vid in video_ids:
            meta = fetch_metadata(vid)
            transcript = fetch_transcript(vid)
            row = {**meta, "transcript_segments": transcript}
            w.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Wrote {len(video_ids)} rows to {out_path}")

if __name__ == "__main__":
    main()
