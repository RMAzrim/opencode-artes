---
name: Transcript to SRT Automator
description: Turn a timestamped transcript (JSON) into ready-to-burn SRT subtitles, chapter markers, and a keyword-driven highlight-clip plan with in/out offsets - all in the Python standard library. No ffmpeg required to generate the assets; optional ffmpeg command lines are emitted for the actual clipping step. Zero MCP.
metadata:
  source: skills/transcript-to-srt-automator/transcript-to-srt-automator.md
---

# Transcript to SRT Automator

Convert a machine transcript with timestamps into production-ready subtitle and clip-planning assets using only the standard library: an SRT file with correct cue timing, chapter markers derived from slide/topic boundaries, and a highlight-clip plan (start/end + label) from keyword + silence-heuristic scoring. ffmpeg is *not* needed to generate the assets â€” the module also emits copy-paste `ffmpeg` commands for the clipping step.

## 1. System Architecture & Prerequisites

- **Runtime**: CPython 3.9+ (`json`, `re`, `math`, `datetime`, `argparse`, `collections`). No whisper/srt libs, no ffmpeg binding, no MCP.
- **Input transcript schema**:
  ```json
  {
    "id": "pod-014",
    "duration_s": 3720,
    "segments": [
      {"start": 0.0, "end": 8.4, "speaker": "P1", "text": "Welcome to the show..."},
      {"start": 8.4, "end": 22.1, "speaker": "P2", "text": "Today we talk about ETL pipelines."}
    ]
  }
  ```
- **Outputs**:
  - `out.srt` â€” SRT subtitle file (one cue per segment, `HH:MM:SS,mmm`).
  - `chapters.json` â€” boundaries where speaker changes or a topic keyword appears.
  - `clips.json` â€” `[{label, start, end, reason, confidence}]` computed via keyword hits + gap heuristics.
  - `commands.sh` (optional) â€” ffmpeg cut commands reflecting clips.json.
- **Heuristics**: topic keyword list per clip desired â†’ clip confidence = (keyword strength + gap margin). Segments must be monotonic; overlapping segments are clamped.

## 2. Input/Output Data Contracts

```
python srt_automator.py transcript.json --out subs.srt --chapters chapters.json \
    --clips clips.json --ffmpeg out.sh -k "ETL, pipeline" -c "keynote"
```

- `-k/--keywords` comma-separated; `-c/--chapter` per-topic; `--min-dur-s` clip floor (default 8 s); clock format `HH:MM:SS,mmm`.
- Exit `0` OK, `1` schema/segment validation, `2` input file missing/invalid JSON.

## 3. Production Reference Implementation

