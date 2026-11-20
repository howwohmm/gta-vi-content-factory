"""Posts approved videos from the queue to Instagram, Facebook and Threads with the official APIs.

Safety rules (learned the hard way):
- before every post we check the account for a post with the same first line, so nothing goes up twice
- only upload problems are retried (they happen before anything is published); anything else is skipped
- three failures in a row stops that platform until you press Start again
"""
import os, re, sys, json, time, shutil, socket, threading, subprocess, urllib.parse, urllib.request, urllib.error, datetime
from . import core, pipeline

API = "v23.0"
G_FB, G_IG, G_TH = f"https://graph.facebook.com/{API}", f"https://graph.instagram.com/{API}", "https://graph.threads.net/v1.0"
STATUS = {}                 # platform -> {"state","until","account","kind"} for the web app
_qlock = threading.Lock()
_stop = threading.Event()

class AuthError(RuntimeError): pass

def _req(method, url, params=None, data=None, timeout=120):
    if params: url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    r = urllib.request.Request(url, data=data, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        if '"code":190' in body.replace(" ", ""): raise AuthError(body)
        raise RuntimeError(f"HTTP {e.code} from {url.split('?')[0]}: {body[:600]}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"network problem: {e.reason}")

def req(method, url, params=None, data=None, timeout=120, tag="--"):
    for attempt in range(8):
        try: return _req(method, url, params, data, timeout)
        except AuthError: raise
        except RuntimeError as e:
            m = str(e).replace(" ", "")
            if "networkproblem" in m and attempt < 7:
                core.say(tag, "no internet right now, trying again in 2 min", "warn"); _nap(tag, 120, "NO INTERNET"); continue
            if any(x in m for x in ('"code":4,', '"code":17,', '"code":32,', '"code":613,', "requestlimit")) and attempt < 7:
                core.say(tag, "Meta says too many requests, waiting 15 min", "warn"); _nap(tag, 900, "RATE LIMITED"); continue
            raise

def form(d): return urllib.parse.urlencode(d).encode()

def _state(tag, text, secs=None, kind="wait", **extra):
    STATUS.setdefault(tag, {}).update(state=text, until=(time.time() + secs) if secs else None, kind=kind, **extra)

def _nap(tag, secs, text):
    _state(tag, text, secs)
    _stop.wait(secs)

def push_file(url, token, path):
    size = os.path.getsize(path)
    r = subprocess.run(["curl", "-sS", "-X", "POST", url, "-H", f"Authorization: OAuth {token}", "-H", "offset: 0",
                        "-H", f"file_size: {size}", "--data-binary", f"@{path}", "--max-time", "900"],
                       capture_output=True, text=True)
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    if r.returncode != 0 or '"success":true' not in out.replace(" ", ""):
        raise RuntimeError(f"upload rejected: {out[:300]}")

def first_line(caption):
    return next((l.strip() for l in caption.splitlines() if l.strip() and not l.lower().startswith("follow ")), caption[:80])

# ---------------- token helpers (make keys last, so users rarely touch them) ----------------
def fb_long_lived(short_token):
    """With the app id + secret saved, swap a 1-hour token for a 60-day one."""
    app_id, secret = core.get_key("meta_app_id"), core.get_key("meta_app_secret")
    if not (app_id and secret): return short_token
    r = _req("GET", f"{G_FB}/oauth/access_token", {"grant_type": "fb_exchange_token", "client_id": app_id,
                                                  "client_secret": secret, "fb_exchange_token": short_token})
    return r.get("access_token", short_token)

def threads_long_lived(token):
    secret = core.get_key("threads_app_secret") or core.get_key("meta_app_secret")
    if not secret:
        return token
    try:
        r = _req("GET", "https://graph.threads.net/access_token", {"grant_type": "th_exchange_token", "client_secret": secret, "access_token": token})
        core.set_key("threads_token_expires", str(int(time.time()) + int(r.get("expires_in", 5184000))))
        return r.get("access_token", token)
    except RuntimeError:
        return token          # already long-lived, or the secret is for another app

def threads_refresh():
    """Long-lived Threads tokens can be refreshed (needs to be >24h old). Run daily; extends to another 60 days."""
    t = core.get_key("threads_token")
    if not t: return
    exp = int(core.get_key("threads_token_expires") or 0)
    if exp and exp - time.time() > 20 * 86400: return
    try:
        r = _req("GET", "https://graph.threads.net/refresh_access_token", {"grant_type": "th_refresh_token", "access_token": t})
        core.set_key("threads_token", r["access_token"])
        core.set_key("threads_token_expires", str(int(time.time()) + int(r.get("expires_in", 5184000))))
        core.say("TH", "Threads key refreshed for another 60 days")
    except Exception as e:
        core.say("TH", f"couldn't refresh the Threads key: {str(e)[:160]}", "warn")

# ---------------- clients ----------------
class Instagram:
    name, tag, kinds = "instagram", "IG", ("reel",)
    def __init__(self):
        self.t = core.get_key("instagram_token")
        if not self.t: raise RuntimeError("not connected")
        if self.t.startswith("IG"):
            self.g = G_IG
            me = req("GET", f"{self.g}/me", {"fields": "user_id,username", "access_token": self.t})
            self.id, self.username = me["user_id"], me["username"]
        else:
            self.g = G_FB
            self.id = core.get_key("instagram_user_id")
            if not self.id:
                for pg in req("GET", f"{self.g}/me/accounts", {"fields": "instagram_business_account", "access_token": self.t}).get("data", []):
                    if pg.get("instagram_business_account"): self.id = pg["instagram_business_account"]["id"]; break
            if not self.id: raise RuntimeError("couldn't find the Instagram account linked to this key")
            core.set_key("instagram_user_id", self.id)
            self.username = req("GET", f"{self.g}/{self.id}", {"fields": "username", "access_token": self.t})["username"]
        self.account = f"@{self.username}"

    def room_today(self):
        try:
            r = req("GET", f"{self.g}/{self.id}/content_publishing_limit", {"fields": "quota_usage,config", "access_token": self.t}, tag=self.tag)
            d = (r.get("data") or [{}])[0]
            return d.get("quota_usage", 0) < (d.get("config", {}).get("quota_total") or 50)
        except AuthError: raise
        except RuntimeError: return True

    def find_live(self, line):
        r = req("GET", f"{self.g}/{self.id}/media", {"fields": "caption,permalink", "limit": 50, "access_token": self.t}, tag=self.tag)
        for m in r.get("data", []):
            if line in [l.strip() for l in (m.get("caption") or "").splitlines()]:
                return m["id"], m.get("permalink", "")
        return None

    def post(self, item):
        f = {"media_type": "REELS", "upload_type": "resumable", "caption": item["captions"]["instagram"],
             "share_to_feed": "true", "access_token": self.t}
        c = req("POST", f"{self.g}/{self.id}/media", data=form(f), tag=self.tag)
        cid = c["id"]
        core.say(self.tag, f"uploading {os.path.getsize(item['file'])/1e6:.1f} MB")
        push_file(c.get("uri") or f"https://rupload.facebook.com/ig-api-upload/{API}/{cid}", self.t, item["file"])
        for _ in range(20):
            time.sleep(30)
            st = req("GET", f"{self.g}/{cid}", {"fields": "status_code,status", "access_token": self.t}, tag=self.tag)
            if st.get("status_code") == "FINISHED": break
            if st.get("status_code") in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"processing failed: {st.get('status')}  (Instagram's API refuses some longer reels; keep reels at 25s)")
        else:
            raise RuntimeError("still processing after 10 min")
        try:
            mid = req("POST", f"{self.g}/{self.id}/media_publish", data=form({"creation_id": cid, "access_token": self.t}), tag=self.tag)["id"]
        except AuthError: raise
        except RuntimeError as e:
            time.sleep(45)
            live = self.find_live(first_line(item["captions"]["instagram"]))
            if live: return live
            raise RuntimeError(f"publish failed: {e}")
        link = req("GET", f"{self.g}/{mid}", {"fields": "permalink", "access_token": self.t}, tag=self.tag).get("permalink", "")
        return mid, link

class Facebook:
    name, tag, kinds = "facebook", "FB", ("reel", "long")
    def __init__(self):
        t = core.get_key("facebook_token")
        if not t: raise RuntimeError("not connected")
        pid = core.get_key("facebook_page_id")
        if pid:
            pg = req("GET", f"{G_FB}/{pid}", {"fields": "id,name,access_token", "access_token": t})
            if not pg.get("access_token"): raise RuntimeError("this key can't manage the Page " + pg.get("name", pid))
            self.t, self.id, self.page = pg["access_token"], pg["id"], pg["name"]
        else:
            pages = req("GET", f"{G_FB}/me/accounts", {"fields": "id,name,access_token", "limit": 100, "access_token": t}).get("data", [])
            if len(pages) == 1:
                self.t, self.id, self.page = pages[0]["access_token"], pages[0]["id"], pages[0]["name"]
                core.set_key("facebook_page_id", self.id)
            elif pages:
                raise RuntimeError("this key manages several Pages; pick one in Accounts: " + ", ".join(p["name"] for p in pages))
            else:
                me = req("GET", f"{G_FB}/me", {"fields": "id,name", "access_token": t})
                self.t, self.id, self.page = t, me["id"], me["name"]
        self.account = f"Page: {self.page}"

    def room_today(self): return True

    def find_live(self, line):
        ok = 0
        for edge, field in (("video_reels", "description"), ("videos", "description"), ("posts", "message")):
            try:
                r = req("GET", f"{G_FB}/{self.id}/{edge}", {"fields": f"id,{field}", "limit": 100, "access_token": self.t}, tag=self.tag)
            except AuthError: raise
            except RuntimeError: continue
            ok += 1
            for v in r.get("data", []):
                if line in [l.strip() for l in (v.get(field) or "").splitlines()]:
                    vid = v["id"].split("_")[-1]
                    return v["id"], (f"https://www.facebook.com/reel/{vid}" if edge != "posts" else f"https://www.facebook.com/{v['id']}")
        if not ok: raise RuntimeError("couldn't read the Page to check for an existing copy, so nothing was posted")
        return None

    def _wait(self, vid, minutes):
        for _ in range(minutes * 2):
            time.sleep(30)
            try: st = req("GET", f"{G_FB}/{vid}", {"fields": "status", "access_token": self.t}, tag=self.tag).get("status", {})
            except AuthError: raise
            except RuntimeError: return
            phases = [st.get(k, {}).get("status") for k in ("uploading_phase", "processing_phase", "publishing_phase")]
            if st.get("video_status") == "ready" or phases[2] == "complete": return
            if st.get("video_status") == "error" or "error" in phases: raise RuntimeError(f"processing failed: {st}")

    def post(self, item):
        if item["kind"] == "long":
            return self.post_long(item)
        s = req("POST", f"{G_FB}/{self.id}/video_reels", data=form({"upload_phase": "start", "access_token": self.t}), tag=self.tag)
        vid = s["video_id"]
        push_file(s.get("upload_url") or f"https://rupload.facebook.com/video-upload/{API}/{vid}", self.t, item["file"])
        req("POST", f"{G_FB}/{self.id}/video_reels", data=form({"upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED",
            "description": item["captions"]["facebook"], "access_token": self.t}), tag=self.tag)
        self._wait(vid, 15)
        return vid, f"https://www.facebook.com/reel/{vid}"

    def post_long(self, item):
        gv, path = f"https://graph-video.facebook.com/{API}", item["file"]
        size = os.path.getsize(path)
        s = req("POST", f"{gv}/{self.id}/videos", data=form({"upload_phase": "start", "file_size": size, "access_token": self.t}), tag=self.tag)
        sess, vid = s["upload_session_id"], s["video_id"]
        start, end = int(s["start_offset"]), int(s["end_offset"])
        tmp = os.path.join(core.DIRS["logs"], "_chunk.bin")
        with open(path, "rb") as f:
            while start < end:
                f.seek(start)
                with open(tmp, "wb") as c: c.write(f.read(end - start))
                r = subprocess.run(["curl", "-sS", "--max-time", "1800", "-X", "POST", f"{gv}/{self.id}/videos",
                                    "--form-string", "upload_phase=transfer", "--form-string", f"upload_session_id={sess}",
                                    "--form-string", f"start_offset={start}", "--form-string", f"access_token={self.t}",
                                    "-F", f"video_file_chunk=@{tmp}"], capture_output=True, text=True)
                try: j = json.loads(r.stdout)
                except Exception: raise RuntimeError(f"upload rejected: {(r.stdout + r.stderr)[:300]}")
                if "start_offset" not in j: raise RuntimeError(f"upload rejected: {j}")
                start, end = int(j["start_offset"]), int(j["end_offset"])
                _state(self.tag, f"UPLOADING {start/size*100:.0f}%", kind="busy")
        try: os.remove(tmp)
        except OSError: pass
        req("POST", f"{gv}/{self.id}/videos", data=form({"upload_phase": "finish", "upload_session_id": sess, "title": item["title"],
            "description": item["captions"]["facebook"], "published": "true", "access_token": self.t}), tag=self.tag)
        self._wait(vid, 60)
        return vid, f"https://www.facebook.com/{self.id}/videos/{vid}"

class VideoLink:
    """Threads downloads videos by URL, so we serve the file from this Mac through a temporary Cloudflare link."""
    def __init__(self, root):
        cf = core.which("cloudflared")
        if not cf: raise RuntimeError("cloudflared isn't installed (the installer adds it)")
        self.root = root
        sck = socket.socket(); sck.bind(("127.0.0.1", 0)); port = sck.getsockname()[1]; sck.close()
        self.http = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "--directory", root],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.tun = subprocess.Popen([cf, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{port}"],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.base, t0 = None, time.time()
        while time.time() - t0 < 60:
            m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", self.tun.stdout.readline() or "")
            if m: self.base = m.group(0); break
        if not self.base: raise RuntimeError("couldn't open the temporary video link (cloudflared)")
        threading.Thread(target=lambda: [None for _ in self.tun.stdout], daemon=True).start()
        for _ in range(30):     # new links take a while to show up in local DNS; ask Cloudflare's DNS directly
            r = subprocess.run(["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "10",
                                "--doh-url", "https://1.1.1.1/dns-query", self.base + "/"], capture_output=True, text=True)
            if r.stdout.strip() == "200": time.sleep(5); return
            time.sleep(3)

    def url(self, path):
        return self.base + "/" + urllib.parse.quote(os.path.relpath(path, self.root).replace(os.sep, "/"))

    def close(self):
        for pr in (self.tun, self.http):
            try: pr.terminate()
            except Exception: pass

class Threads:
    name, tag, kinds = "threads", "TH", ("reel",)
    def __init__(self):
        self.t = core.get_key("threads_token")
        if not self.t: raise RuntimeError("not connected")
        me = req("GET", f"{G_TH}/me", {"fields": "id,username", "access_token": self.t})
        self.id, self.username = me["id"], me["username"]
        self.account = f"Threads @{self.username}"
        self.link = None

    def room_today(self):
        try:
            r = req("GET", f"{G_TH}/{self.id}/threads_publishing_limit", {"fields": "quota_usage,config", "access_token": self.t}, tag=self.tag)
            d = (r.get("data") or [{}])[0]
            return d.get("quota_usage", 0) < (d.get("config", {}).get("quota_total") or 250)
        except AuthError: raise
        except RuntimeError: return True

    def find_live(self, line):
        try: r = req("GET", f"{G_TH}/{self.id}/threads", {"fields": "id,text,permalink", "limit": 30, "access_token": self.t}, tag=self.tag)
        except AuthError: raise
        except RuntimeError: return None
        for m in r.get("data", []):
            if line in [l.strip() for l in (m.get("text") or "").splitlines()]:
                return m["id"], m.get("permalink", "")
        return None

    def post(self, item):
        if self.link is None: self.link = VideoLink(core.HOME_DIR)
        c = req("POST", f"{G_TH}/{self.id}/threads", data=form({"media_type": "VIDEO", "video_url": self.link.url(item["file"]),
                "text": item["captions"]["threads"][:500], "access_token": self.t}), tag=self.tag)
        cid = c["id"]
        for _ in range(20):
            time.sleep(30)
            st = req("GET", f"{G_TH}/{cid}", {"fields": "status,error_message", "access_token": self.t}, tag=self.tag)
            if st.get("status") == "FINISHED": break
            if st.get("status") in ("ERROR", "EXPIRED"): raise RuntimeError(f"processing failed: {st}")
        else:
            raise RuntimeError("still processing after 10 min")
        mid = req("POST", f"{G_TH}/{self.id}/threads_publish", data=form({"creation_id": cid, "access_token": self.t}), tag=self.tag)["id"]
        try: link = req("GET", f"{G_TH}/{mid}", {"fields": "permalink", "access_token": self.t}, tag=self.tag).get("permalink", "")
        except RuntimeError: link = ""
        return mid, link

CLIENTS = {"instagram": Instagram, "facebook": Facebook, "threads": Threads}

def check(platform):
    """For the Accounts screen: (ok, message)."""
    try:
        c = CLIENTS[platform]()
        return True, f"Connected as {c.account}"
    except AuthError:
        return False, "That key has expired or was revoked. Make a new one (the guide shows how)."
    except Exception as e:
        return False, str(e)[:300]

# ---------------- the scheduler ----------------
RETRYABLE = ("upload rejected", "processing failed", "still processing")

def _last_post_time(q, platform):
    times = [v.get("time", 0) for it in q for p, v in it["posted"].items() if p == platform and v.get("status") == "posted"]
    return max(times) if times else 0

def _next_item(q, platform, kinds, alternate):
    todo = [it for it in q if it["approved"] and it["kind"] in kinds and platform not in it["posted"]]
    if not todo: return None
    if alternate and len(kinds) > 1:
        done = sorted((v.get("time", 0), it["kind"]) for it in q for p, v in it["posted"].items() if p == platform and v.get("status") == "posted")
        last_kind = done[-1][1] if done else "long"
        want = "reel" if last_kind == "long" else "long"
        pick = [it for it in todo if it["kind"] == want]
        if pick: return pick[0]
    return todo[0]

def _mark(item_id, platform, **v):
    with _qlock:
        q = pipeline.queue()
        for it in q:
            if it["id"] == item_id:
                it["posted"][platform] = dict(v, time=time.time())
        pipeline.save_queue(q)

def _post_with_retries(client, item):
    line = first_line(item["captions"].get(client.name) or item["captions"].get("facebook", ""))
    live = client.find_live(line)
    if live:
        core.say(client.tag, f"already live, skipping: {item['title'][:60]}"); return live
    waits = [120, 300, 600]
    for attempt in range(len(waits) + 1):
        try:
            return client.post(item)
        except AuthError: raise
        except RuntimeError as e:
            if attempt == len(waits) or not any(x in str(e) for x in RETRYABLE): raise
            core.say(client.tag, f"Meta refused the upload (try {attempt+1}); nothing was posted. Retrying in {waits[attempt]//60} min", "warn")
            _nap(client.tag, waits[attempt], "RETRYING")

def run_platform(platform):
    tag = CLIENTS[platform].tag
    try:
        client = CLIENTS[platform]()
    except AuthError:
        _state(tag, "KEY EXPIRED", kind="dead"); core.say(tag, "key expired; reconnect it in Accounts", "error"); return
    except Exception as e:
        _state(tag, "NOT CONNECTED", kind="dead", note=str(e)[:200]); return
    _state(tag, "STARTING", kind="busy", account=client.account)
    core.say(tag, f"posting as {client.account}")
    fails = 0
    while not _stop.is_set():
        s = core.load_settings()
        if not s["platforms_on"].get(platform, True):
            _nap(tag, 60, "PAUSED"); continue
        a, b = s["post_hours"]
        if not (a <= datetime.datetime.now().hour < b):
            _nap(tag, 600, "OUTSIDE POSTING HOURS"); continue
        q = pipeline.queue()
        gap = s["post_every_min"].get(platform, 60) * 60 - (time.time() - _last_post_time(q, platform))
        if gap > 0:
            _nap(tag, min(gap, 60), "NEXT POST"); STATUS[tag]["until"] = time.time() + max(0, gap - 60); continue
        item = _next_item(q, platform, client.kinds, s.get("alternate_long", True))
        if not item:
            _nap(tag, 120, "WAITING FOR APPROVED VIDEOS"); continue
        try:
            if not client.room_today():
                _nap(tag, 1800, "DAILY LIMIT REACHED"); continue
            _state(tag, f"POSTING: {item['title'][:40]}", kind="busy")
            core.say(tag, f"posting: {item['title'][:80]}")
            pid, url = _post_with_retries(client, item)
            _mark(item["id"], platform, status="posted", id=pid, url=url)
            core.say(tag, f"posted: {url}", "good")
            fails = 0
        except AuthError:
            _state(tag, "KEY EXPIRED", kind="dead"); core.say(tag, "key expired; reconnect it in Accounts", "error"); return
        except Exception as e:
            fails += 1
            _mark(item["id"], platform, status="error", note=str(e)[:400])
            core.say(tag, f"couldn't post '{item['title'][:50]}': {str(e)[:250]}", "error")
            if fails >= 3:
                _state(tag, "STOPPED AFTER 3 FAILURES", kind="dead"); return
            _nap(tag, 300, "SKIPPED, COOLING DOWN")
    _state(tag, "STOPPED", kind="dead")

_threads = {}

def start_all():
    _stop.clear()
    threading.Thread(target=_daily, daemon=True).start()
    for p in CLIENTS:
        if p in _threads and _threads[p].is_alive(): continue
        if not core.load_settings()["platforms_on"].get(p, True): continue
        t = threading.Thread(target=run_platform, args=(p,), daemon=True); t.start(); _threads[p] = t
    if shutil.which("caffeinate") and not getattr(start_all, "_awake", None):
        start_all._awake = subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())])   # keep the Mac awake while posting

def stop_all():
    _stop.set()

def running():
    return {p: t.is_alive() for p, t in _threads.items()}

def _daily():
    while not _stop.is_set():
        threads_refresh()
        _stop.wait(86400)

def retry(item_id, platform):
    """User pressed 'try again' on a failed post."""
    with _qlock:
        q = pipeline.queue()
        for it in q:
            if it["id"] == item_id and it["posted"].get(platform, {}).get("status") == "error":
                del it["posted"][platform]
        pipeline.save_queue(q)
