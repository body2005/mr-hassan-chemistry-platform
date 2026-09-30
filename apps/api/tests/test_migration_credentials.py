from alembic.config import Config
from sqlalchemy.engine import make_url


def test_alembic_preserves_url_encoded_random_password():
    url = "postgresql+psycopg://lms:a%2Bb%2Fc%25d@postgres/lms"
    config = Config()
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    assert config.get_main_option("sqlalchemy.url") == url
    assert make_url(config.get_main_option("sqlalchemy.url")).password == "a+b/c%d"
