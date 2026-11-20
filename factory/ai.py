"""Talks to whichever AI the user picked: Claude, OpenAI, or a free local model through Ollama.
Every provider gets the same job: look at a few frames (+ what was said) and write a hook."""
import json, base64, re, urllib.request, urllib.error
from . import core

STYLE = """You write hooks for a short-video page about {game}.
Every reel starts with the words "{header}" on screen; you write what comes after it.

Good hooks (style to copy):
- "if you wreck Brian's seaplane, he's waiting at the dock to ask what happened"
- "an NPC climbs back into his burning car just so he can sue"
- "you can sneak through the airport and steal a commercial plane"
- "your neighbour stops you every single time you leave the house"

Rules:
- Plain, casual, human English. Lowercase is fine. Max ~80 characters. No hashtags. No ALL CAPS.
- Describe only what is actually visible in the frames or said in the transcript. Never invent features, story spoilers, news or numbers.
- Be specific, not generic ("you can drive cars" is bad).
- If nothing interesting happens (menus, loading screens, black frames, a talking head with no gameplay), give a low score.
"""

ASK = """These are {n} frames from a {secs}-second clip (timestamps in yellow), in order.
{transcript}
Reply with JSON only, no prose:
{{"score": <1-10, how likely this clip is to make people stop scrolling>,
  "hook": "<text that comes after '{header}'>",
  "emoji": "<one emoji that fits, or empty>",
  "keywords": ["<3 to 5 search phrases like 'gta 6 police chase'>"],
  "best_start": <seconds into this clip where the good part starts, 0 if from the start>,
  "why": "<one short line>"}}"""

class AIError(RuntimeError): pass

def _post(url, headers, body, timeout=120):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=dict(headers, **{"Content-Type": "application/json"}))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise AIError(f"HTTP {e.code}: {e.read().decode(errors='replace')[:400]}")
    except urllib.error.URLError as e:
        raise AIError(f"couldn't reach the AI service ({e.reason})")

def _get(url, headers, timeout=20):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

def ollama_ok():
    try:
        tags = _get("http://127.0.0.1:11434/api/tags", {}, timeout=3)
        return [m["name"] for m in tags.get("models", [])]
    except Exception:
        return None

def pick_provider(s):
    """auto = Claude key if present, else OpenAI key, else Ollama if running, else none."""
    p = s.get("ai_provider", "auto")
    if p != "auto": return p
    if core.get_key("claude_api_key"): return "claude"
    if core.get_key("openai_api_key"): return "openai"
    if ollama_ok(): return "ollama"
    return "none"

def _parse(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m: raise AIError("the AI didn't return JSON")
    d = json.loads(m.group(0))
    d["score"] = float(d.get("score") or 0)
    d["hook"] = re.sub(r"^\s*(in gta vi|in gta 6)[, ]*", "", str(d.get("hook") or "").strip(), flags=re.I).strip(' "')
    d["keywords"] = [str(k) for k in (d.get("keywords") or [])][:5]
    d["best_start"] = float(d.get("best_start") or 0)
    return d

def describe(image_jpg, transcript, secs, s, provider=None):
    """image_jpg: bytes of a frame strip. Returns dict(score, hook, emoji, keywords, best_start, why)."""
    provider = provider or pick_provider(s)
    system = STYLE.format(game=s["game"], header=s["header"])
    t = f'What is said in the clip: "{transcript.strip()[:900]}"' if transcript and transcript.strip() else "There is no transcript."
    user = ASK.format(n=6, secs=int(secs), transcript=t, header=s["header"])
    b64 = base64.b64encode(image_jpg).decode()

    if provider == "claude":
        key = core.get_key("claude_api_key")
        if not key: raise AIError("No Claude API key saved.")
        r = _post("https://api.anthropic.com/v1/messages",
                  {"x-api-key": key, "anthropic-version": "2023-06-01"},
                  {"model": s.get("claude_model"), "max_tokens": 400, "system": system,
                   "messages": [{"role": "user", "content": [
                       {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                       {"type": "text", "text": user}]}]})
        return _parse("".join(c.get("text", "") for c in r.get("content", [])))

    if provider == "openai":
        key = core.get_key("openai_api_key")
        if not key: raise AIError("No OpenAI API key saved.")
        r = _post("https://api.openai.com/v1/chat/completions", {"Authorization": f"Bearer {key}"},
                  {"model": s.get("openai_model"), "max_tokens": 400, "response_format": {"type": "json_object"},
                   "messages": [{"role": "system", "content": system},
                                {"role": "user", "content": [
                                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                                    {"type": "text", "text": user}]}]})
        return _parse(r["choices"][0]["message"]["content"])

    if provider == "ollama":
        r = _post("http://127.0.0.1:11434/api/chat", {},
                  {"model": s.get("ollama_model"), "stream": False, "format": "json",
                   "messages": [{"role": "system", "content": system},
                                {"role": "user", "content": user, "images": [b64]}]}, timeout=600)
        return _parse(r.get("message", {}).get("content", ""))

    raise AIError("no AI set up")

def test(provider, s):
    """Small call to check a key works. Returns (ok, message)."""
    try:
        if provider == "claude":
            _get("https://api.anthropic.com/v1/models", {"x-api-key": core.get_key("claude_api_key"), "anthropic-version": "2023-06-01"})
            return True, "Claude key works."
        if provider == "openai":
            _get("https://api.openai.com/v1/models", {"Authorization": f"Bearer {core.get_key('openai_api_key')}"})
            return True, "OpenAI key works."
        if provider == "ollama":
            models = ollama_ok()
            if models is None: return False, "Ollama isn't running. Open the Ollama app, then try again."
            want = s.get("ollama_model")
            if not any(m.startswith(want.split(":")[0]) for m in models):
                return False, f"Ollama is running but the model isn't downloaded yet. In Terminal run:  ollama pull {want}"
            return True, f"Ollama is ready with {want}."
        return False, "Pick an AI first."
    except urllib.error.HTTPError as e:
        return False, "That key was rejected." if e.code in (401, 403) else f"HTTP {e.code}"
    except Exception as e:
        return False, str(e)[:200]
