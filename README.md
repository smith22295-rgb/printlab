# PrintLab

Personal 3D print file maker — a desktop app that turns plain-English
descriptions into print-ready STLs. No subscriptions, no per-model fees:
new parts are forged by Claude Code (your existing plan), and size tweaks
re-run locally for free.

## Starting it

Double-click **PrintLab** on the Desktop (or `PrintLab.bat` in this folder).
It starts the local server and opens the app window.

## Setting up on another PC

Clone the repo and double-click `setup.bat` — it builds the Python
environment, generates the icon, and puts PrintLab on the Desktop.
Needs Python 3.11+ and the Claude desktop app installed.

## First run only

The forge engine needs a one-time login (it's Claude Code under the hood,
using the plan you already pay for):

1. Click **Forge it** on anything — the app will show a "Connect" card
2. Click **Connect** — a terminal opens
3. Type `/login`, press Enter, finish the sign-in in your browser
4. Close the terminal and forge again — it sticks from then on

## Using it

- **Forge a part** — describe it in the box ("a wall hook for a 19mm closet
  rod, two screw holes") and click Forge. Watch the engine work in the live
  console; the finished part loads in the viewer. Takes a minute or two.
- **Tweak sizes free** — every part's dimensions appear as editable fields.
  Change a number, click **Rebuild** — instant, no Claude usage. **Save as
  defaults** writes the values into the part permanently.
- **Modify with words** — select a part, tick "modify", and describe the
  change ("add a second hook below the first").
- **Print** — **Open in slicer** sends the STL to Bambu Studio;
  **Show file** reveals it in Explorer. STLs live in `output/`.

You can also just ask Claude Code directly in this folder — same toolkit,
same conventions (see CLAUDE.md).

## What it can't do

Organic sculpts (figurines, faces, animals from photos) need specialized AI
mesh models. Functional parts, organizers, mounts, text, signs, cookie
cutters, vases, lithophanes: all covered.
