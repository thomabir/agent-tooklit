---
name: partsbox
description: PartsBox inventory through the MCP server partsbox (setup, stock lookup, project BOM). Use when a BOM is compared with the parts in stock, or when a PartsBox project is made for a PCB.
---

# PartsBox

Toolkit: `github.com/thomabir/agent-tooklit`, local `~/code/agent-toolkit`. Failure modes: L19 in `lessons.md`. Substitution rules for stock parts: skill `kicad-project`, section "Parts in stock".

## Setup (once per machine)
1. `git clone https://github.com/nickweedon/partsbox_mcp ~/code/partsbox_mcp`
2. `git -C ~/code/partsbox_mcp am ~/code/agent-toolkit/patches/partsbox_mcp-entries-key.patch` (L19; patch base: upstream `4e04828`).
3. `uv python pin --directory ~/code/partsbox_mcp 3.13`, then `uv sync --directory ~/code/partsbox_mcp`. With Python 3.11 the server stops at start: pydantic "Please use `typing_extensions.TypedDict` instead of `typing.TypedDict` on Python < 3.12".
4. `claude mcp add --scope user partsbox -- uv run --directory ~/code/partsbox_mcp partsbox-mcp`
5. API key (PartsBox Settings | Data): the user writes `PARTSBOX_API_KEY=...` into `~/.partsbox/.env` (mode 600). The agent never reads or prints the key.
6. Permissions in `~/.claude/settings.json`:
   - allow: all `list_*` and `get_*` tools, `create_project`, `add_project_entries`;
   - ask: `update_project`, `update_project_entries`;
   - deny: all other write tools, `get_image_resource`, `get_file_resource`, `Read(~/.partsbox/**)`, `Edit(~/.partsbox/**)`, `Bash(*.partsbox*)`.
7. Restart Claude Code or `/mcp` reconnect after each change to the server.

## Stock lookup
- `list_parts` with a JMESPath filter on `"part/footprint"`, `"part/name"`, `"part/description"`, `"part/mpn"` (double quotes for field names).
- On-hand quantity: `get_part_storage` (`source/quantity`, status null = on hand). Do not use `get_part_stock` (L19).
- Parts with stock 0 and no MPN are generic library entries, not stock.

## Project BOM
- One project per PCB version, name `<title> v<rev>`.
- Every BOM line is an entry, also lines that are not in stock:
  - stock part: `entry/part-id`, `entry/quantity`, `entry/designators`;
  - other part: no part id, `entry/name` = MPN, `entry/comments` = manufacturer and short description. PartsBox shows it as unmatched; link it to the part after the order is received.
- Check with `get_project_entries`: number of entries = number of BOM lines.
