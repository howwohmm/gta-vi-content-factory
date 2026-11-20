"""python -m factory  ->  starts the Content Factory and opens it in your browser."""
import os, sys, threading, time, webbrowser

def main():
    port = int(os.environ.get("GVCF_PORT", "8765"))
    from . import server, core
    server.boot()
    url = f"http://localhost:{port}"
    core.say("factory", f"Content Factory is running at {url}  (keep this window open; Ctrl+C to stop)")
    if "--no-browser" not in sys.argv:
        threading.Thread(target=lambda: (time.sleep(1.2), webbrowser.open(url)), daemon=True).start()
    import uvicorn
    uvicorn.run(server.app, host="127.0.0.1", port=port, log_level="warning")

if __name__ == "__main__":
    main()
