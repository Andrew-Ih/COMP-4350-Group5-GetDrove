"""Gateway factory for payment use cases; health needs no Stripe key."""

from stripe import HTTPClient, StripeClient

from payments.adapters.stripe_gateway import StripePaymentGateway
from payments.application.ports import PaymentGatewayPort
from payments.infrastructure.settings import Settings


def create_payment_gateway(
    settings: Settings, http_client: HTTPClient | None = None
) -> PaymentGatewayPort:
    if settings.stripe_secret_key is None:
        raise ValueError("PAYMENTS_STRIPE_SECRET_KEY is required for Stripe operations")
    return StripePaymentGateway(
        StripeClient(
            settings.stripe_secret_key.get_secret_value(),
            base_addresses={"api": settings.stripe_api_base},
            max_network_retries=2,
            http_client=http_client,
        )
    )
