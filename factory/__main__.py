"""python -m factory               start in the mode you picked during setup (browser or terminal)
python -m factory --web         browser dashboard
python -m factory --terminal    terminal dashboard (the web app keeps running too, for reviewing reels)
python -m factory add <link|file>   hand a video to a running factory
python -m factory status            one-line summary from a running factory
"""
import json, os, shutil, sys, threading, time, urllib.request, webbrowser

PORT = int(os.environ.get("GVCF_PORT", "8765"))
URL = f"http://localhost:{PORT}"


def _call(path, body=None):
    req = urllib.request.Request(URL + path, method="POST" if body is not None else "GET",
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", "x-gvcf": "1"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)


def cli(args):
    cmd = args[0]
    try:
        if cmd == "status":
            s = _call("/api/state")
            on = any(s["posting"]["running"].values())
            print(f"{s['settings'].get('page_name') or 'Your page'} · posting {'ON' if on else 'off'} · queue {s['queue_size']}")
            for p, c in s["counts"].items():
                print(f"  {p:<10} {c['posted']:>4} posted  {c['waiting']:>4} waiting  {c['error']:>3} failed")
            return
        if cmd == "add" and len(args) > 1:
            what = args[1]
            if what.startswith("http"):
                _call("/api/videos/link", {"url": what}); print("Added. Clipping has started.")
            else:
                from . import core
                shutil.copy2(what, core.DIRS["inbox"]); print("Copied into the inbox. Clipping starts within 20 seconds.")
            return
    except OSError:
        print("The factory isn't running. Start it with ./start.sh first."); sys.exit(1)
    print(__doc__)


def main():
    args = sys.argv[1:]
    if args and not args[0].startswith("-"):
        return cli(args)
    from . import server, core
    s = core.load_settings()
    mode = "terminal" if "--terminal" in args else "web" if "--web" in args else (s.get("launch_mode") or "web")
    if not s.get("setup_done"):
        mode = "web"   # setup happens in the browser, once
    if mode == "terminal":
        core.QUIET = True
    server.boot()
    import uvicorn
    if mode == "terminal":
        cfg = uvicorn.Config(server.app, host="127.0.0.1", port=PORT, log_level="critical", access_log=False)
        threading.Thread(target=uvicorn.Server(cfg).run, daemon=True).start()
        from . import tui
        core.say("factory", f"terminal dashboard on · web app still at {URL}")
        tui.run(URL)
        return
    core.say("factory", f"Content Factory is running at {URL}  (keep this window open; Ctrl+C to stop)")
    if "--no-browser" not in args:
        threading.Thread(target=lambda: (time.sleep(1.2), webbrowser.open(URL)), daemon=True).start()
    uvicorn.run(server.app, host="127.0.0.1", port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
