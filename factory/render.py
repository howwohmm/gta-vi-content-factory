"""Turns moments into finished vertical reels and the long video into parts."""
import os, re, textwrap
from . import core

def _esc(t):
    return (t.replace("\\", "\\\\").replace("'", "’").replace('"', "”").replace(":", "\\:")
             .replace("%", "\\%").replace(",", "\\,"))

def reel_filter(hook, header, credit=""):
    """1080x1920: video in the middle, '<header>' + hook above it, inside the safe zone."""
    font = core.FONT_BOLD.replace(":", r"\:")
    lines, fs, lh = textwrap.wrap(hook, 27), 54, 68
    if len(lines) > 3: lines, fs, lh = textwrap.wrap(hook, 31), 48, 60
    if len(lines) > 4: raise ValueError("Hook is too long for the screen. Shorten it to ~100 characters.")
    head, gap = 72, 26
    top = 626 - (head + gap + len(lines) * lh)
    parts = ["scale=1080:-2", "pad=1080:1920:0:(oh-ih)/2:black"]
    if header:
        parts.append(f"drawtext=fontfile='{font}':text='{_esc(header)}':fontcolor=white:fontsize=58:x=(w-text_w)/2:y={top}")
    for k, line in enumerate(lines):
        parts.append(f"drawtext=fontfile='{font}':text='{_esc(line)}':fontcolor=white:fontsize={fs}:x=(w-text_w)/2:y={top+head+gap+k*lh}")
    if credit:
        parts.append(f"drawtext=fontfile='{font}':text='{_esc(credit)}':fontcolor=white@0.8:fontsize=30:x=(w-text_w)/2:y=1330")
    return ",".join(parts)

def reel(video, start, length, hook, out, s):
    ff = core.which("ffmpeg") or "ffmpeg"
    tmp = out + ".part.mp4"
    core.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-ss", str(start), "-t", str(length), "-i", video,
              "-vf", reel_filter(hook, s["header"], s.get("credit_line", "")), "-r", "30",
              "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
              "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-movflags", "+faststart", tmp], timeout=900)
    os.replace(tmp, out)
    return out

def long_parts(job, video, minutes, outdir, title_fmt):
    """Cuts the full video into ~N-minute parts (fast: no re-encode, cuts on keyframes)."""
    ff = core.which("ffmpeg") or "ffmpeg"
    os.makedirs(outdir, exist_ok=True)
    pattern = os.path.join(outdir, "part_%03d.mp4")
    job.update(None, f"Cutting the full video into {minutes}-minute parts")
    core.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-i", video, "-c", "copy", "-map", "0:v:0", "-map", "0:a:0?",
              "-f", "segment", "-segment_time", str(minutes * 60), "-reset_timestamps", "1", pattern], timeout=3600)
    parts = []
    files = sorted(f for f in os.listdir(outdir) if re.match(r"part_\d{3}\.mp4$", f))
    for i, f in enumerate(files, 1):
        p = os.path.join(outdir, f)
        d = core.duration(p)
        if d < minutes * 60 * 0.25 and parts:     # tiny tail: not worth its own video
            core.move_to_trash(p); continue
        final = os.path.join(outdir, core.safe_name(title_fmt.format(n=i)) + ".mp4")
        os.replace(p, final)
        parts.append({"n": i, "file": final, "duration": d, "title": title_fmt.format(n=i), "posted": {}, "cover": ""})
    return parts

def still(video, at, out):
    """A frame for cover backgrounds (scaled to 1280 wide)."""
    ff = core.which("ffmpeg") or "ffmpeg"
    core.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-ss", str(at), "-i", video, "-frames:v", "1",
              "-vf", "scale=1280:-2", "-q:v", "2", out])
    return out
