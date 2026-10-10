"""Offline validation of the committed template, not a Render deployment."""
from pathlib import Path
import yaml
from app.core.config import Settings


def test_production_blueprint_settings_and_no_public_passwords():
    # QA runs mount the repository template explicitly, not a scratch copy.
    path = Path('/qa-tools/render.yaml')
    if not path.exists():
        path = Path(__file__).parents[3] / 'render.yaml'
    blueprint = yaml.safe_load(path.read_text(encoding='utf-8'))
    services = {s['name']: s for s in blueprint['services']}
    api = services['chemistry-platform-api']
    worker = services['chemistry-platform-worker']
    values = {}
    for service in (api, worker):
        assert service['branch'] == 'fix/queen-p0-handoff'
        assert service['autoDeployTrigger'] == 'off'
        env = {}
        for item in service['envVars']:
            key = item['key']
            assert key not in {'GEMINI_API_KEY', 'GROQ_API_KEY', 'OPENAI_API_KEY'}, 'Removed AI services must not require deployment credentials'
            if 'value' in item:
                env[key] = item['value']
            elif item.get('fromService', {}).get('envVarKey'):
                env[key] = values[item['fromService']['envVarKey']]
            else:
                # Synthetic secret substitutions for offline startup validation.
                env[key] = {'SECRET_KEY': 'qa-blueprint-private-placeholder',
                            'FRONTEND_ORIGINS': 'https://frontend.example.test',
                            'DATABASE_URL': 'postgresql+psycopg://qa:qa@postgres/qa',
                            'SMTP_HOST': 'smtp.example.test', 'SMTP_USER': 'qa',
                            'SMTP_FROM_EMAIL': 'qa@example.test'}.get(key, 'qa-private-placeholder')
            if 'PASSWORD' in key and not key.startswith('RESET_'):
                assert 'value' not in item, 'Passwords must be secret inputs/references'
        config = Settings(_env_file=None, **{k.lower(): v for k, v in env.items()})
        assert config.app_env == 'production' and config.smtp_port == 465 and config.secure_cookies
        assert not config.email_enabled
        if service is api:
            assert config.email_provider == 'resend'
        assert not any(item['key'].startswith('SMTP_') for item in service['envVars'])
        values.update(env)
    api_env = {e['key']: e.get('value') for e in api['envVars']}
    assert api_env['ENABLE_DEMO_ACCOUNTS'] == 'false'
    assert api_env['RESET_DEMO_PASSWORDS'] == 'false'
    assert api_env['RESET_INITIAL_TEACHER_PASSWORD'] == 'false'
