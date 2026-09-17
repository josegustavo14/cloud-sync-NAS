"""Providers expose discovery and read streams only. No remote mutation API."""
import configparser
import json
import mimetypes
import os
import re
import selectors
import subprocess
import tarfile
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


class ProviderError(Exception):
    pass


class Cancelled(Exception):
    pass


@dataclass
class Entry:
    remote_id: str
    path: str
    size: int
    mime: str
    fingerprint: str
    container: str = ''
    member: str = ''


def mime(path):
    return mimetypes.guess_type(path)[0] or 'application/octet-stream'


def check(cancel):
    if cancel():
        raise Cancelled()


def stream_file(source, cancel):
    while True:
        check(cancel)
        chunk = source.read(1024 * 1024)
        if not chunk:
            break
        yield chunk


class FilesystemProvider:
    def __init__(self, root, source_root, takeout=False):
        candidate = Path(root)
        if not candidate.is_absolute():
            candidate = source_root / candidate
        self.root = candidate.resolve()
        if not self.root.is_relative_to(source_root.resolve()):
            raise ProviderError('Source must be inside PCS_SOURCE_ROOT')
        if not self.root.exists():
            raise ProviderError('Source is not mounted or does not exist')
        self.takeout = takeout

    def discover(self, cancel):
        paths = [self.root] if self.root.is_file() else self.root.rglob('*')
        for path in paths:
            check(cancel)
            if path.is_symlink() or not path.is_file():
                continue
            if not path.resolve().is_relative_to(self.root if self.root.is_dir() else self.root.parent):
                raise ProviderError('Source path escaped its root')
            name = path.name if self.root.is_file() else path.relative_to(self.root).as_posix()
            stat = path.stat()
            fingerprint = f'{stat.st_size}:{stat.st_mtime_ns}'
            if self.takeout and zipfile.is_zipfile(path):
                with zipfile.ZipFile(path) as archive:
                    for member in archive.infolist():
                        check(cancel)
                        if member.is_dir():
                            continue
                        key = f'{name}!/{member.filename}'
                        yield Entry(key, key, member.file_size, mime(member.filename),
                                    f'{fingerprint}:{member.CRC}', str(path), member.filename)
            elif self.takeout and (name.endswith('.tar') or name.endswith('.tgz') or name.endswith('.tar.gz')):
                with tarfile.open(path, 'r:*') as archive:
                    for member in archive:
                        check(cancel)
                        if member.isfile():
                            key = f'{name}!/{member.name}'
                            yield Entry(key, key, member.size, mime(member.name),
                                        f'{fingerprint}:{member.offset_data}:{member.mtime}', str(path), member.name)
            else:
                yield Entry(name, name, stat.st_size, mime(name), fingerprint, str(path))

    def chunks(self, entry, cancel):
        path = Path(entry.container)
        # No archive extraction: member names can never become destination paths.
        if entry.member and zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as archive, archive.open(entry.member) as source:
                yield from stream_file(source, cancel)
        elif entry.member:
            with tarfile.open(path, 'r:*') as archive:
                with archive.extractfile(entry.member) as source:
                    yield from stream_file(source, cancel)
        else:
            before = path.stat()
            if f'{before.st_size}:{before.st_mtime_ns}' != entry.fingerprint:
                raise ProviderError('Source changed during discovery; retry next sync')
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, 'rb') as source:
                yield from stream_file(source, cancel)
                after = os.fstat(source.fileno())
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise ProviderError('Source changed during download; retry next sync')


REMOTE_TYPES = {'google_drive': 'drive', 'onedrive': 'onedrive', 'dropbox': 'dropbox'}


def remotes(config):
    parser = configparser.RawConfigParser()
    try:
        parser.read(config)
    except configparser.Error:
        raise ProviderError('Invalid rclone configuration') from None
    return [{'name': section, 'type': parser.get(section, 'type', fallback='')}
            for section in parser.sections()
            if parser.get(section, 'type', fallback='') in REMOTE_TYPES.values()]


class RcloneProvider:
    def __init__(self, location, provider, config):
        remote, separator, folder = location.partition(':')
        if not separator or not re.fullmatch(r'[A-Za-z0-9_-]+', remote):
            raise ProviderError('Use a configured remote such as personal:folder')
        if folder.startswith('/') or '..' in PurePosixPath(folder).parts:
            raise ProviderError('Remote folder must be a relative path')
        if not any(r['name'] == remote and r['type'] == REMOTE_TYPES[provider] for r in remotes(config)):
            raise ProviderError('Remote is missing or its type does not match this provider')
        self.location = location.rstrip('/')
        self.config = config

    def command(self, operation, source):
        if operation not in ('lsjson', 'cat'):
            raise ProviderError('Operation not allowed')
        return ['rclone', operation, source, '--config', str(self.config),
                '--contimeout', '20s', '--timeout', '60s', '--retries', '3',
                '--low-level-retries', '3', '--log-level', 'ERROR']

    def discover(self, cancel):
        with tempfile.TemporaryFile() as output:
            process = subprocess.Popen(self.command('lsjson', self.location) + ['--recursive', '--files-only'],
                                       stdout=output, stderr=subprocess.DEVNULL)
            deadline = time.monotonic() + 3600
            try:
                while process.poll() is None:
                    check(cancel)
                    if time.monotonic() > deadline:
                        raise ProviderError('Discovery timed out')
                    time.sleep(0.1)
                if process.returncode:
                    raise ProviderError('Cloud discovery failed; check connection and authorization')
                output.seek(0)
                entries = json.load(output)
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait()
        for item in entries:
            check(cancel)
            path = item['Path']
            yield Entry(item.get('ID') or path, path, item['Size'], item.get('MimeType') or mime(path),
                        json.dumps([item['Size'], item.get('ModTime'), path], separators=(',', ':')))

    def chunks(self, entry, cancel):
        source = self.location + ('' if self.location.endswith(':') else '/') + entry.path
        process = subprocess.Popen(self.command('cat', source), stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL)
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                last_read = time.monotonic()
                while True:
                    check(cancel)
                    if not selector.select(timeout=0.25):
                        if time.monotonic() - last_read > 90:
                            raise ProviderError('Cloud download timed out')
                        continue
                    chunk = os.read(process.stdout.fileno(), 1024 * 1024)
                    if not chunk:
                        break
                    last_read = time.monotonic()
                    yield chunk
            if process.wait(timeout=10):
                raise ProviderError('Cloud download failed; check connection and authorization')
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()
            process.stdout.close()


def build_provider(account, settings):
    if account['provider'] in ('filesystem', 'takeout'):
        return FilesystemProvider(account['location'], settings.source_root, account['provider'] == 'takeout')
    return RcloneProvider(account['location'], account['provider'], settings.root / 'config/rclone.conf')
