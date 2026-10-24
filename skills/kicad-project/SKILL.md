---
name: kicad-project
description: KiCad PCB project workflow (project template, checks, outputs, README, parts, prices, PartsBox, release). Use for any KiCad schematic or PCB work, when outputs or the README must be updated, or when a board goes to manufacturing.
---

# KiCad project

Toolkit: `~/code/agent-toolkit` (package `hwkit`). Project template: `~/code/kicad-prj-template`. Field names, author, project identifier pattern: `lab/profile.toml` section `[kicad]`.

## Principles
- `make` runs all deterministic steps (`make help`). Use the targets; do not do their work by hand.
- Each decision has one source: the schematic, the board, a script, the README. No side files.
- The user decides the project identifier, the version (`rev`), the date, and the power budget. Ask.
- A tool that behaves unexpectedly: fix `hwkit` or write a helper. Do not record a workaround.

## Layout
- `pcb/kicad/`: source. `pcb/docs/`, `pcb/manufacturing/`, `pcb/bom/`: generated, committed. `pcb/build/`: deletable.
- `pcb/manifest.json`: hashes of the sources of the outputs. `make check` reports outputs that are not up to date.

## New project
1. Copy the template. Ask the user for the identifier and the title.
2. `make init ID=PRJ-0123 TITLE='Name'`: file names, title blocks (`rev` 0.1, date, author), README title.
3. `make fab-rules` lists the process rules; `make fab-rules PROCESS=<name>` copies one. Ask the user for the process.

## Parts
- Every BOM symbol: Manufacturer, MPN, Datasheet, DigiKey, DigiKey PN, Mouser, Mouser PN. Optional: Notes (shown in the README BOM), Order Qty. Symbols without a physical part: "Exclude from BOM".
- Symbol, footprint and 3D model: find the LCSC part number of the MPN, then `make part LCSC=C123456` (project library `parts`, STEP model embedded in the footprint, field `LCSC Part`). The search is an agent task; check that the LCSC part has the same MPN.
- Distributor fields: `make distributors` (dry run), `make distributors-write`. An `ISSUE` line (no exact match, several products, only reels) needs a decision: select the part and write the field.
- Prices: `make prices` writes `pcb/bom/prices.csv`. Run it before a release and when parts change.
- Order files: DigiKey and Mouser, by distributor part number only. The DigiKey upload is tested; the Mouser upload is not tested yet: check the column mapping on the first upload and update this skill.
- Order Qty (non-negative integer): `0` = in stock, not ordered. `N` = order max(N, quantity × boards).

## Parts in stock
`make stock` lists stock per BOM line, and candidates (same chip size and value) for lines that are not in stock. The decision is an agent task:
- Use a stock part if its specification is the same or better for the circuit (value, package, voltage, dielectric, tolerance, temperature coefficient, power). A lower rating is acceptable if the circuit does not need it.
- A better stock part in a higher price class (example: thin film for thick film): do not substitute.
- Substitution: write the stock part into the symbol fields, `Order Qty` = `0`.
- New jellybean part: `Order Qty` = a quantity worth a few USD.
- `NOTE` lines about low stock: tell the user.
- `make stock` also writes `pcb/bom/stock.csv` (on-hand quantity per exact MPN match) and `pcb/bom/order-digikey-against-stock.csv`: DigiKey order quantity minus the on-hand quantity, lines with no shortfall left out. `make outputs` writes this order file again while `stock.csv` exists. Both files are not tracked: they change with the stock.
- After the order files are final: `make partsbox-project` (ask the user first; it writes to PartsBox).

## Design recommendations
These are not checked. Apply them unless the user decides otherwise.
- Ground pour on the ground nets; ground pads connect to the pour.
- Mounting holes from library `MountingHole`, near the corners, on an integer mm grid relative to the outline corner.
- Rounded board corners: arcs between Edge.Cuts lines, or a rectangle with a corner radius.
- Silkscreen: `${TITLE} v${REVISION} ${ISSUE_DATE}`, if there is space.

## Check and outputs
- `make outputs`: PDFs, renders, Gerbers, positions, BOM, iBOM, order files, README blocks. It skips the KiCad exports if the sources did not change.
- `make check`: title blocks, outline, zones filled, process rules load, BOM fields, ERC, DRC, outputs and README up to date. Exit status 0 = no issues.
- Fill the zones in KiCad (key B) and save before the check.
- Commit the outputs and the README with the source files.

## README
- Each section holds content, `TODO`, or `N/A: <reason>`. Never delete a section. Guidance is in HTML comments.
- Generated blocks (`titleblock`, `bom`): never edit by hand.
- The power budget and the design decisions come from the user. Propose text, do not invent values.

## Release
1. `make release-check` without issues, everything committed.
2. Ask the user to confirm the version and the date in the title block.
3. Tag `pcb-v<rev>-<date>`, then `gh release create pcb-v<rev>-<date> --title "<title> PCB v<rev> (<date>)"` with the Gerber archive, the position file, the PDFs and the BOM files. Ask the user before the push and the release.
