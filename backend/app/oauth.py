"""Small, allow-listed adapter around rclone's non-interactive config protocol."""
import json
import os
import re
import subprocess
import threading
from pathlib import Path

ALLOWED = {'google_drive': 'drive', 'onedrive': 'onedrive', 'dropbox': 'dropbox'}
NAME = re.compile(r'^[A-Za-z0-9_-]{1,48}$')


class OAuthError(Exception):
    pass


class OAuthWizard:
    def __init__(self, config):
        self.config = Path(config)
        self.sessions = {}
        self.lock = threading.Lock()

    def _run(self, args):
        process = subprocess.run(['rclone', *args, '--config', str(self.config), '--non-interactive'],
                                 capture_output=True, text=True, timeout=120, env={**os.environ, 'RCLONE_CONFIG_PASS': os.getenv('RCLONE_CONFIG_PASS', '')})
        if process.returncode:
            raise OAuthError('rclone não conseguiu continuar a configuração; revise o provider e tente novamente')
        try:
            return json.loads(process.stdout)
        except (json.JSONDecodeError, TypeError):
            raise OAuthError('rclone retornou uma resposta de configuração inválida') from None

    def start(self, provider, name):
        if provider not in ALLOWED or not NAME.fullmatch(name):
            raise OAuthError('Provider ou nome de conta inválido')
        result = self._run(['config', 'create', name, ALLOWED[provider]])
        session = os.urandom(18).hex()
        with self.lock:
            self.sessions[session] = (name, provider, result.get('State', ''), result)
        return self.public(session, result)

    def continue_(self, session, result):
        with self.lock:
            current = self.sessions.get(session)
        if not current:
            raise OAuthError('Sessão de autorização expirada; comece novamente')
        name, provider, state, _ = current
        if not isinstance(result, str) or len(result) > 8192:
            raise OAuthError('Resposta inválida')
        output = self._run(['config', 'create', name, ALLOWED[provider], '--continue', '--state', state, '--result', result])
        if output.get('State'):
            with self.lock:
                self.sessions[session] = (name, provider, output['State'], output)
            return self.public(session, output)
        with self.lock:
            self.sessions.pop(session, None)
        return {'complete': True, 'remote': f'{name}:', 'provider': provider}

    @staticmethod
    def public(session, output):
        option = output.get('Option') or {}
        return {'complete': False, 'session': session, 'state': output.get('State', ''),
                'question': {'name': option.get('Name'), 'help': option.get('Help'),
                             'type': option.get('Type'), 'default': option.get('Default'),
                             'required': option.get('Required', False), 'examples': option.get('Examples', [])},
                'error': output.get('Error', '')}
