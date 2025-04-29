from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from nats import NATS
from nats.errors import TimeoutError
from nats.js import JetStreamContext
from pydantic import ValidationError

from shared.services.nats_jetstream_publish import (
    Event,
    EventFactory,
    NatsJetstreamPublish,
    SchemaEventPayload,
    TenantEventPayload,
)


def test_event_factory_create_tenant_event():
    # Valid Tenant Event
    event = EventFactory.create_tenant_event(
        subject="tenant.subject",
        wallet_id="wallet123",
        wallet_label="Test Wallet",
        wallet_name="Test Wallet Name",
        roles=["admin", "user"],
        state="active",
        group_id="group123",
        topic="tenant.created",
        image_url="https://example.com/image.png",
        created_at="2025-04-23T07:29:08.401017Z",
        updated_at="2025-04-23T07:29:08.401017Z",
    )
    assert event.subject == "tenant.subject"
    assert event.payload.wallet_id == "wallet123"
    assert event.payload.wallet_label == "Test Wallet"
    assert event.payload.wallet_name == "Test Wallet Name"
    assert event.payload.roles == ["admin", "user"]
    assert event.payload.state == "active"
    assert event.payload.group_id == "group123"
    assert event.payload.topic == "tenant.created"
    assert event.payload.image_url == "https://example.com/image.png"
    assert event.payload.created_at == "2025-04-23T07:29:08.401017Z"
    assert event.payload.updated_at == "2025-04-23T07:29:08.401017Z"


def test_event_factory_create_schema_event():
    # Valid Schema Event
    event = EventFactory.create_schema_event(
        subject="schema.subject",
        schema_id="schema123",
        name="Test Schema",
        version="1.0",
        attributes=["attr1", "attr2"],
        wallet_label="Test Wallet",
        state="active",
        topic="schema.created",
        created_at="2025-04-23T07:29:08.401017Z",
        updated_at="2025-04-23T07:29:08.401017Z",
    )
    assert event.subject == "schema.subject"
    assert event.payload.schema_id == "schema123"
    assert event.payload.name == "Test Schema"
    assert event.payload.version == "1.0"
    assert event.payload.attributes == ["attr1", "attr2"]
    assert event.payload.wallet_label == "Test Wallet"
    assert event.payload.state == "active"
    assert event.payload.topic == "schema.created"
    assert event.payload.created_at == "2025-04-23T07:29:08.401017Z"
    assert event.payload.updated_at == "2025-04-23T07:29:08.401017Z"


def test_tenant_event_payload():
    # Valid TenantEventPayload
    TenantEventPayload(
        wallet_id="wallet123",
        wallet_label="Test Wallet",
        wallet_name="Test Wallet Name",
        roles=["admin", "user"],
        image_url="https://example.com/image.png",
        group_id="group123",
        topic="tenant.created",
        state="active",
        created_at="2025-04-23T07:29:08.401017Z",
        updated_at="2025-04-23T07:29:08.401017Z",
    )

    # Invalid TenantEventPayload (missing required field)
    with pytest.raises(ValidationError):
        TenantEventPayload(
            wallet_id="wallet123",
            wallet_label="Test Wallet",
            # Missing required field `wallet_name`
            roles=["admin", "user"],
            image_url="https://example.com/image.png",
            group_id="group123",
            topic="tenant.created",
            state="active",
            created_at="2025-04-23T07:29:08.401017Z",
            updated_at="2025-04-23T07:29:08.401017Z",
        )


def test_schema_event_payload():
    # Valid SchemaEventPayload
    SchemaEventPayload(
        schema_id="schema123",
        name="Test Schema",
        version="1.0",
        attributes=["attr1", "attr2"],
        topic="schema.created",
        state="active",
        wallet_label="Test Wallet",
        created_at="2025-04-23T07:29:08.401017Z",
        updated_at="2025-04-23T07:29:08.401017Z",
    )

    # Invalid SchemaEventPayload (missing required field)
    with pytest.raises(ValidationError):
        SchemaEventPayload(
            schema_id="schema123",
            name="Test Schema",
            # Missing required field `version`
            attributes=["attr1", "attr2"],
            topic="schema.created",
            state="active",
            wallet_label="Test Wallet",
            created_at="2025-04-23T07:29:08.401017Z",
            updated_at="2025-04-23T07:29:08.401017Z",
        )


