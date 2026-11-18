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


def test_riders_are_reminded_30_minutes_before_departure_by_default() -> None:
    assert Settings().reminder_lead_minutes == 30


def test_the_reminder_lead_time_can_be_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NOTIFICATIONS_REMINDER_LEAD_MINUTES", "45")

    assert Settings().reminder_lead_minutes == 45


@pytest.mark.parametrize("minutes", ["0", "-5", "1441"])
def test_the_reminder_lead_time_must_be_sensible(
    monkeypatch: pytest.MonkeyPatch, minutes: str
) -> None:
    monkeypatch.setenv("NOTIFICATIONS_REMINDER_LEAD_MINUTES", minutes)

    with pytest.raises(ValueError, match="reminder_lead_minutes"):
        Settings()


def test_reminders_are_looked_for_every_30_seconds_by_default() -> None:
    assert Settings().reminder_interval_seconds == 30


def test_no_address_is_skipped_by_default() -> None:
    """Locally Mailpit catches every email, demo accounts' included (#415)."""
    assert Settings().email_skip_patterns == []


def test_the_skip_list_is_read_as_production_sets_it(monkeypatch: pytest.MonkeyPatch) -> None:
    # Exactly as infra/docker-compose.prod.yml writes it.
    monkeypatch.setenv("NOTIFICATIONS_EMAIL_SKIP_PATTERNS", '["getdrove.demo.*@myumanitoba.ca"]')

    assert Settings().email_skip_patterns == ["getdrove.demo.*@myumanitoba.ca"]
