---
name: content-factory-youtube-scheduler
description: Schedules Content Factory videos that the user dragged into YouTube Studio as drafts, sets details (title, description, not made for kids, thumbnail) and spaces them out. Use when the user says "schedule my YouTube drafts", "set up the long videos on YouTube", or uploads a Day folder.
---

# YouTube Studio scheduling for GTA VI Content Factory

YouTube's API keeps uploads from unaudited apps private, so the user drags files from `~/GTA VI Content Factory/YouTube uploads/Day NN` into YouTube Studio. They land as **drafts**. You finish them in Studio via the browser.

## Rules
- Only touch videos on the user's own channel that are Drafts or that they asked you to reschedule.
- Never publish immediately unless asked; always schedule.
- Don't change channel settings. Ask before uploading anything yourself.

## Inputs
- Each Day folder has `_titles and descriptions.txt` (title + description per video, in posting order) and `… - thumbnail.jpg` files for long parts.
- Default cadence: one Short every 30 minutes, long videos twice a day 12 hours apart (e.g. 4:00 PM and 4:00 AM in the user's time zone). Ask the user if they want something else.
- Order: follow the file order in `_titles and descriptions.txt` (reels alternate with gameplay parts).

## Per draft (Studio → Content → Shorts or Videos tab → "Edit draft")
1. Details: title is already the file name. For long videos, paste the description from the txt file (select-all in the description box, then insert the text).
2. Set **No, it's not made for kids**. Tip: `document.querySelector('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]').click()`.
3. Press Next three times (`#next-button`) to reach Visibility, expand Schedule (`#second-container-expand-button`).
4. Date: open the date picker and click the day in the calendar (typing into the field does not stick).
5. Time: open the time list and click the exact option. Option labels use a narrow no-break space (` `) before AM/PM, so match text after normalising spaces.
6. Check the time zone shows the user's local zone, click **Schedule**, and read the "Video scheduled … on <date> at <time>" confirmation before closing.

## Thumbnails for long videos
Studio's upload dialog doesn't take thumbnails from browser automation unless the user shares the image files into the chat first. Ask them to drag the `… - thumbnail.jpg` files into the conversation, then on each video's details page (`studio.youtube.com/video/<id>/edit`) use the thumbnail file input, check the preview shows the right PART number, and Save.

## Rescheduling (already scheduled videos)
Content list → hover the row → Visibility dropdown chevron → change date/time in the popover → Schedule. Scroll the row to the middle of the screen first so the popover opens in the same place each time.

## Finish
Reload the Content list and confirm every video shows Scheduled with the expected date. Report a table of time → video to the user.
