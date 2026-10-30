# Lessons

General design principles for all projects, one bullet per entry, at most 100 entries (`hwkit lessons check lessons.md`).
At the limit, compress: merge, abstract, or move entries to `lessons-archive.md` (no size limit). Never delete a lesson without a copy in the archive.
Not here: tool failures and workarounds (fix the tool, or write a helper), project-specific decisions (project `DESIGN.md` or `AGENTS.md`).

## Verification

- Report a result at the level of its evidence. A slice analysis gives "slice verified", a DRC gives "DRC clean"; only a test of the built part shows that it works.
- Do not attribute a defect to a user action before the file content or a measurement shows it.
- Verify a setting in the output file (G-code header, Gerber, order file), not only in the input. Tools can apply settings differently in the GUI and on the command line.
- A tool that fails without a message is not a pass. Use a test input that must fail, and confirm that it fails.

## Electronics

- Check devices with polarity or pin order (diodes, electrolytic capacitors, transistors, connectors) against the datasheet, the symbol and the footprint.
- Order from distributors by distributor part number, not by MPN. One MPN has several packaging variants (cut tape, reel), and the upload tools select one.

## Mechanics and printing

- Clearances of printed fits are at least 2 × layer height. Printed surfaces move to layer boundaries, by up to half a layer each.
- A clearance is play. A joint that must not move needs preload (a wedge face on a flexing part, or a spring), not a smaller clearance.
- Print narrow features on the first layers slowly. Fast moves pull narrow lines from the plate.
- For a print defect, check the simple causes first (clean build plate, filament dry, correct plate type) before you change the design or the settings. A defect at some plate positions only is a sign of a contaminated plate.
- Put mating and stop surfaces of printed parts on layer boundaries.
- Print a test piece of a critical feature (snap hook, press fit) before the full part.
- Printed features are at least 2 × nozzle diameter wide, also gaps between them.
- Check each coordinate frame transform against a physical reference, for example the side of a connector. Frames can be mirrored.

## Files

- Never overwrite a file that a human can have changed after it was generated. Detect changes with hashes.
