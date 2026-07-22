from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


DEEPGRAM_LISTEN_URL = "https://api.deepgram.com/v1/listen"


def transcribe_audio_file(path: Path, content_type: str | None = None) -> str:
    api_key = os.getenv("DEEPGRAM_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("DEEPGRAM_API_KEY is not configured.")
    params = urllib.parse.urlencode(
        {
            "model": "nova-2",
            "diarize": "true",
            "punctuate": "true",
            "utterances": "true",
            "smart_format": "true",
        }
    )
    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": content_type or _content_type_for(path),
    }
    request = urllib.request.Request(
        f"{DEEPGRAM_LISTEN_URL}?{params}",
        data=path.read_bytes(),
        method="POST",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read(600).decode("utf-8", errors="replace")
        raise RuntimeError(f"Deepgram API returned status={exc.code} response={detail!r}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Deepgram API request failed: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Deepgram API returned a non-JSON response.") from exc
    transcript = speaker_tagged_transcript(payload)
    if not transcript.strip():
        raise RuntimeError("Deepgram returned an empty transcript.")
    return transcript


def speaker_tagged_transcript(payload: dict[str, Any]) -> str:
    utterances = payload.get("results", {}).get("utterances", [])
    if isinstance(utterances, list) and utterances:
        lines = []
        for utterance in utterances:
            if not isinstance(utterance, dict):
                continue
            transcript = str(utterance.get("transcript") or "").strip()
            if transcript:
                lines.append(f"Speaker {utterance.get('speaker', 0)}: {transcript}")
        if lines:
            return "\n".join(lines)

    alternatives = payload.get("results", {}).get("channels", [{}])[0].get("alternatives", [{}])
    words = alternatives[0].get("words", []) if alternatives else []
    if isinstance(words, list) and words:
        lines: list[str] = []
        current_speaker: Any = None
        current_words: list[str] = []
        for word in words:
            if not isinstance(word, dict):
                continue
            speaker = word.get("speaker", 0)
            token = str(word.get("punctuated_word") or word.get("word") or "").strip()
            if not token:
                continue
            if current_speaker is not None and speaker != current_speaker and current_words:
                lines.append(f"Speaker {current_speaker}: {' '.join(current_words)}")
                current_words = []
            current_speaker = speaker
            current_words.append(token)
        if current_words:
            lines.append(f"Speaker {current_speaker}: {' '.join(current_words)}")
        if lines:
            return "\n".join(lines)

    transcript = alternatives[0].get("transcript", "") if alternatives else ""
    return str(transcript).strip()


def _content_type_for(path: Path) -> str:
    extension = path.suffix.lower()
    if extension == ".mp3":
        return "audio/mpeg"
    if extension == ".wav":
        return "audio/wav"
    if extension == ".m4a":
        return "audio/mp4"
    if extension == ".ogg":
        return "audio/ogg"
    return "application/octet-stream"
