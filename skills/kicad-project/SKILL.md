---
name: kicad-project
description: KiCad PCB project rules and outputs (schematic and board PDFs, manufacturing files, interactive BOM, DigiKey and Mouser order files, README, release). Use for any KiCad schematic or PCB work, when outputs or the README must be updated, or when a board goes to manufacturing.
---

# KiCad project

Toolkit: `github.com/thomabir/agent-tooklit`, local `~/code/agent-toolkit` (package `hwkit`). Failure modes: `lessons.md`. Field names, author, ground nets, grid: `lab/profile.toml` section `[kicad]`.

## Design rules
- Title block (schematic, every sheet, and PCB): title, author (field `company`), version (field `rev`, `Major.Minor`), date (`YYYY-MM-DD`). Same values in all files.
- The user decides when the version increments. The agent does not change `rev` without an instruction.
- PCB silkscreen: title block fields as text variables (`${TITLE}`, `${REVISION}`, `${ISSUE_DATE}`, `${COMPANY}`), if there is space.
- Every BOM symbol: fields Manufacturer, MPN, DigiKey (product link), Mouser (product link). Symbols without a physical part: set "Exclude from BOM".
- Every BOM symbol: field `DigiKey PN`, DigiKey part number (`-ND`), for SMD parts the cut-tape variant (`CT-ND`, `-1-ND`). With an MPN, the DigiKey upload selects a packaging variant itself (often tape and reel, "quantity not available in the selected packaging") or reports "duplicate manufacturer part number". Get the number from the DigiKey product page and check it there.
- Optional symbol field `Order Qty` (non-negative integer): `0` = part in stock, not in the order files. `N` = order max(N, quantity × `--boards`).

## Parts in stock
Before an order, compare the R and C lines of the BOM with the stock in PartsBox (MCP server `partsbox`, on-hand quantity from `get_part_storage`).
- Use a stock part if its specification is identical or better for the circuit (value, package, voltage, dielectric, tolerance, temperature coefficient, power). A lower rating is acceptable if the circuit does not need it (example: 25 V capacitor on a board with no voltage near 25 V). Write the stock part into the symbol fields and set `Order Qty` to `0`.
- A better stock part in a higher price class (example: thin film for thick film): do not substitute. Order the BOM part and add it to the library.
- New library part (a jellybean R or C that is not in stock): set `Order Qty` to a quantity worth a few USD, to get the quantity price.
- Ground pour on the ground nets. Connect ground pads to the pour, not with tracks.
- Mounting holes: footprints from library `MountingHole`, preferably at the corners. Positions on an integer mm grid relative to the outline bounding-box corner.
- Board corners rounded: arcs between Edge.Cuts lines, or a rectangle with a corner radius.

## Check
`uv run hwkit kicad check <project>.kicad_pro`: title blocks, outline corners, mounting-hole grid, filled ground zones, BOM fields, ERC and DRC errors (with schematic parity). Exit status 0 = no issues. `NOTE:` lines are recommendations.
Fill the zones in KiCad (key B) and save before the check, else the check reports "not filled".

## Outputs
`uv run hwkit kicad outputs <project>.kicad_pro --out outputs --boards <n>` writes:
- `outputs/docs/`: `<name>-schematic.pdf`, `<name>-board.pdf` (one page per copper, silkscreen and fab layer), `<name>-top.png`, `<name>-bottom.png`.
- `outputs/manufacturing/`: `gerbers/` (Gerbers, Excellon drill, drill map), `<name>-v<rev>-gerbers.zip`, `<name>-pos.csv`.
- `outputs/bom/`: `<name>-bom.csv`, `<name>-ibom.html` (InteractiveHtmlBom), `order-digikey.csv`, `order-mouser.csv` (quantity × `--boards` or field `Order Qty`, DNP parts and parts with `Order Qty` = 0 left out, lines with the same manufacturer and MPN merged).
- Order files: upload in the DigiKey BOM Manager and the Mouser BOM Tool. Check the column mapping on the first upload of a project. DigiKey columns: Digi-Key Part Number, Quantity, Customer Reference (references separated by spaces). The file has no MPN column and no field with a comma.
- Run `check` and `outputs` after each change to the schematic or the board, and commit the outputs with the source files.

## README
Update the README in the same commit as the outputs. Contents:
- Short description.
- Render: `outputs/docs/<name>-top.png`. If a case exists: exploded view of the case (see exploded-render).
- Links: schematic PDF, board PDF, interactive BOM, BOM CSV, order files, Gerber archive.
- Version and date from the title block.
- Interfaces: connectors with pin-out, power input (voltage, current), signals (level, direction, frequency range).
- Power budget: table with one line per rail: source, loads, typical and maximum current, source rating, margin.
- Design notes: decisions and their reasons, calculations, known limits.
- Unit price: sum of the order-file lines at 1 board and at `--boards` boards, with the distributor and the date of the prices.

## Release
When a board goes to manufacturing:
1. `check` without issues, outputs and README up to date and committed.
2. Ask the user to confirm the version and the date in the title block.
3. Tag `pcb-v<rev>-<date>`, then `gh release create pcb-v<rev>-<date> --title "<title> PCB v<rev> (<date>)"` with the Gerber archive, the position file, the PDFs and the BOM files as assets. Ask the user before the push and the release.