def test_event_model():
    # Valid Event with TenantEventPayload
    tenant_payload = TenantEventPayload(
        wallet_id="wallet123",
        wallet_label="Test Wallet",
        wallet_name="Test Wallet Name",
        roles=["admin", "user"],
        image_url="https://example.com/image.png",
        group_id="group123",
        topic="tenant.created",
        state="active",
        created_at="2025-04-23T07:29:08.401017Z",
        updated_at="2025-04-23T07:29:08.401017Z",
    )
    Event(subject="tenant.subject", payload=tenant_payload)

    # Valid Event with SchemaEventPayload
    schema_payload = SchemaEventPayload(
        schema_id="schema123",
        name="Test Schema",
        version="1.0",
        attributes=["attr1", "attr2"],
        topic="schema.created",
        state="active",
        wallet_label="Test Wallet",
        created_at="2025-04-23T07:29:08.401017Z",
        updated_at="2025-04-23T07:29:08.401017Z",
    )
    Event(subject="schema.subject", payload=schema_payload)

    # Invalid Event (missing required field)
    with pytest.raises(ValidationError):
        Event(
            # Missing required field `subject`
            payload=tenant_payload,
        )


def test_event_factory_create_tenant_event_without_timestamps():
    # Tenant Event without created_at and updated_at
    event = EventFactory.create_tenant_event(
        subject="tenant.subject",
        wallet_id="wallet123",
        wallet_label="Test Wallet",
        wallet_name="Test Wallet Name",
        roles=["admin", "user"],
        state="active",
        group_id="group123",
        topic="tenant.created",
        image_url="https://example.com/image.png",
    )
    assert event.subject == "tenant.subject"
    assert event.payload.created_at is not None
    assert event.payload.updated_at == event.payload.created_at


def test_event_factory_create_schema_event_without_timestamps():
    # Schema Event without created_at and updated_at
    event = EventFactory.create_schema_event(
        subject="schema.subject",
        schema_id="schema123",
        name="Test Schema",
        version="1.0",
        attributes=["attr1", "attr2"],
        wallet_label="Test Wallet",
        state="active",
        topic="schema.created",
    )
    assert event.subject == "schema.subject"
    assert event.payload.created_at is not None
    assert event.payload.updated_at == event.payload.created_at


@pytest.fixture
async def mock_nats_client():
    with patch("nats.connect") as mock_connect:
        mock_nats = AsyncMock(spec=NATS)
        mock_jetstream = AsyncMock(spec=JetStreamContext)
        mock_nats.jetstream.return_value = mock_jetstream
        mock_connect.return_value = mock_nats
        yield mock_jetstream


@pytest.mark.anyio
async def test_nats_jetstream_publish_success(mock_nats_client):

    # Create NatsJetstreamPublish instance
    publisher = NatsJetstreamPublish(jetstream=mock_nats_client)

    # Mock logger
    mock_logger = MagicMock()

    # Create a sample event
    event = EventFactory.create_tenant_event(
        subject="tenant.subject",
        wallet_id="wallet123",
        wallet_label="Test Wallet",
        wallet_name="Test Wallet Name",
        roles=["admin", "user"],
        state="active",
        group_id="group123",
        topic="tenant.created",
        image_url="https://example.com/image.png",
    )

    # Call the publish method
    await publisher.publish(logger=mock_logger, event=event)


@pytest.mark.anyio
async def test_nats_jetstream_publish_duplicate(mock_nats_client):

    # Create NatsJetstreamPublish instance
    publisher = NatsJetstreamPublish(jetstream=mock_nats_client)

    # Mock logger
    mock_logger = MagicMock()

    # Create a sample event
    event = EventFactory.create_tenant_event(
        subject="tenant.subject",
        wallet_id="wallet123",
        wallet_label="Test Wallet",
        wallet_name="Test Wallet Name",
        roles=["admin", "user"],
        state="active",
        group_id="group123",
        topic="tenant.created",
        image_url="https://example.com/image.png",
    )

    # Call the publish method
    await publisher.publish(logger=mock_logger, event=event)


@pytest.mark.anyio
async def test_nats_jetstream_publish_failure(mock_nats_client):

    # Create NatsJetstreamPublish instance
    publisher = AsyncMock(spec=NatsJetstreamPublish)
    publisher.publish.side_effect = TimeoutError()

    # Mock logger
    mock_logger = MagicMock()

    # Create a sample event
    event = EventFactory.create_tenant_event(
        subject="tenant.subject",
        wallet_id="wallet123",
        wallet_label="Test Wallet",
        wallet_name="Test Wallet Name",
        roles=["admin", "user"],
        state="active",
        group_id="group123",
        topic="tenant.created",
        image_url="https://example.com/image.png",
    )

    # Call the publish method and expect an exception
    with pytest.raises(TimeoutError):
        await publisher.publish(logger=mock_logger, event=event)
