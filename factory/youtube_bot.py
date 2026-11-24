"""100% local YouTube Studio Auto-Uploader & Public Scheduler via real Google Chrome + Playwright CDP.

Why CDP over native Google Chrome.app instead of bundled Chromium:
- Google Sign-In blocks Playwright's bundled Chromium ("This browser or app may not be secure").
- Launching real `/Applications/Google Chrome.app` with a dedicated `--user-data-dir` + `--remote-debugging-port=9229`
  lets the user sign into YouTube Studio ONCE cleanly, persists cookies across restarts, and lets Playwright drive
  unlimited daily Shorts + Long-Form Public Scheduled uploads with custom thumbnails & descriptions (bypassing
  Google's 6/day unaudited Data API Private lock).
"""
import os, re, time, json, socket, datetime, subprocess, urllib.request
from . import core, pipeline

CDP_PORT = 9229
PROFILE_DIR = os.path.join(core.HOME_DIR, ".yt_chrome_profile")
SCHED_LEDGER = os.path.join(core.DIRS["logs"], "youtube_scheduled.json")

CHROME_PATHS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/usr/bin/google-chrome",
]

def _chrome_bin():
    for p in CHROME_PATHS:
        if os.access(p, os.X_OK):
            return p
    return core.which("google-chrome") or core.which("chromium")

def _cdp_up(port=CDP_PORT):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1.5) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None

def launch_studio_browser():
    """Launch real Google Chrome with persistent YouTube profile + CDP port 9229 and open studio.youtube.com."""
    os.makedirs(PROFILE_DIR, exist_ok=True)
    if _cdp_up():
        return {"ok": True, "already_open": True, "profile": PROFILE_DIR}
    chrome = _chrome_bin()
    if not chrome:
        raise RuntimeError("Google Chrome wasn't found in /Applications. Install Google Chrome first.")
    subprocess.Popen(
        [
            chrome,
            f"--user-data-dir={PROFILE_DIR}",
            f"--remote-debugging-port={CDP_PORT}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-popup-blocking",
            "https://studio.youtube.com",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    for _ in range(25):
        if _cdp_up():
            break
        time.sleep(0.4)
    return {"ok": True, "already_open": False, "profile": PROFILE_DIR}

def studio_status():
    """Return {browser_open, signed_in, channel_url, scheduled_count, day_folders}."""
    root = core.DIRS["youtube"]
    os.makedirs(root, exist_ok=True)
    days = sorted(
        [d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d)) and not d.startswith(".")],
        reverse=True,
    )
    led = core.read_json(SCHED_LEDGER, {})
    info = {
        "browser_open": False,
        "signed_in": False,
        "channel_url": "",
        "scheduled_count": len(led),
        "day_folders": days,
    }
    if not _cdp_up():
        return info
    info["browser_open"] = True
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/list", timeout=2) as r:
            tabs = json.loads(r.read().decode())
        for t in tabs:
            u = t.get("url") or ""
            if "studio.youtube.com/channel/" in u or u.rstrip("/") == "https://studio.youtube.com":
                if "accounts.google.com" not in u:
                    info["signed_in"] = "studio.youtube.com/channel/" in u
                    info["channel_url"] = u
                    if info["signed_in"]:
                        break
    except Exception:
        pass
    return info

def parse_day_folder(day_dir):
    """Return ordered list of {mp4, thumb, title, description} for a Day folder."""
    notes_file = os.path.join(day_dir, "_titles and descriptions.txt")
    desc_by_idx = {}
    desc_by_title = {}
    if os.path.isfile(notes_file):
        raw = open(notes_file, encoding="utf-8").read()
        for block in re.split(r"-{20,}\n?", raw):
            lines = [l.rstrip() for l in block.strip().splitlines() if l.strip()]
            if not lines:
                continue
            head = lines[0]
            body = "\n".join(lines[1:]).strip()
            m = re.match(r"^\[(\d+)\]\s*(.*)$", head)
            if m:
                desc_by_idx[int(m.group(1))] = (m.group(2).strip(), body)
            else:
                desc_by_title[head.strip()] = body

    mp4s = sorted(f for f in os.listdir(day_dir) if f.lower().endswith(".mp4") and not f.startswith("."))
    items = []
    for i, fname in enumerate(mp4s, 1):
        mp4_path = os.path.join(day_dir, fname)
        stem = os.path.splitext(fname)[0]
        thumb_path = os.path.join(day_dir, stem + " - thumbnail.jpg")
        m_num = re.match(r"^(\d+)\s*-\s*(.*)$", stem)
        idx = int(m_num.group(1)) if m_num else i
        clean_stem = m_num.group(2).strip() if m_num else stem
        if idx in desc_by_idx:
            title, desc = desc_by_idx[idx]
        else:
            title = clean_stem
            desc = desc_by_title.get(stem) or desc_by_title.get(clean_stem) or f"{title}\n\n#gta6 #gtavi #Shorts"
        items.append({
            "mp4": mp4_path,
            "thumb": thumb_path if os.path.isfile(thumb_path) else "",
            "title": title[:100],
            "description": desc[:4900],
        })
    return items

