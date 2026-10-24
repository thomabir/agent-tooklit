---
name: retro
description: End-of-project review that moves new findings into the agent toolkit (code, skills, lessons) and the project files. Use when the user says "retro", or when a hardware project or feature is finished.
---

# Retro

Toolkit: `~/code/agent-toolkit`. Its `AGENTS.md` has the rules for changes.

1. Read the session, `git log` and the diff of the project since the last retro.
2. List candidates, in this order of preference:
   - a manual step that occurred twice or more, or a tool that behaved unexpectedly → `hwkit` code (fix, check, or helper);
   - a change to a procedure → `skills/*/SKILL.md`;
   - a general design principle, valid for other projects → one bullet in `lessons.md`;
   - a project decision and its reason → project `DESIGN.md` (propose; the user writes larger edits);
   - a fact only the agent needs for this project → project `AGENTS.md`;
   - an equipment or default change → `lab/profile.toml`.
3. Each candidate needs evidence from the session (command output, measured value, user statement). Drop candidates without evidence.
4. A lesson is a principle, not an incident. Example: "PRJ-0042 had a reversed diode" → "Check devices with polarity against the datasheet, the symbol and the footprint."
5. Show the list to the user in short form. Apply only the approved items.
6. `hwkit lessons check lessons.md`: at more than 100 entries, compress (merge, abstract, or move to `lessons-archive.md`) before you add. Each removed or replaced entry goes to the archive, in a new section with the date.
7. In the toolkit: run the tests, commit, tag a new version, push with tags (ask first).
8. In the project: update the pinned `hwkit` tag if the project uses the new code.
