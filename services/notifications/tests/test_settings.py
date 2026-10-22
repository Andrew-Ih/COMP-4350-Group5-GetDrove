"""Notifications' settings (#220): production passes the Brevo SMTP key in an environment
variable, and it must never show up when the settings are printed or logged."""

import pytest

from notifications.infrastructure.settings import Settings

KEY = "xsmtpsib-not-a-real-key"  # a made-up key, for the test


def test_the_smtp_key_is_hidden_when_printed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NOTIFICATIONS_SMTP_PASSWORD", KEY)

    settings = Settings()

    assert KEY not in repr(settings)
    assert KEY not in str(settings.model_dump())
    assert settings.smtp_password is not None
    assert settings.smtp_password.get_secret_value() == KEY


def test_production_settings_are_read_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # What infra/docker-compose.prod.yml sets.
    monkeypatch.setenv("NOTIFICATIONS_SMTP_HOST", "smtp-relay.brevo.com")
    monkeypatch.setenv("NOTIFICATIONS_SMTP_PORT", "587")
    monkeypatch.setenv("NOTIFICATIONS_SMTP_STARTTLS", "true")
    monkeypatch.setenv("NOTIFICATIONS_EMAIL_FROM", "GetDrove <team@example.com>")
    monkeypatch.setenv("NOTIFICATIONS_WEB_BASE_URL", "https://getdrove.duckdns.org")

    settings = Settings()

    assert settings.smtp_host == "smtp-relay.brevo.com"
    assert settings.smtp_port == 587
    assert settings.smtp_starttls is True
    assert settings.email_from == "GetDrove <team@example.com>"
    assert settings.web_base_url == "https://getdrove.duckdns.org"


def test_without_a_key_there_is_no_login() -> None:
    assert Settings(smtp_password=None).smtp_password is None
