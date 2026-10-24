"""Bambu Studio project 3MF, presets, command-line slicing, checks and G-code analysis."""

# Per-object settings for an object with inlaid labels. The classic wall generator leaves gaps in strokes that are not a multiple of the line width. Elephant-foot compensation shrinks label and body contours separately on layer 1 and opens a gap between them.
INLAY_OBJECT_SETTINGS = {"wall_generator": "arachne", "elefant_foot_compensation": "0"}
