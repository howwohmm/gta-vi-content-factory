---
name: content-factory-meta-setup
description: Walks a Content Factory user through creating their Meta developer app and getting Instagram, Facebook Page and Threads keys in the browser. Use when someone says "set up my Meta app", "connect Instagram/Facebook/Threads to the content factory", or their key expired.
---

# Meta app + keys for GTA VI Content Factory

You are helping a creator connect their Instagram, Facebook Page and Threads to the Content Factory running on their Mac (http://localhost:8765 → Accounts). Work in their browser. Go one step at a time and confirm what you see on screen before moving on.

## Hard rules
- Never type passwords, 2FA codes, app secrets or access tokens into any page. When a key appears, tell the user to copy it (or click Meta's Copy button for them) and paste it into the factory's Accounts page themselves.
- Ask before accepting any terms, permissions dialog or app review prompt, and before changing account settings.
- Use the user's own accounts only. Don't create accounts for them.

## 0. Check prerequisites
1. Instagram must be a Professional account (Business or Creator). In Instagram: Settings → Account type and tools. If it isn't, tell the user how to switch; don't do it without a yes.
2. The Instagram account must be linked to their Facebook Page (Page → Settings → Linked accounts → Instagram). New Pages experience Pages sometimes don't show up in `/me/accounts`; that's fine, the factory accepts a Page ID.

## 1. Create the app
1. Open https://developers.facebook.com/apps → Create app. Name: "<page name> poster".
2. Use cases to add: **Manage everything on your Page**, **Instagram API** (with Facebook login), **Access the Threads API**.
3. If asked for a business portfolio, the user can pick theirs or skip.
4. App settings → Basic: show the user where **App ID** and **App secret** are. They paste both into the factory (Accounts → "Your Meta app"). This lets the factory turn 1-hour keys into 60-day keys and refresh Threads keys by itself.

## 2. Instagram + Facebook key
1. Open https://developers.facebook.com/tools/explorer/ and select their app (top right).
2. Add permissions: `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`, `instagram_basic`, `instagram_content_publish`, `business_management`.
3. Click **Generate Access Token**. In the popup the user ticks their Page and Instagram account and approves (ask first).
4. The user copies the token (starts with `EAA`) into Accounts → Instagram + Facebook → Connect. The factory extends it and finds the Page + Instagram account.
5. If they manage several Pages, get the Page ID from the Page's About/Page transparency section, or from the Explorer: `GET me/accounts`.

## 3. Threads key
1. App → Use cases → Access the Threads API → Customize: make sure `threads_basic` and `threads_content_publish` are added.
2. App roles → Roles → Threads testers → Add the user's Threads username.
3. The user accepts the invite in the Threads app: Settings → Account → Website permissions → Invites.
4. Back on the Threads API settings page: **User Token Generator** → Generate Access Token for their account. Click Copy for them; they paste it into Accounts → Threads → Connect.

## 4. Verify
In the factory, each card should show "connected as …". If Instagram says it can't find the account, the Instagram isn't linked to the Page yet (step 0.2).

## Common errors
- `code 190`: key expired → generate a new one (steps 2/3). With the app secret saved this rarely happens.
- `Application does not have permission for this action` on Instagram trial reels: the account isn't eligible for trial reels yet; normal reels still work.
- Instagram `ProcessingFailedError` on upload: some accounts only accept API reels around 30s; keep reels at 25s (factory default).