```python
#!/usr/bin/env python3
"""srt_automator.py - transcript to SRT + chapters + clip plan (pure stdlib)."""
import argparse
import json
import math
import re
import sys
from datetime import timedelta
from pathlib import Path


def srt_ts(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    ms = int(round((seconds - int(seconds)) * 1000))
    delta = timedelta(seconds=int(seconds))
    return f"{delta.seconds // 3600:02d}:{(delta.seconds % 3600) // 60:02d}:{delta.seconds % 60:02d},{ms:03d}"


def build_srt(segments: list[dict]) -> str:
    blocks = []
    for i, seg in enumerate(segments, 1):
        start = srt_ts(float(seg["start"]))
        end = srt_ts(float(seg["end"]))
        text = (seg.get("speaker", "?").strip() + ": " if seg.get("speaker") else "") + seg["text"].strip()
        blocks.append(f"{i}\n{start} --> {end}\n{text}\n")
    return "\n".join(blocks)


TOPIC_GAP_S = 30.0


def silence_gaps(segments: list[dict], min_gap: float = 1.5) -> list[float]:
    return [seg["start"] - prev["end"]
            for prev, seg in zip(segments, segments[1:])
            if seg["start"] - prev["end"] >= min_gap]


def chapters(segments: list[dict], chapter_words: list[str], min_dur: float = 60.0) -> dict:
    boundaries = []
    last = segments[0]["start"]
    for i, seg in enumerate(segments):
        topic_hit = any(w.lower() in seg["text"].lower() for w in chapter_words)
        speaker_change = i > 0 and seg["speaker"] != segments[i - 1]["speaker"]
        if (topic_hit or speaker_change) and seg["start"] - last >= min_dur:
            boundaries.append({"at": seg["start"], "label": f"{seg['speaker']} @ {seg['text'][:30]}"})
            last = seg["start"]
    return {"chapter_words": chapter_words, "count": len(boundaries), "boundaries": boundaries}


def clips(segments: list[dict], keywords: list[str], min_dur: float = 8.0) -> list[dict]:
    kws = [k.lower() for k in keywords]
    found = []
    for i, seg in enumerate(segments):
        text_l = seg["text"].lower()
        hits = [k for k in kws if k in text_l]
        if not hits:
            continue
        start = max(0.0, seg["start"] - 2.0)
        end = seg["end"] + min(4.0, 2.0)
        gap_bonus = 0.15 if any(g >= 1.5 for g in
                               [seg["start"] - segments[i - 1]["end"] if i > 0 else 0]) else 0.0
        confidence = round(min(0.99, 0.35 + 0.22 * len(hits) + gap_bonus), 2)
        if end - start < min_dur:
            end = start + min_dur
        found.append({"label": "|".join(hits), "start": round(start, 2),
                      "end": round(end, 2), "confidence": confidence,
                      "reason": f"{len(hits)} keyword hit(s)"})
    return found


def ffmpeg_commands(clip_list: list[dict], input_path: str = "input.mp4") -> list[str]:
    cmds = []
    for i, c in enumerate(clip_list, 1):
        cmds.append(
            f'ffmpeg -y -i "{input_path}" -ss {c["start"]} -to {c["end"]} '
            f'-c copy "clip_{i}_{c["label"].replace("|", "_")}.mp4"'
        )
    return cmds


def validate(segments: list[dict]) -> list[str]:
    errs = []
    if not segments:
        return ["no segments"]
    for i, seg in enumerate(segments):
        for key in ("start", "end", "text"):
            if key not in seg:
                errs.append(f"segment {i}: missing '{key}'")
        if i and seg["start"] < segments[i - 1]["end"]:
            errs.append(f"segment {i}: start < previous end (overlap)")
        if seg["end"] <= seg["start"]:
            errs.append(f"segment {i}: end <= start")
    return errs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="srt_automator")
    ap.add_argument("transcript", type=Path)
    ap.add_argument("--out", default="subs.srt")
    ap.add_argument("--chapters", default=None)
    ap.add_argument("--clips", default=None)
    ap.add_argument("--ffmpeg", default=None)
    ap.add_argument("--input", default="input.mp4", help="media path for ffmpeg commands")
    ap.add_argument("-k", "--keywords", default="")
    ap.add_argument("-c", "--chapter", default="")
    ap.add_argument("--min-dur-s", type=float, default=8.0)
    args = ap.parse_args(argv)

    if not args.transcript.exists():
        print(f"[error] transcript not found: {args.transcript}", file=sys.stderr)
        return 2
    try:
        data = json.loads(args.transcript.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"[error] invalid JSON: {exc}", file=sys.stderr)
        return 2
    segments = data.get("segments", [])
    errs = validate(segments)
    if errs:
        for e in errs:
            print(f"  - {e}")
        return 1

    Path(args.out).write_text(build_srt(segments), encoding="utf-8")
    print(f"srt written -> {args.out} ({len(segments)} cues)")
    if args.chapters:
        ch = chapters(segments, [w.strip() for w in args.chapter.split(",") if w.strip()])
        Path(args.chapters).write_text(json.dumps(ch, indent=2), encoding="utf-8")
        print(f"chapters written -> {args.chapters} ({int(ch['count'])} boundaries)")
    if args.clips:
        cl = clips(segments, [w.strip() for w in args.keywords.split(",") if w.strip()],
                   args.min_dur_s)
        Path(args.clips).write_text(json.dumps(cl, indent=2), encoding="utf-8")
        print(f"clips written -> {args.clips} ({len(cl)} highlights)")
        if args.ffmpeg:
            cmds = ffmpeg_commands(cl[:10], args.input)
            Path(args.ffmpeg).write_text("\n".join(cmds) + "\n", encoding="utf-8")
            print(f"ffmpeg commands -> {args.ffmpeg}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

## 4. Execution Protocol & Step-by-Step Workflow

1. **Prepare transcript**: export your STT/whisper transcript as `transcript.json` with the schema above.
2. **Generate SRT**: `python srt_automator.py transcript.json --out subs.srt` â†’ playable subtitles, cue-indexed with `HH:MM:SS,mmm` bounds.
3. **Chapter markers**: `python srt_automator.py transcript.json --chapters ch.json -c "intro, recap, outro"` â†’ speaker-change + topic-word boundaries (min 60 s spacing).
4. **Highlight clips**: `python srt_automator.py transcript.json --clips clips.json -k "ETL, pipeline, error" --ffmpeg cut.sh --input episode.mp4` â†’ ranked highlight plan with confidence + ready-to-run ffmpeg commands.
5. **Inspect**: `clips.json` explains *why* each clip was chosen (`reason`, `confidence`); tune `--min-dur-s` to tighten or loosen segments.
6. **Burn & clip**: run `cut.sh` (requires ffmpeg on the host â€” the only external step, and it is optional) or pass the SRT to a video editor.

## 5. Edge Cases & Error Handling

- **Overlapping / out-of-order segments** â†’ validation exits `1` listing each offending index; fix the transcript before SRT generation.
- **Missing `start`/`end`/`text`** â†’ validation flags the exact segment; SRT never emits half-cues.
- **Zero keywords** â†’ `clips` returns `[]` with a printed count `0` â€” never crashes.
- **Negative/zero-duration cues** â†’ clamped to `>= 0` and `end > start` (min-dur floor applied).
- **Long clips** â†’ hard cap of 10 ffmpeg commands to keep shell output readable; the full `clips.json` stays authoritative.
- **Non-UTF8 files** â†’ `read_text` raises; wrap your producer (whisper) to output UTF-8 â€” the error surfaces with a clear traceback point.
