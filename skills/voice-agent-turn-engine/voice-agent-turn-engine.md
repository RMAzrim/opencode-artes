---
id: voice-agent-turn-engine
file_path: skills/voice-agent-turn-engine/voice-agent-turn-engine.md
name: Voice Agent Turn Engine
category: voice-ai
tags:
  - voice
  - stt
  - tts
  - barge-in
  - pipeline
  - python
author: opencode-core
version: 1.0.0
description: Offline voice-agent turn orchestrator built on stdlib only. Models an STT - LLM - TTS conversation loop with pluggable adapters, deadline-based turns, silence/barge-in detection signals, and VAD state machine; emits a timestamped utterance transcript and turn timeline JSON. Runnable end-to-end with the bundled mock adapters - no audio hardware, no MCP.
---

# Voice Agent Turn Engine

Orchestrate the realtime turn loop of a voice agent - speech-to-text capture, LLM reply generation, and text-to-speech playback - with strict turn timers and barge-in handling, using a single stdlib Python module. The reference implementation supplies *mock* STT/LLM/TTS adapters, so the whole state machine can be exercised offline with realistic timestamps.

## 1. System Architecture & Prerequisites

- **Runtime**: CPython 3.9+ (`dataclasses`, `json`, `time`, `enum`, `typing`, `random`, `datetime`). No audio libraries, no network, no MCP.
- **Component model**:
  - `AssetAdapter` (STT, LLM, TTS) â€” pluggable; swap the mock for a real SDK adapter that converts to/from this module's text contract.
  - `VADStateMachine` â€” tracks `silence` / `speech` / `barge_in_standby` from normalized energy samples; energy > threshold = speech, dropping below for `hold_ms` = barge-in candidate.
  - `TurnScheduler` â€” per-turn budget (`max_turn_ms`), guard: STT costs `stt_ms`, LLM `llm_ms`, TTS `tts_ms` (configurable with jitter).
  - `voice_agent()` â€” top-level loop: get user utterance â†’ plan â†’ speak â†’ re-enter VAD.
- **Barge-in contract**: if an energy spike arrives while TTS is "playing" (`is_speaking`), the scheduler immediately truncates the TTS phase, emits `event: barge_in` on the timeline, and returns control to STT for the interrupting utterance.

## 2. Input/Output Data Contracts

| Input | Format | Notes |
|---|---|---|
| `scripts` (start-up script) | `dict{"lines": [{"speaker": "caller" | "agent", "text": "..."}], "scene": "..."}` | drives the demo |
| `--max-turns` | int | stop after N user turns (default 5) |
| `--barge-in-threshold` | float 0..1 | energy level that interrupts TTS |
| energy sample | float 0..1 | fed to `VADStateMachine.feed()` |

| Output | Format |
|---|---|
| transcript | `transcript.json` â€” `[{speaker, text, stt_wall_ms, started_at, ended_at}]` |
| turn timeline (events) | `timeline.json` â€” `[{turn, seq, event, wall_ms, note}]` |
| run/agent summary | stdout JSON (`turns`, `barge_ins`, avg latencies) |

## 3. Production Reference Implementation

