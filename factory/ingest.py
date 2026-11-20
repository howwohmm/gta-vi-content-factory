"""Getting a long video into a project: from a link (YouTube, Twitch, X...) or a file on the Mac."""
import os, re, time, shutil
from . import core

def project_dir(pid): return os.path.join(core.DIRS["projects"], pid)
def project_file(pid): return os.path.join(project_dir(pid), "project.json")
def load(pid): return core.read_json(project_file(pid), None)
def save(p): core.write_json(project_file(p["id"]), p)

def all_projects():
    out = []
    root = core.DIRS["projects"]
    for name in sorted(os.listdir(root)) if os.path.isdir(root) else []:
        p = load(name)
        if p: out.append(p)
    return sorted(out, key=lambda p: p.get("created", 0), reverse=True)

def new_project(title, source):
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40] or "video"
    pid = f"{time.strftime('%Y%m%d-%H%M%S')}-{slug}"
    os.makedirs(project_dir(pid), exist_ok=True)
    p = {"id": pid, "title": title, "source": source, "created": time.time(), "status": "new",
         "video": "", "duration": 0, "moments": [], "long_parts": []}
    save(p)
    return p

def from_link(job, url):
    """Downloads a stream VOD or video with yt-dlp. Only use videos you own or have permission to use."""
    if not re.match(r"^https?://", url.strip()):
        raise ValueError("That doesn't look like a link.")
    ytdlp = core.which("yt-dlp")
    if not ytdlp:
        raise RuntimeError("yt-dlp isn't installed. Run the installer again (it installs it for you).")
    job.update(0.02, "Reading the link")
    info = core.run([ytdlp, "--no-playlist", "--print", "%(title)s", "--skip-download", "--", url], timeout=120)
    title = (info.stdout.strip().splitlines() or ["Downloaded video"])[0][:120]
    p = new_project(title, url)
    out = os.path.join(project_dir(p["id"]), "source.%(ext)s")
    job.update(0.05, "Downloading (this can take a while for long streams)")
    import subprocess
    env = dict(os.environ, PATH=":".join(core.BREW_PATHS + [os.environ.get("PATH", "")]))
    proc = subprocess.Popen([ytdlp, "--no-playlist", "--newline", "-f", "bv*[height<=1080]+ba/b[height<=1080]/b",
                             "--merge-output-format", "mp4", "-o", out, "--", url],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
    for line in proc.stdout:
        m = re.search(r"\[download\]\s+([\d.]+)%", line)
        if m: job.update(0.05 + 0.9 * float(m.group(1)) / 100, f"Downloading {m.group(1)}%")
    if proc.wait() != 0:
        raise RuntimeError("The download failed. Is the video public, and is the link right?")
    video = next((os.path.join(project_dir(p["id"]), f) for f in os.listdir(project_dir(p["id"])) if f.startswith("source.") and f.endswith(".mp4")), None)
    if not video:
        raise RuntimeError("Downloaded, but couldn't find the video file.")
    return finish(p, video)

def from_file(job, path, move=False):
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    p = new_project(os.path.splitext(os.path.basename(path))[0], path)
    dst = os.path.join(project_dir(p["id"]), "source" + os.path.splitext(path)[1].lower())
    job.update(0.1, "Copying the video into the project")
    (shutil.move if move else shutil.copyfile)(path, dst)
    return finish(p, dst)

def finish(p, video):
    p["video"] = video
    p["duration"] = core.duration(video)
    p["status"] = "downloaded"
    save(p)
    core.say("ingest", f"Added '{p['title']}' ({p['duration']/60:.0f} min)")
    return p["id"]

VIDEO_EXT = (".mp4", ".mov", ".mkv", ".webm", ".m4v")

def scan_inbox():
    """Files dropped into 'Drop videos here' that haven't been picked up yet (and aren't still copying)."""
    out = []
    for f in sorted(os.listdir(core.DIRS["inbox"])):
        path = os.path.join(core.DIRS["inbox"], f)
        if f.lower().endswith(VIDEO_EXT) and os.path.isfile(path):
            s1 = os.path.getsize(path); time.sleep(0.5)
            if os.path.getsize(path) == s1: out.append(path)
    return out
