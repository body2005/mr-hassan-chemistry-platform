"""Keep editable installation metadata aligned with Docker's exact lock."""
from pathlib import Path
from hatchling.metadata.plugin.interface import MetadataHookInterface


class LockedDependencies(MetadataHookInterface):
    def update(self, metadata):
        lines = (Path(self.root) / "requirements.lock").read_text(encoding="utf-8").splitlines()
        metadata["dependencies"] = [line.strip() for line in lines if line.strip() and not line.startswith("#")]
