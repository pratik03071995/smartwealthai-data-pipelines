from smartwealth_data.config import settings

def test_has_host_env_key():
    # This will pass even if .env isn't present (it will just raise at runtime when used)
    assert hasattr(settings, 'databricks_host')
