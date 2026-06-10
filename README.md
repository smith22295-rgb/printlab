# PrintLab

Personal 3D print file maker. No subscriptions, no per-model API fees — Claude
writes the geometry as code on this machine and exports print-ready STLs.

## How to use it

Open Claude Code and describe the part in plain English:

> "Make me a wall hook for a 3/4 inch closet rod, two screw holes"
> "A box with a sliding lid, 80 x 60 x 40 inside"
> "A keychain that says ELLIE in rounded letters"
> "Turn this photo into a lithophane" (attach the photo)

Claude writes a script in `parts/`, runs it, and the STL lands in `output/`.
Every part script has a `P = {...}` settings block at the top — say "make it
20mm wider" or "thicker base" and Claude adjusts and re-runs.

## Previewing

Double-click `viewer.html` and drag any STL onto it. Spin with the mouse,
scroll to zoom. The blue square is the Bambu P1S build plate (256 x 256 mm).

## Printing

Drag the STL from `output/` into Bambu Studio and slice as usual. Every
exported file is checked watertight before it's written.

## What it can't do

Organic sculpts (figurines from photos, faces, animals) need specialized
AI mesh models — that's the one Meshy thing this doesn't replace. Functional
parts, organizers, mounts, text, signs, cookie cutters, vases, lithophanes:
all covered.
