"""Paths, settings, logging and small helpers shared by every part of the factory."""
import os, json, time, shutil, subprocess, threading, datetime, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
FONT_BOLD = os.path.join(ASSETS, "fonts", "Poppins-Bold.ttf")
FONT_HEAVY = os.path.join(ASSETS, "fonts", "Anton-Regular.ttf")

# Everything the user owns lives in one folder they can open in Finder.
HOME_DIR = os.environ.get("GVCF_HOME") or os.path.join(os.path.expanduser("~"), "GTA VI Content Factory")
DIRS = {
    "inbox":    os.path.join(HOME_DIR, "Drop videos here"),   # anything dropped here gets picked up
    "projects": os.path.join(HOME_DIR, "Projects"),           # one folder per source video
    "queue":    os.path.join(HOME_DIR, "Ready to post"),      # rendered reels/long videos waiting to post
    "youtube":  os.path.join(HOME_DIR, "YouTube uploads"),    # Day folders to drag into YouTube Studio
    "covers":   os.path.join(HOME_DIR, "Cover backgrounds"),  # your own art for thumbnails
    "logs":     os.path.join(HOME_DIR, "logs"),
    "keys":     os.path.join(HOME_DIR, ".keys"),
    "trash":    os.path.join(HOME_DIR, "_to_delete"),
}
SETTINGS_FILE = os.path.join(HOME_DIR, "settings.json")

DEFAULTS = {
    "setup_done": False,
    "page_name": "",                 # e.g. "Page for GTA VI"
    "handle": "",                    # e.g. "pageforgtavi" (Instagram/Threads handle, no @)
    "game": "GTA VI",                # header on every reel: "In GTA VI"
    "header": "In GTA VI",
    # AI
    "ai_provider": "auto",           # auto | claude | openai | ollama | none
    "claude_model": "claude-sonnet-4-5",
    "openai_model": "gpt-4.1-mini",
    "ollama_model": "qwen2.5vl:7b",
    # clipping
    "reel_seconds": 25,              # Instagram API rejects long reels on some accounts; 25s is safe
    "reels_per_hour": 12,            # how many reels to aim for per hour of source video
    "long_minutes": 25,              # length of long-form parts
    "make_long": True,
    "credit_line": "",               # e.g. "gameplay: @someone" if you clip someone else's stream (with permission)
    # captions ({hook} {handle} {page} {keywords} {hashtags} are filled in)
    "caption_instagram": "follow @{handle} for more {game}\n\n{hook}\n\n{keywords}\n\n{hashtags}",
    "caption_facebook": "{hook}\n\nFollow {page} for more {game} videos!\n\n{hashtags}",
    "caption_threads": "{hook}",
    "hashtags": "#gta6 #gtavi #gta6gameplay #grandtheftauto6 #vicecity #gta6clips",
    # posting
    "post_every_min": {"instagram": 30, "facebook": 60, "threads": 45},
    "post_hours": [0, 24],           # local hours when posting is allowed, [0, 24] = any time
    "alternate_long": True,          # reel, long part, reel, long part... where a platform supports long video
    "platforms_on": {"instagram": True, "facebook": True, "threads": True},
    "posting_on": False,             # remembered so posting resumes after a restart
    # covers
    "cover_style": "bold-left",
    "cover_background": "",          # file in "Cover backgrounds"; empty = a frame from the video
    # youtube
    "youtube_per_day": 15,
}

_lock = threading.Lock()

def ensure_dirs():
    for d in DIRS.values():
        os.makedirs(d, exist_ok=True)

def load_settings():
    ensure_dirs()
    s = dict(DEFAULTS)
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, encoding="utf-8") as f:
                s.update(json.load(f))
        except Exception:
            pass
    return s

def save_settings(changes):
    with _lock:
        s = load_settings()
        s.update(changes)
        tmp = SETTINGS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(s, f, indent=2, ensure_ascii=False)
        os.replace(tmp, SETTINGS_FILE)
        return s

# ---------- secrets (kept out of settings.json, chmod 600) ----------
def key_path(name): return os.path.join(DIRS["keys"], name)

def get_key(name):
    p = key_path(name)
    try:
        return open(p, encoding="utf-8").read().strip()
    except OSError:
        return ""

def set_key(name, value):
    ensure_dirs()
    p = key_path(name)
    with open(p, "w", encoding="utf-8") as f:
        f.write(value.strip() + "\n")
    os.chmod(p, 0o600)

def del_key(name):
    p = key_path(name)
    if os.path.exists(p):
        os.replace(p, os.path.join(DIRS["trash"], f"{name}.{int(time.time())}"))

# ---------- log + live feed for the web app ----------
FEED = collections.deque(maxlen=400)

def now(): return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def say(tag, msg, level="info"):
    line = {"t": now(), "tag": tag, "msg": str(msg), "level": level}
    FEED.append(line)
    try:
        with open(os.path.join(DIRS["logs"], "factory.log"), "a", encoding="utf-8") as f:
            f.write(f"[{line['t']}] [{tag}] {msg}\n")
    except OSError:
        pass
    print(f"[{line['t']}] [{tag}] {msg}", flush=True)

# ---------- json files ----------
def read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)

# ---------- external tools ----------
BREW_PATHS = ["/opt/homebrew/bin", "/usr/local/bin"]

def which(name):
    for d in BREW_PATHS:
        p = os.path.join(d, name)
        if os.access(p, os.X_OK):
            return p
    return shutil.which(name)

def run(cmd, timeout=None, check=True):
    env = dict(os.environ, PATH=":".join(BREW_PATHS + [os.environ.get("PATH", "")]))
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env, stdin=subprocess.DEVNULL)
    if check and r.returncode != 0:
        raise RuntimeError(f"{os.path.basename(cmd[0])} failed: {(r.stderr or r.stdout).strip()[-600:]}")
    return r

def duration(path):
    r = run([which("ffprobe") or "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path])
    return float(r.stdout.strip() or 0)

def safe_name(text, limit=90):
    bad = '<>:"/\\|?*\n\r\t'
    t = "".join("-" if c in bad else c for c in text).strip(" .-")
    return t[:limit].rstrip(" .-") or "untitled"

def move_to_trash(path):
    """We never delete the user's files; things we replace go to _to_delete so they can bin them."""
    if os.path.exists(path):
        dst = os.path.join(DIRS["trash"], f"{int(time.time())}-{os.path.basename(path)}")
        shutil.move(path, dst)