def _round_15m(dt: datetime.datetime) -> datetime.datetime:
    dt = dt.replace(second=0, microsecond=0)
    rem = dt.minute % 15
    if rem:
        dt += datetime.timedelta(minutes=(15 - rem))
    return dt

def _next_schedule_slots(n, spacing_min=45, start_in_min=30):
    led = core.read_json(SCHED_LEDGER, {})
    latest_ts = max((v.get("scheduled_ts", 0) for v in led.values()), default=0)
    base_ts = max(time.time() + start_in_min * 60, latest_ts + spacing_min * 60)
    cur = _round_15m(datetime.datetime.fromtimestamp(base_ts))
    slots = []
    step = max(15, round(spacing_min / 15) * 15)
    for _ in range(n):
        slots.append(cur)
        cur = _round_15m(cur + datetime.timedelta(minutes=step))
    return slots

def _set_textbox(page, selector, text):
    box = page.locator(selector).first
    box.wait_for(state="visible", timeout=25000)
    box.click()
    time.sleep(0.2)
    page.keyboard.press("Meta+A")
    page.keyboard.press("Backspace")
    time.sleep(0.15)
    if text:
        box.fill(text)

def _pick_schedule_datetime(page, target_dt: datetime.datetime):
    # Expand schedule section
    sched_radio = page.locator('tp-yt-paper-radio-button[name="SCHEDULE"], #second-container-expand-button').first
    sched_radio.scroll_into_view_if_needed()
    sched_radio.click()
    time.sleep(0.8)

    # 1. Date input
    dp_trigger = page.locator("#datepicker-trigger").first
    dp_trigger.click()
    time.sleep(0.6)
    date_input = page.locator("ytcp-date-picker tp-yt-paper-input input, ytcp-date-picker input").first
    date_input.wait_for(state="visible", timeout=10000)
    for fmt in ("%b %d, %Y", "%d %b %Y", "%m/%d/%Y"):
        candidate = target_dt.strftime(fmt).replace(" 0", " ")
        date_input.click()
        page.keyboard.press("Meta+A")
        page.keyboard.type(candidate)
        page.keyboard.press("Enter")
        time.sleep(0.5)
        if not page.locator("ytcp-date-picker tp-yt-paper-input[invalid]").count():
            break

    # 2. Time input (15-min increment)
    t_12 = target_dt.strftime("%I:%M %p").lstrip("0")   # e.g. "2:30 PM"
    t_24 = target_dt.strftime("%H:%M")                 # e.g. "14:30"
    time_input = page.locator("#time-of-day-container input, ytcp-datetime-picker tp-yt-paper-input input").last
    if time_input.count():
        time_input.click()
        time.sleep(0.4)
        # Try clicking exact dropdown option first (normalizing narrow no-break spaces per YouTube Studio quirk)
        clicked_opt = page.evaluate(
            """([t12, t24]) => {
                const norm = s => (s || '').replace(/[\\u202f\\u00a0\\s]+/g, ' ').trim().toUpperCase();
                const items = [...document.querySelectorAll('tp-yt-paper-item')];
                const hit = items.find(el => {
                    const txt = norm(el.textContent);
                    return txt === norm(t12) || txt === norm(t24);
                });
                if (hit) { hit.click(); return true; }
                return false;
            }""",
            [t12_s := t_12, t_24],
        )
        if not clicked_opt:
            page.keyboard.press("Meta+A")
            page.keyboard.type(t_12)
            page.keyboard.press("Enter")
        time.sleep(0.5)

