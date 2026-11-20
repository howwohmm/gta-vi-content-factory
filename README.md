# GTA VI Content Factory

**Turn your GTA VI gameplay into a posting machine.** Drop in a long stream or playthrough. The factory finds the best moments, writes the hooks, renders vertical reels and long-form parts, makes thumbnails, and posts to Instagram, Facebook and Threads on a schedule while your Mac sits there. YouTube gets ready-to-drag folders.

Runs 100% on your Mac. Free and open source.

```
 long video ──▶ best moments ──▶ reels + long parts ──▶ you approve ──▶ posted on schedule
 (link/file)    (AI or free)      (hooks, captions,       (one click)      IG · FB · Threads
                                   thumbnails)                             + YouTube folders
```

## What you get

- **Clipping that watches the video.** Loudness + scene changes find the action; an AI (Claude, OpenAI, or free local Ollama) looks at each moment and writes a hook like *"In GTA VI, an NPC climbs back into his burning car just so he can sue 💀"*.
- **Reels that look like a real page.** 1080×1920, your header + hook above the clip, inside the safe zone, 25 seconds (the length Instagram's API reliably accepts).
- **Long-form too.** The full session is cut into 25-minute parts with thumbnails in 3 styles. Use your own art as the background.
- **A review screen.** Watch every reel, fix a hook (it re-renders), approve all with one click. Nothing posts without approval.
- **Hands-off posting.** Official Instagram / Facebook / Threads APIs, your schedule, daily limits respected, never double-posts, keys auto-extended, Mac kept awake.
- **YouTube without the audit.** Day folders named with titles + thumbnails + descriptions; drag into Studio, and Claude can schedule them for you (skill included).
- **Simple onboarding.** A 6-step setup wizard in your browser, with step-by-step guides for every key.

## Install (Mac, 3 minutes)

```bash
git clone https://github.com/priyanshuratnakar/gta-vi-content-factory.git
cd gta-vi-content-factory
./install.sh
```

The installer sets up Homebrew (if needed), ffmpeg, yt-dlp, cloudflared and a private Python, then opens the app at **http://localhost:8765**. After that, double-click **`start.command`** to start it.

Apple Silicon recommended (M1 or newer). Intel Macs work, local AI is slower.

## Your first day

1. **Setup wizard.** Name your page, pick the AI, connect accounts, pick a thumbnail style.
2. **Add a long video.** Paste a link to your stream VOD, or drop a file into `~/GTA VI Content Factory/Drop videos here`.
   *Tip: on PS5/Xbox, stream straight to a (private/unlisted) YouTube channel while you play, then paste the link.*
3. **Review.** Watch the reels, edit any hook, **Approve all**.
4. **Start posting.** Leave the Mac on, plugged in, lid open. The Home screen shows what's posting next.
5. **YouTube.** Press **Make Day folders**, drag one into YouTube Studio, ask Claude to schedule them (or do it yourself).

## AI options

| Option | Cost | Quality | Needs |
|---|---|---|---|
| Claude | a few cents per long video | best hooks | Anthropic API key |
| OpenAI | similar | great | OpenAI API key |
| Free local | free | good, slower | [Ollama](https://ollama.com) + `ollama pull qwen2.5vl:7b` |
| No AI | free | you write hooks | nothing |

Speech-to-text (better hooks when people talk in the video) is installed automatically on Apple Silicon.

## Platform limits (built in)

| Platform | How | Limit the factory respects |
|---|---|---|
| Instagram | Graph API (your Meta app) | ~50 posts / 24h; reels ≤ ~30s on some accounts |
| Facebook Page | Graph API | 30 API reels / 24h; long videos up to 4h |
| Threads | Threads API | 250 posts / 24h |
| YouTube | Studio drag-and-drop + Claude skill | channel daily upload limit (verify your channel to raise it) |
| X | not yet (paid API) | |

## Claude skills (optional)

`skills/` has step-by-step skills Claude can follow in your browser:

- **meta-setup**: creates your Meta app and gets your Instagram/Facebook/Threads keys
- **page-setup**: names, bios and links across all platforms
- **youtube-studio-scheduler**: schedules your dragged-in drafts, sets details and thumbnails

## Use footage you're allowed to use

The best source is **your own gameplay**: record or stream it yourself. Clipping other creators needs their permission (many run clipping programs) and a credit (Settings → credit line). Re-uploading other people's videos gets pages struck and removed. You're responsible for what you post.

Not affiliated with Rockstar Games or Take-Two Interactive. "Grand Theft Auto" and "GTA" are their trademarks.

## Where things live

```
~/GTA VI Content Factory/
  Drop videos here/      drop long videos here
  Projects/              one folder per video: source, reels, long parts, covers
  YouTube uploads/       Day folders to drag into YouTube Studio
  Cover backgrounds/     your own thumbnail art
  queue.json             what's approved and what's been posted where
  logs/                  everything the factory did
  _to_delete/            replaced files (the factory never deletes your stuff)
```

## Roadmap

- [ ] Trial Reels on Instagram (for eligible accounts)
- [ ] Threads photo + question posts between reels
- [ ] X / Twitter (bring your own paid API key)
- [ ] Follower + views dashboard
- [ ] Windows support
- [ ] Pro: cloud rendering, more thumbnail packs, multi-page management

## Contributing

Issues and PRs welcome. Keep the UX simple enough for someone who has never opened Terminal.

## License

[AGPL-3.0](LICENSE). Free to use, change and share. If you run a modified version as a service for others, you must share your changes under the same license.
