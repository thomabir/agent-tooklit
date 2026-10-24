---
name: partsbox
description: PartsBox inventory (stock of BOM parts, project BOM, setup of the API key and the MCP server). Use when a BOM is compared with the parts in stock, or when a PartsBox project is made for a PCB.
---

# PartsBox

Toolkit: `~/code/agent-toolkit`. Decision rules for stock parts: skill `kicad-project`, section "Parts in stock".

## Commands (project Makefile)
- `make stock`: stock per BOM line (exact MPN match, on-hand quantity, low-stock level), candidates for the other lines. Writes `stock.csv` and `order-digikey-against-stock.csv` into the BOM folder (see skill `kicad-project`).
- `make partsbox`: creates the project `<title> v<rev>`, or replaces all its entries with the BOM. Stock parts are linked by MPN; other lines are named entries (MPN, manufacturer and value in the comments). Ask the user before it runs.

## API key (once per machine)
The user writes `PARTSBOX_API_KEY=...` into `~/.partsbox/.env` (mode 600), from PartsBox Settings | Data. The agent never reads or prints the key.

## MCP server (optional, for questions outside the commands)
1. `git clone https://github.com/nickweedon/partsbox_mcp ~/code/partsbox_mcp`
2. `git -C ~/code/partsbox_mcp am ~/code/agent-toolkit/patches/partsbox_mcp-entries-key.patch` (the server sends `project/entries`; the API key is `entries`).
3. `uv python pin --directory ~/code/partsbox_mcp 3.13`, then `uv sync --directory ~/code/partsbox_mcp`.
4. `claude mcp add --scope user partsbox -- uv run --directory ~/code/partsbox_mcp partsbox-mcp`
5. Permissions: allow `list_*` and `get_*`; deny all write tools, `Read(~/.partsbox/**)`.
- On-hand quantity: `get_part_storage`, sources without status. `get_part_stock` returns 0 for parts with stock.