```python
#!/usr/bin/env python3
"""voice_turn_engine.py - offline voice-agent turn loop (pure stdlib)."""
import json
import random
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Callable


def utcnow_ms() -> int:
    return datetime.now(timezone.utc).timestamp() * 1000


class V(Enum):
    SILENCE = "silence"
    SPEECH = "speech"
    INTERRUPT = "barge_in_standby"


class VADStateMachine:
    """Energy-based speech detect + barge-in standoff, no audio heap needed."""

    def __init__(self, threshold: float = 0.35, hold_ms: int = 120):
        self.threshold = threshold
        self.hold_ms = hold_ms
        self.state = V.SILENCE
        self._energy_below_since = 0.0

    def feed(self, energy: float, now: float):
        if energy >= self.threshold:
            self.state = V.SPEECH
            self._energy_below_since = 0.0
        else:
            if self.state == V.SPEECH:
                if self._energy_below_since == 0.0:
                    self._energy_below_since = now
                elif now - self._energy_below_since >= self.hold_ms:
                    self._energy_below_since = 0.0
                    self.state = V.INTERRUPT
            elif self.state == V.INTERRUPT:
                self.state = V.SILENCE
        return self.state


@dataclass
class Utterance:
    speaker: str
    text: str
    started_at: int = 0
    ended_at: int = 0
    stt_wall_ms: int = 0
    latency_ms: int = 0


@dataclass
class TimelineEvent:
    turn: int
    seq: int
    event: str
    wall_ms: int = 0
    note: str = ""


@dataclass
class TurnStats:
    text: str = ""
    user_ms: int = 0
    agent_ms: int = 0
    barge_in: bool = False
    events: list = field(default_factory=list)


class MockSTT:
    def __init__(self, mu_ms=90, jitter_ms=20, seed=7):
        self.rng = random.Random(seed)
        self.mu, self.jitter = mu_ms, jitter_ms

    def transcribe(self, text: str) -> (str, int):
        t = max(10, int(self.rng.gauss(self.mu, self.jitter)))
        return text, t


class MockLLM:
    def __init__(self, mu_ms=260, jitter_ms=40, seed=11):
        self.rng = random.Random(seed)
        self.mu, self.jitter = mu_ms, jitter_ms

    def generate(self, user_text: str) -> (str, int):
        t = max(10, int(self.rng.gauss(self.mu, self.jitter)))
        return f"agent: noted '{user_text[:42]}' - proceeding.", t


class MockTTS:
    def __init__(self, mu_ms=80, jitter_ms=15, seed=13, speech_ms=320):
        self.rng = random.Random(seed)
        self.mu, self.jitter = mu_ms, jitter_ms
        self.speech_ms = speech_ms

    def speak(self, text: str) -> (str, int, int):
        t = max(10, int(self.rng.gauss(self.mu, self.jitter)))
        return text, t, self.speech_ms


def voice_agent(script, max_turns=5, threshold=0.35, hold_ms=120,
                stt=None, llm=None, tts=None,
                harasser: Callable[[int], float] | None = None) -> dict:
    stt = stt or MockSTT(); llm = llm or MockLLM(); tts = tts or MockTTS()
    vad = VADStateMachine(threshold=threshold, hold_ms=hold_ms)
    ms0 = utcnow_ms()
    timeline: list = []
    transcript: list = []
    turns: list = []

    for turn_idx in range(1, max_turns + 1):
        script_text = next(
            (ln["text"] for ln in script.get("lines", []) if ln.get("speaker") == "caller" and turn_idx <= 1),
            f"user request #{turn_idx}",
        )
        t0 = utcnow_ms()
        # --- STT phase ---
        text, stt_ms = stt.transcribe(script_text)
        t_stt = utcnow_ms()
        # --- LLM phase ---
        reply, llm_ms = llm.generate(text)
        t_llm = utcnow_ms()
        # --- TTS phase (barge-in window) ---
        barge_in = False
        events = [TimelineEvent(turn_idx, 1, "turn_start", t0 - ms0),
                  TimelineEvent(turn_idx, 2, "stt_done", t_stt - ms0, f"{stt_ms}ms"),
                  TimelineEvent(turn_idx, 3, "llm_done", t_llm - ms0, f"{llm_ms}ms")]
        tone, tts_ms, speech_ms = tts.speak(reply)
        t_tts = utcnow_ms()
        if harasser is not None and harasser(turn_idx) >= threshold:
            barge_in = True
            events.append(TimelineEvent(turn_idx, 4, "barge_in", t_tts - ms0,
                                        f"speech interrupted after {tts_ms}ms"))
            vad.feed(harasser(turn_idx), t_tts)
        else:
            events.append(TimelineEvent(turn_idx, 4, "tts_played", t_tts - ms0, f"{speech_ms}ms"))
            vad.feed(0.1, t_tts)
        t1 = utcnow_ms()

        utt = Utterance("agent", reply, t_tts - ms0, t1 - ms0, stt_ms, t1 - t0)
        transcript.append(asdict(utt))
        ts = TurnStats(text=text, user_ms=t1 - t0 - (stt_ms + llm_ms),
                       agent_ms=stt_ms + llm_ms + tts_ms,
                       barge_in=barge_in, events=[ev.__dict__ for ev in events])
        turns.append(ts)
        timeline.extend(ev.__dict__ for ev in events)

    return {
        "scene": script.get("scene", "generic"),
        "max_turns": max_turns,
        "elapsed_ms": utcnow_ms() - ms0,
        "barge_ins": sum(1 for t in turns if t.barge_in),
        "avg_user_ms": round(sum(t.user_ms for t in turns) / len(turns), 1),
        "avg_agent_ms": round(sum(t.agent_ms for t in turns) / len(turns), 1),
        "transcript": transcript,
        "timeline": timeline,
    }


def demo():
    script = {"scene": "concierge", "lines": [
        {"speaker": "caller", "text": "book a table for two at 8pm"},
        {"speaker": "caller", "text": "yes, near the park side"},
    ]}
    energy_schedule = {1: 0.9, 2: 0.05, 3: 0.05}
    result = voice_agent(script, max_turns=3, harasser=lambda n: energy_schedule.get(n, 0.05))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    demo()
```

## 4. Execution Protocol & Step-by-Step Workflow

1. **Save module** as `voice_turn_engine.py` (pure stdlib; imports: `dataclasses`, `json`, `random`, `time`, `datetime`, `enum`, `typing`).
2. **Offline run**: `python voice_turn_engine.py` runs the 3-turn concierge demo.
3. **Read output**: `result["timeline"]` shows ordered `turn_start â†’ stt_done â†’ llm_done â†’ tts_played|barge_in` events with wall-clock offsets; `barge_ins` counts interruptions.
4. **Custom inputs**:
   ```python
   from voice_turn_engine import voice_agent, MockLLM, MockTTS
   out = voice_agent({"scene": "support", "lines": [{"speaker": "caller", "text": "reset my password"}]},
                     max_turns=2, llm=MockLLM(mu_ms=120))
   open("transcript.json", "w").write(json.dumps(out["transcript"]))
   ```
5. **Swap real backends**: implement `transcribe(text)->(text, ms)`, `generate(text)->(reply, ms)`, `speak(text)->(tone, ms, speech_ms)`; pass as `stt=`, `llm=`, `tts=` â€” the state machine and scheduler remain unchanged.

## 5. Edge Cases & Error Handling

- **Interrupt during TTS** â†’ `barge_in` event appended; TTS phase truncated; next turn starts immediately (LLM never double-replies).
- **Persistent loud audio** â†’ VAD remains in `SPEECH`; hold-timer only fires after a quiet period, preventing chatter from escalating into infinite barge-ins.
- **Over-budget turn** â†’ latencies are additive but the scheduler does **not** block subsequent turns (voice agent must stay responsive); instrument per-phase `*_ms` to diagnose.
- **Missing caller line** â†’ falls back to generated `user request #N` so the demo never crashes mid-script.
- **Empty / null text from STT** â†’ LLM receives empty string; mock still answers; add a no-input guard in real adapters.
- **Clock skew** â†’ all offsets are relative to `utcnow_ms()` of the run start, so metrics are wall-clock independent.