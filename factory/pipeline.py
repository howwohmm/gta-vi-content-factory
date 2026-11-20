"""The whole 'long video in, posts out' flow, plus the posting queue it feeds."""
import os, time, uuid
from . import core, ingest, moments, render, covers, jobs

QUEUE_FILE = os.path.join(core.HOME_DIR, "queue.json")

def queue():
    return core.read_json(QUEUE_FILE, [])

def save_queue(q):
    core.write_json(QUEUE_FILE, q)

def hook_line(s, hook, emoji=""):
    return f"{s['header']}, {hook}".strip() + (f" {emoji}" if emoji else "")

def captions(s, hook, emoji="", keywords=(), credit=""):
    vals = {"hook": hook_line(s, hook, emoji), "handle": s.get("handle") or "", "page": s.get("page_name") or "",
            "game": s.get("game", "GTA VI"), "hashtags": s.get("hashtags", ""),
            "keywords": ", ".join(list(keywords) + [f"{s['game'].lower()} gameplay", f"{s['game'].lower()} clips"])}
    out = {}
    for p in ("instagram", "facebook", "threads"):
        t = s.get(f"caption_{p}", "{hook}")
        for k, v in vals.items(): t = t.replace("{" + k + "}", v)
        t = "\n".join(l for l in t.splitlines())
        if credit: t += f"\n\n{credit}"
        out[p] = t.strip()[: 2200 if p != "threads" else 500]
    return out

def process(job, pid):
    """Analyse -> render reels -> cut long parts -> covers -> queue. Safe to re-run."""
    s = core.load_settings()
    p = ingest.load(pid)
    p["status"] = "analysing"; ingest.save(p)

    found = moments.find(job, p, s)
    p["moments"] = found; p["status"] = "rendering"; ingest.save(p)

    reels_dir = os.path.join(ingest.project_dir(pid), "reels")
    os.makedirs(reels_dir, exist_ok=True)
    for i, m in enumerate(found):
        job.update(0.0 + 0.7 * i / max(1, len(found)), f"Rendering reel {i+1} of {len(found)}")
        render_moment(p, m, s, reels_dir)
        ingest.save(p)

    if s.get("make_long") and p["duration"] > s["long_minutes"] * 60 * 0.8:
        job.update(0.75, "Cutting long-form parts")
        parts = render.long_parts(job, p["video"], s["long_minutes"], os.path.join(ingest.project_dir(pid), "long"),
                                  f"{s['game']} Full Gameplay Walkthrough - Part {{n}}")
        bg = covers.background_for(p, s, render.still)
        for part in parts:
            job.update(0.85, f"Making cover for part {part['n']}")
            part["cover"] = covers.make(bg, part["n"], part["file"][:-4] + " cover.jpg", s)
        p["long_parts"] = parts

    p["status"] = "review"; ingest.save(p)
    sync_queue(p)
    core.say("factory", f"'{p['title']}': {sum(1 for m in found if m.get('reel'))} reels ({sum(1 for m in found if not m.get('reel'))} need a hook) and {len(p['long_parts'])} long parts ready to review")
    return pid

def render_moment(p, m, s, reels_dir=None):
    reels_dir = reels_dir or os.path.join(ingest.project_dir(p["id"]), "reels")
    os.makedirs(reels_dir, exist_ok=True)
    if not m["hook"]:
        m["status"] = "needs_hook"; return
    out = os.path.join(reels_dir, f"{int(m['start']):06d} {core.safe_name(m['hook'], 60)}.mp4")
    if m.get("reel") and os.path.exists(m["reel"]) and m["reel"] != out:
        core.move_to_trash(m["reel"])
    render.reel(p["video"], m["start"], s["reel_seconds"], m["hook"], out, s)
    m["reel"] = out
    if m["status"] == "needs_hook": m["status"] = "review"

def sync_queue(p):
    """Mirror a project's reels/parts into the posting queue, keeping anything already posted."""
    s = core.load_settings()
    q = queue()
    by_key = {(it["project"], it["ref"]): it for it in q}
    for m in p["moments"]:
        if not m.get("reel"): continue
        it = by_key.get((p["id"], m["id"]))
        caps = captions(s, m["hook"], m.get("emoji", ""), m.get("keywords", []), s.get("credit_line", ""))
        if it:
            if not any(v.get("status") == "posted" for v in it["posted"].values()):
                it.update(file=m["reel"], hook=m["hook"], captions=caps)
            it["approved"] = m["status"] == "approved"
        else:
            q.append({"id": uuid.uuid4().hex[:10], "project": p["id"], "ref": m["id"], "kind": "reel",
                      "file": m["reel"], "hook": m["hook"], "title": hook_line(s, m["hook"], m.get("emoji", "")),
                      "captions": caps, "cover": "", "approved": m["status"] == "approved",
                      "created": time.time(), "posted": {}})
    for part in p.get("long_parts", []):
        ref = f"long{part['n']}"
        it = by_key.get((p["id"], ref))
        desc = (f"{part['title']}\n\npart {part['n']} of the full {s['game']} playthrough. no commentary, just the game.\n\n"
                f"{('Follow ' + s['page_name'] + ' for the next part!') if s.get('page_name') else ''}\n\n{s.get('hashtags','')}").strip()
        if not it:
            q.append({"id": uuid.uuid4().hex[:10], "project": p["id"], "ref": ref, "kind": "long",
                      "file": part["file"], "hook": part["title"], "title": part["title"], "cover": part.get("cover", ""),
                      "captions": {"facebook": desc, "youtube": desc}, "approved": part.get("approved", False),
                      "created": time.time(), "posted": {}})
        else:
            it["approved"] = part.get("approved", False)
    save_queue(q)

def set_moment(pid, mid, approved=None, hook=None, emoji=None):
    p = ingest.load(pid)
    m = next(x for x in p["moments"] if x["id"] == mid)
    if hook is not None and hook.strip() != m["hook"]:
        m["hook"] = hook.strip().removeprefix("In GTA VI,").strip()
        if emoji is not None: m["emoji"] = emoji
        def rerender(job):
            render_moment(p, m, core.load_settings()); ingest.save(p); sync_queue(p)
        jobs.start("render", f"Re-render: {m['hook'][:40]}", rerender)
    if approved is not None:
        m["status"] = "approved" if approved else "rejected"
    ingest.save(p); sync_queue(p)
    return m

def approve_all(pid, include_long=True):
    p = ingest.load(pid)
    for m in p["moments"]:
        if m["status"] in ("review",) and m.get("reel"): m["status"] = "approved"
    if include_long:
        for part in p.get("long_parts", []): part["approved"] = True
    p["status"] = "approved"
    ingest.save(p); sync_queue(p)
