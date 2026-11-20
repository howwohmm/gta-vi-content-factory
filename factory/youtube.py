"""YouTube: the official upload API locks videos to private unless your app passes Google's audit,
so the factory prepares 'Day' folders you drag into YouTube Studio (file name = title).
Claude (with the youtube-studio-scheduler skill) or you then set details and schedule them."""
import os, re, csv, time, shutil
from . import core, pipeline

LOG = os.path.join(core.DIRS["logs"], "youtube.csv")

def placed():
    if not os.path.exists(LOG): return set()
    with open(LOG, newline="", encoding="utf-8") as f:
        return {r["item"] for r in csv.DictReader(f)}

def fit_title(t, tail=" #Shorts", limit=100):
    t = re.sub(r"\s+", " ", t.replace(":", " -").replace("/", "-").replace("\\", "-").replace('"', "'")).strip()
    if len(t) + len(tail) <= limit: return t + tail
    return t[:limit - len(tail) - 1].rsplit(" ", 1)[0].rstrip(" ,.-") + "…" + tail

def build_days(days=7):
    """Fill up to `days` Day folders ahead: reels as Shorts, alternating with long parts. Never repeats a video."""
    s = core.load_settings()
    per_day = int(s.get("youtube_per_day", 15))
    done = placed()
    todo = [it for it in pipeline.queue() if it["approved"] and it["id"] not in done]
    reels = [it for it in todo if it["kind"] == "reel"]
    longs = [it for it in todo if it["kind"] == "long"]
    root = core.DIRS["youtube"]
    existing = sorted(d for d in os.listdir(root) if re.match(r"Day \d+$", d))
    full = [d for d in existing if os.listdir(os.path.join(root, d))]
    nxt = (max(int(d.split()[1]) for d in existing) + 1) if existing else 1
    made = []
    new_log = not os.path.exists(LOG)
    with open(LOG, "a", newline="", encoding="utf-8") as lf:
        w = csv.writer(lf)
        if new_log: w.writerow(["time", "day", "item", "kind", "title"])
        for _ in range(max(0, days - len(full))):
            batch = []
            day_longs = 0
            while len(batch) < per_day and (reels or longs):
                if reels: batch.append(reels.pop(0))
                if longs and len(batch) < per_day and day_longs < 2:     # max 2 long videos a day
                    batch.append(longs.pop(0)); day_longs += 1
            if not batch: break
            d = os.path.join(root, f"Day {nxt:02d}"); os.makedirs(d, exist_ok=True)
            notes = []
            for it in batch:
                title = fit_title(it["title"]) if it["kind"] == "reel" else fit_title(it["title"], tail="")
                shutil.copyfile(it["file"], os.path.join(d, core.safe_name(title, 120) + ".mp4"))
                if it["kind"] == "long" and it.get("cover"):
                    shutil.copyfile(it["cover"], os.path.join(d, core.safe_name(title, 120) + " - thumbnail.jpg"))
                notes.append(f"{title}\n{it['captions'].get('youtube') or it['captions'].get('facebook','')}\n" + "-" * 40)
                w.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), f"Day {nxt:02d}", it["id"], it["kind"], title])
            with open(os.path.join(d, "_titles and descriptions.txt"), "w", encoding="utf-8") as f:
                f.write("\n".join(notes))
            made.append(f"Day {nxt:02d}"); nxt += 1
    core.say("YT", f"made {len(made)} Day folder(s): {', '.join(made) or 'nothing new to add'}")
    return made
