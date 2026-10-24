"""Output files with an overwrite guard.

Each written file gets its SHA-256 in <out_dir>/manifest.json. A file that changed afterwards (for example saved in Bambu Studio) stops write_all() before anything is written.
"""

import hashlib
import json
from pathlib import Path


class OutputGuard:
    def __init__(self, out_dir):
        self.out_dir = Path(out_dir)
        self.manifest = self.out_dir / "manifest.json"
        self.hashes = json.loads(self.manifest.read_text()) if self.manifest.exists() else {}

    @staticmethod
    def sha256(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def check(self, name):
        path = self.out_dir / name
        stored = self.hashes.get(name)
        if path.exists() and stored is not None and self.sha256(path) != stored:
            raise RuntimeError(f"{path} changed after it was written. Move the file, or remove its entry from {self.manifest.name} to permit the overwrite.")

    def record(self, name):
        self.hashes[name] = self.sha256(self.out_dir / name)
        self.manifest.write_text(json.dumps(self.hashes, indent=1, sort_keys=True) + "\n")

    def write_all(self, writers):
        """writers: {file name: function(path)}. Check all files first, then write each and record its hash."""
        self.out_dir.mkdir(parents=True, exist_ok=True)
        for name in writers:
            self.check(name)
        for name, write in writers.items():
            write(self.out_dir / name)
            self.record(name)
