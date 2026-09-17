import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    root: Path
    source_root: Path
    token: str
    web_root: Path = Path('/app/web')

    @classmethod
    def from_env(cls):
        return cls(Path(os.getenv('PCS_ROOT', '/DATA/CloudSync')).resolve(),
                   Path(os.getenv('PCS_SOURCE_ROOT', '/sources')).resolve(),
                   os.getenv('PCS_TOKEN', ''),
                   Path(os.getenv('PCS_WEB_ROOT', '/app/web')))

    def prepare(self):
        if len(self.token) < 32:
            raise RuntimeError('PCS_TOKEN must contain at least 32 characters')
        if self.root == self.source_root or self.root.is_relative_to(self.source_root) or self.source_root.is_relative_to(self.root):
            raise RuntimeError('Source and destination roots must not overlap')
        for name in ('data', 'data/.parts', 'database', 'config', 'logs'):
            (self.root / name).mkdir(parents=True, exist_ok=True)
        for name in ('database', 'config', 'logs'):
            (self.root / name).chmod(0o700)
