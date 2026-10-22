---
name: retro
description: End-of-project review that moves new findings into the agent toolkit (lessons, skills, code). Use when the user says "retro", or when a hardware project or feature is finished.
---

# Retro

Toolkit: `github.com/thomabir/agent-tooklit`, local `~/code/agent-toolkit`. Its `AGENTS.md` has the rules for changes.

1. Read the session, `git log` and the diff of the project since the last retro.
2. List candidates:
   - new failure modes (symptom, cause, proof, fix) → `lessons.md`;
   - changes to procedures or acceptance criteria → `skills/*/SKILL.md`;
   - manual steps that occurred twice or more → `hwkit` code;
   - equipment or default changes → `lab/profile.toml`.
3. Each candidate needs evidence from the session (command output, measured value, user statement). Drop candidates without evidence.
4. Show the list to the user in short form. Apply only the approved items.
5. In the toolkit: run the tests, commit, tag a new version (`vX.Y.Z`, minor for new features, patch for fixes), push with tags.
6. In the project: update the pinned `hwkit` tag if the project uses the new code.
