import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

REPOSITORY = 'josegustavo14/cloud-sync-NAS'
_cache = {'checked': None, 'value': None}


def _version(value):
    match = re.search(r'(?<!\d)v?(\d+)\.(\d+)\.(\d+)', value or '')
    return tuple(map(int, match.groups())) if match else None


def latest(current):
    now = datetime.now(timezone.utc)
    if _cache['checked'] and now - _cache['checked'] < timedelta(minutes=10):
        return _cache['value']
    result = {'current': current, 'latest': None, 'update_available': False, 'release_url': f'https://github.com/{REPOSITORY}/releases', 'checked_at': now.isoformat(), 'available': False}
    try:
        request = urllib.request.Request(f'https://api.github.com/repos/{REPOSITORY}/releases/latest', headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'personal-cloud-sync'})
        with urllib.request.urlopen(request, timeout=4) as response:
            payload = json.load(response)
        tag = payload.get('tag_name', '')
        current_version, latest_version = _version(current), _version(tag)
        result.update({'latest': tag or None, 'update_available': bool(current_version and latest_version and latest_version > current_version), 'release_url': payload.get('html_url') or result['release_url'], 'available': bool(tag)})
    except (OSError, urllib.error.URLError, ValueError, KeyError):
        pass
    _cache.update(checked=now, value=result)
    return result