def autopost_day_job(job, day_name="S-Tier Day 01", spacing_min=45, max_videos=15):
    """Background job: uploads & schedules every unscheduled video in `day_name` on YouTube Studio."""
    day_dir = os.path.join(core.DIRS["youtube"], day_name)
    if not os.path.isdir(day_dir):
        raise RuntimeError(f"Day folder not found: {day_dir}. Build a Day pack first.")

    launch_studio_browser()
    items = parse_day_folder(day_dir)
    if not items:
        raise RuntimeError(f"No .mp4 files in {day_name}.")

    led = core.read_json(SCHED_LEDGER, {})
    todo = []
    for it in items:
        sha = pipeline.file_sha256(it["mp4"])
        if sha in led:
            continue
        it["sha256"] = sha
        todo.append(it)
        if len(todo) >= max_videos:
            break

    if not todo:
        core.say("YT", f"All videos in '{day_name}' are already scheduled on YouTube!", "good")
        return {"scheduled": 0, "skipped": len(items)}

    slots = _next_schedule_slots(len(todo), spacing_min=spacing_min)
    from playwright.sync_api import sync_playwright

    scheduled_n = 0
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(f"http://127.0.0.1:{CDP_PORT}")
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = next((p for p in ctx.pages if "studio.youtube.com" in (p.url or "")), None)
        if page is None:
            page = ctx.new_page()
            page.goto("https://studio.youtube.com", wait_until="domcontentloaded", timeout=45000)
        time.sleep(3.0)

        if "accounts.google.com" in (page.url or "") or "studio.youtube.com/channel/" not in (page.url or ""):
            page.bring_to_front()
            raise RuntimeError(
                "Sign into your YouTube Studio account in the Google Chrome window that just opened, "
                "then click 'Start Auto-Schedule' again!"
            )

        for idx, (it, slot_dt) in enumerate(zip(todo, slots), 1):
            slot_str = slot_dt.strftime("%b %d · %I:%M %p")
            job.update((idx - 0.8) / len(todo), f"[{idx}/{len(todo)}] Uploading: {it['title'][:42]} ({slot_str})")
            core.say("YT", f"[{idx}/{len(todo)}] uploading '{it['title'][:55]}' -> schedule {slot_str}")

            if "studio.youtube.com/channel/" not in (page.url or ""):
                page.goto("https://studio.youtube.com", wait_until="domcontentloaded", timeout=45000)
                time.sleep(2.5)

            # Close any leftover modal
            try:
                if page.locator("ytcp-uploads-dialog #close-button, ytcp-uploads-still-processing-dialog #close-button").count():
                    page.locator("ytcp-uploads-dialog #close-button, ytcp-uploads-still-processing-dialog #close-button").first.click(timeout=2000)
                    time.sleep(1.0)
            except Exception:
                pass

            # Click Create -> Upload videos
            create_btn = page.locator("#create-icon, ytcp-button#create-icon, button[aria-label='Create']").first
            create_btn.wait_for(state="visible", timeout=20000)
            create_btn.click()
            time.sleep(0.8)
            upload_item = page.locator("#text-item-0, tp-yt-paper-item:has-text('Upload videos')").first
            upload_item.wait_for(state="visible", timeout=10000)
            upload_item.click()
            time.sleep(1.0)

            file_in = page.locator("ytcp-uploads-file-picker input[type='file'], input[type='file'][name='Filedata']").first
            file_in.set_input_files(it["mp4"])
            time.sleep(2.5)

            # Details: Title, Description, Thumbnail, Not made for kids
            _set_textbox(page, "#title-textarea #textbox", it["title"])
            _set_textbox(page, "#description-textarea #textbox", it["description"])

            if it["thumb"] and os.path.isfile(it["thumb"]):
                try:
                    th_in = page.locator("ytcp-thumbnails-compact-editor input[type='file'], input#file-loader").first
                    if th_in.count():
                        th_in.set_input_files(it["thumb"])
                        time.sleep(1.0)
                except Exception:
                    pass

            not_kids = page.locator('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]').first
            not_kids.scroll_into_view_if_needed()
            not_kids.click()
            time.sleep(0.5)

            # Advance 3 steps -> Visibility
            for _ in range(3):
                nxt = page.locator("#next-button").first
                nxt.wait_for(state="visible", timeout=15000)
                nxt.click()
                time.sleep(1.0)

            _pick_schedule_datetime(page, slot_dt)

            # Wait until file bytes finish uploading before pressing Schedule (#done-button)
            for _ in range(180):
                prog_txt = ""
                try:
                    if page.locator("ytcp-video-upload-progress").count():
                        prog_txt = page.locator("ytcp-video-upload-progress").first.inner_text()
                except Exception:
                    pass
                done_btn = page.locator("#done-button").first
                is_disabled = done_btn.get_attribute("disabled") is not None or done_btn.get_attribute("aria-disabled") == "true"
                if "Uploading" not in prog_txt and not is_disabled:
                    break
                time.sleep(2.0)

            page.locator("#done-button").first.click()
            time.sleep(3.5)

            # Dismiss "Video scheduled" confirmation modal
            for _ in range(15):
                close_b = page.locator(
                    "ytcp-uploads-still-processing-dialog #close-button, "
                    "ytcp-video-share-dialog #close-button, "
                    "ytcp-dialog #close-button"
                ).first
                if close_b.count() and close_b.is_visible():
                    close_b.click()
                    break
                time.sleep(1.0)
            time.sleep(1.5)

            led = core.read_json(SCHED_LEDGER, {})
            led[it["sha256"]] = {
                "file": os.path.basename(it["mp4"]),
                "day": day_name,
                "title": it["title"],
                "scheduled_for": slot_dt.isoformat(),
                "scheduled_ts": slot_dt.timestamp(),
                "uploaded_at": time.time(),
            }
            core.write_json(SCHED_LEDGER, led)
            scheduled_n += 1
            core.say("YT", f"scheduled #{idx}: '{it['title'][:50]}' for {slot_str}", "good")
            job.update(idx / len(todo), f"Scheduled {idx}/{len(todo)}: {slot_str}")

    return {"scheduled": scheduled_n, "day": day_name}
