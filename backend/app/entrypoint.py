"""Prepare a newly mounted NAS volume, then drop root before starting the API."""
import os
from pathlib import Path


def main():
    if os.geteuid() == 0:
        root = Path(os.environ.get('PCS_ROOT', '/DATA/CloudSync'))
        if not root.is_absolute() or root == Path('/'):
            raise RuntimeError('PCS_ROOT must be an absolute dedicated data directory')
        for name in ('', 'data', 'data/.parts', 'database', 'config', 'logs'):
            path = root / name
            if path.is_symlink():
                raise RuntimeError('Persistent directories must not be symlinks')
            path.mkdir(parents=True, exist_ok=True)
            os.chown(path, 1000, 1000)
        os.setgroups([])
        os.setgid(1000)
        os.setuid(1000)
    os.execvp('uvicorn', ['uvicorn', 'app.main:create_app', '--factory', '--host',
                         '0.0.0.0', '--port', '8080', '--workers', '1', '--no-access-log'])


if __name__ == '__main__':
    main()
