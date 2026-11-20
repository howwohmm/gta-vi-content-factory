"""Finds the best moments in a long video.

1. Cheap signals over the whole video: loudness every second + scene cuts.
2. Picks ~3x more candidate windows than needed from the loudest/busiest stretches.
3. Shows each candidate to the AI (frames + transcript if available) for a score and a hook.
4. Keeps the best ones.
Works without any AI too: then it keeps the loudest/busiest moments and leaves the hooks for you to write."""
import os, re, math, uuid
from . import core, ai

def loudness(video, job=None):
    """dB RMS for every second of audio."""
    ff = core.which("ffmpeg") or "ffmpeg"
    r = core.run([ff, "-hide_banner", "-nostats", "-i", video, "-vn", "-af",
                  "aresample=8000,asetnsamples=n=8000,astats=metadata=1:reset=1,"
                  "ametadata=mode=print:key=lavfi.astats.Overall.RMS_level:file=-", "-f", "null", "-"], check=False)
    vals = []
    for line in r.stdout.splitlines():
        if "RMS_level=" in line:
            v = line.split("=", 1)[1].strip()
            vals.append(-90.0 if v in ("-inf", "inf", "nan") else max(-90.0, float(v)))
    return vals

def scene_cuts(video):
    ff = core.which("ffmpeg") or "ffmpeg"
    r = core.run([ff, "-hide_banner", "-nostats", "-i", video, "-an", "-vf",
                  "fps=2,scale=160:-2,select='gt(scene,0.3)',metadata=print:file=-", "-f", "null", "-"], check=False)
    return [float(m.group(1)) for m in re.finditer(r"pts_time:([\d.]+)", r.stdout)]

def transcribe(video):
    """Optional speech-to-text. Uses mlx-whisper on Apple Silicon or faster-whisper if installed; else nothing."""
    try:
        import mlx_whisper  # type: ignore
        res = mlx_whisper.transcribe(video, path_or_hf_repo="mlx-community/whisper-small-mlx")
        return [(s["start"], s["end"], s["text"]) for s in res.get("segments", [])]
    except Exception:
        pass
    try:
        from faster_whisper import WhisperModel  # type: ignore
        model = WhisperModel("small", compute_type="int8")
        segs, _ = model.transcribe(video, vad_filter=True)
        return [(s.start, s.end, s.text) for s in segs]
    except Exception:
        return []

def text_between(segments, a, b):
    return " ".join(t.strip() for s, e, t in segments if e > a and s < b)

def candidates(dur, loud, cuts, length, count):
    """Greedy pick of non-overlapping windows with the most energy."""
    if dur < length + 2:
        return [0.0]
    import statistics
    med = statistics.median(loud) if loud else -40
    spread = (statistics.pstdev(loud) or 1) if loud else 1
    step, scored = 5, []
    for start in range(5, int(dur - length - 2), step):   # skip the first seconds (intros)
        seg = loud[start:start + length] or [med]
        quiet = sum(1 for v in seg if v < -60) / len(seg)          # silence/black/menus
        z = (sum(seg) / len(seg) - med) / spread
        peak = (max(seg) - med) / spread
        n_cuts = sum(1 for c in cuts if start <= c < start + length)
        score = z + 0.5 * peak + 0.15 * min(n_cuts, 8) - 2 * quiet
        scored.append((score, float(start)))
    scored.sort(reverse=True)
    picked = []
    for score, start in scored:
        if all(abs(start - p) >= length + 5 for p in picked):
            picked.append(start)
        if len(picked) >= count:
            break
    return sorted(picked)

def frame_strip(video, start, length, out):
    ff = core.which("ffmpeg") or "ffmpeg"
    font = core.FONT_BOLD.replace(":", r"\:")
    vf = (f"fps=6/{length},scale=480:-2,"
          f"drawtext=fontfile='{font}':text='%{{eif\\:t+{int(start)}\\:d}}s':fontcolor=yellow:fontsize=24:x=8:y=6:box=1:boxcolor=black@0.6,"
          "tile=3x2")
    core.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-ss", str(start), "-t", str(length), "-i", video,
              "-vf", vf, "-frames:v", "1", "-q:v", "5", out])
    with open(out, "rb") as f:
        return f.read()

def find(job, project, s):
    """Fills project['moments'] with the best clips. Returns the list."""
    video, dur, length = project["video"], project["duration"], int(s["reel_seconds"])
    target = max(1, round(dur / 3600 * s["reels_per_hour"]))
    work = os.path.join(os.path.dirname(video), "_analysis"); os.makedirs(work, exist_ok=True)

    job.update(0.03, "Listening to the audio")
    loud = loudness(video)
    job.update(0.15, "Looking for action (scene changes)")
    cuts = scene_cuts(video)
    provider = ai.pick_provider(s)
    segments = []
    if provider != "none":
        job.update(0.25, "Transcribing speech (skipped if no speech model is installed)")
        segments = transcribe(video)

    pool = candidates(dur, loud, cuts, length, target * (3 if provider != "none" else 1))
    core.say("clip", f"{len(pool)} candidate moments, AI: {provider}")
    moments = []
    for i, start in enumerate(pool):
        job.update(0.3 + 0.65 * i / max(1, len(pool)), f"Watching moment {i+1} of {len(pool)}")
        m = {"id": uuid.uuid4().hex[:8], "start": start, "end": start + length, "score": 0, "hook": "",
             "emoji": "", "keywords": [], "why": "", "status": "review", "reel": "", "posted": {}}
        if provider != "none":
            try:
                img = frame_strip(video, start, length, os.path.join(work, f"strip_{int(start)}.jpg"))
                d = ai.describe(img, text_between(segments, start, start + length), length, s, provider)
                shift = max(0.0, min(d["best_start"], length * 0.6))
                m.update(score=d["score"], hook=d["hook"], emoji=d.get("emoji", ""), keywords=d["keywords"],
                         why=d.get("why", ""), start=min(start + shift, dur - length), end=min(start + shift, dur - length) + length)
            except ai.AIError as e:
                core.say("clip", f"AI skipped a moment: {e}", "warn")
                if "key" in str(e).lower() or "401" in str(e):
                    raise
        else:
            m["score"], m["why"] = len(pool) - i, "loud / busy moment"
        moments.append(m)

    if provider != "none":
        moments = [m for m in moments if m["hook"] and m["score"] >= 5] or moments
    moments.sort(key=lambda m: m["score"], reverse=True)
    moments = sorted(moments[:target], key=lambda m: m["start"])
    for m in moments:
        if not m["hook"]: m["status"] = "needs_hook"
    return moments
