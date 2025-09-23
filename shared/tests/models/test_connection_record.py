from aries_cloudcontroller import ConnRecord

from shared.models.connection_record import (
    Connection,
    InvitationMode,
    Protocol,
    Role,
    State,
    _truncate_did_peer_4,
    _validate_field,
    conn_record_to_connection,
)


def test_connection_model():
    # Test creating a Connection instance
    connection = Connection(
        alias="Alice Agent",
        connection_id="conn-id-123",
        connection_protocol="didexchange/1.0",
        created_at="2023-01-01T00:00:00Z",
        error_msg=None,
        invitation_key="invitation-key-123",
        invitation_mode="once",
        invitation_msg_id="invitation-msg-id-123",
        my_did="did:peer:4zQmWbS8XogSNphdDuq8dJeg3z7u72k1hFb5v1b98uzUVbTu:z3qDm8hHtipyThg5iZH9rj...LfE",
        state="completed",
        their_did="did:peer:4zQmd8CpeFPci817KDsbSAKWcXAE2mjvCQSasRewvbSF54Bd:z2M...kjm",
        their_label="Bob Agent",
        their_public_did="did:cheqd:testnet:123",
        their_role="invitee",
        updated_at="2023-01-01T01:00:00Z",
    )

    assert connection.alias == "Alice Agent"
    assert connection.connection_id == "conn-id-123"
    assert connection.connection_protocol == "didexchange/1.0"
    assert connection.created_at == "2023-01-01T00:00:00Z"
    assert connection.error_msg is None
    assert connection.invitation_key == "invitation-key-123"
    assert connection.invitation_mode == "once"
    assert connection.invitation_msg_id == "invitation-msg-id-123"
    assert (
        connection.my_did
        == "did:peer:4zQmWbS8XogSNphdDuq8dJeg3z7u72k1hFb5v1b98uzUVbTu:z3qDm8hHtipyThg5iZH9rj...LfE"
    )
    assert connection.state == "completed"
    assert (
        connection.their_did
        == "did:peer:4zQmd8CpeFPci817KDsbSAKWcXAE2mjvCQSasRewvbSF54Bd:z2M...kjm"
    )
    assert connection.their_label == "Bob Agent"
    assert connection.their_public_did == "did:cheqd:testnet:123"
    assert connection.their_role == "invitee"
    assert connection.updated_at == "2023-01-01T01:00:00Z"


def test_conn_record_to_connection():
    # Mock a ConnRecord with valid base58 invitation key
    record = ConnRecord(
        alias="Test Agent",
        connection_id="conn-id-456",
        connection_protocol="didexchange/1.1",
        created_at="2023-02-01T00:00:00Z",
        error_msg=None,
        invitation_key="H3C2AVvLMv6gmMNam3uVAjZpfkcJCwDwnZn6z3wXmqPV",
        invitation_mode="multi",
        invitation_msg_id="invitation-msg-id-456",
        my_did="did:peer:4zQmWbS8XogSNphdDuq8dJeg3z7u72k1hFb5v1b98uzUVbTu:z3qDm8hHPpgti6CKpyThg5iZH9rj...LfE",
        rfc23_state="completed",
        their_did="did:peer:4zQmd8CpeFPci817KDsbSAKWcXAE2mjvCQSasRewvbSF54Bd:z2M...kjm",
        their_label="Remote Agent",
        their_public_did="did:cheqd:mainnet:456",
        their_role="inviter",
        updated_at="2023-02-01T01:00:00Z",
    )

    connection = conn_record_to_connection(record)

    assert connection.alias == "Test Agent"
    assert connection.connection_id == "conn-id-456"
    assert connection.connection_protocol == "didexchange/1.1"
    assert connection.created_at == "2023-02-01T00:00:00Z"
    assert connection.error_msg is None
    assert connection.invitation_key == "H3C2AVvLMv6gmMNam3uVAjZpfkcJCwDwnZn6z3wXmqPV"
    assert connection.invitation_mode == "multi"
    assert connection.invitation_msg_id == "invitation-msg-id-456"
    # DIDs should be truncated to short form
    assert (
        connection.my_did == "did:peer:4zQmWbS8XogSNphdDuq8dJeg3z7u72k1hFb5v1b98uzUVbTu"
    )
    assert connection.state == "completed"
    assert (
        connection.their_did
        == "did:peer:4zQmd8CpeFPci817KDsbSAKWcXAE2mjvCQSasRewvbSF54Bd"
    )
    assert connection.their_label == "Remote Agent"
    assert connection.their_public_did == "did:cheqd:mainnet:456"
    assert connection.their_role == "inviter"
    assert connection.updated_at == "2023-02-01T01:00:00Z"


def test_conn_record_to_connection_with_invalid_fields():
    # Create a mock object to test validation logic without Pydantic interference
    class MockConnRecord:
        def __init__(self) -> None:
            self.alias = "Test Agent"
            self.connection_id = "conn-id-789"
            self.connection_protocol = "invalid_protocol"  # Invalid protocol
            self.created_at = "2023-03-01T00:00:00Z"
            self.error_msg = None
            self.invitation_key = None
            self.invitation_mode = "invalid_mode"  # Invalid invitation mode
            self.invitation_msg_id = None
            self.my_did = "did:sov:123456"  # Non-peer:4 DID
            self.rfc23_state = "invalid_state"  # Invalid state
            self.their_did = "did:key:987654"  # Non-peer:4 DID
            self.their_label = None
            self.their_public_did = None
            self.their_role = "invalid_role"  # Invalid role
            self.updated_at = "2023-03-01T01:00:00Z"

    record = MockConnRecord()
    connection = conn_record_to_connection(record)

    # Invalid fields should be None due to validation
    assert connection.connection_protocol is None
    assert connection.invitation_mode is None
    assert connection.state is None
    assert connection.their_role is None
    # Valid DIDs should pass through unchanged
    assert connection.my_did == "did:sov:123456"
    assert connection.their_did == "did:key:987654"
    # Other fields should be preserved
    assert connection.alias == "Test Agent"
    assert connection.connection_id == "conn-id-789"


def test_truncate_did_peer_4():
    # Test truncating did:peer:4 DIDs
    long_did = "did:peer:4zQmWbS8XogSNphdDuq8dJeg3z7u72k1hFb5v1b98uzUVbTu:z3qDm8hHPpgti6CKpyThg5iZH9rj...LfE"
    short_did = _truncate_did_peer_4(long_did)
    assert short_did == "did:peer:4zQmWbS8XogSNphdDuq8dJeg3z7u72k1hFb5v1b98uzUVbTu"

    # Test with minimal did:peer:4
    minimal_did = "did:peer:4zQmWbS8XogSNphdDuq8dJeg3z7u72k1hFb5v1b98uzUVbTu"
    result = _truncate_did_peer_4(minimal_did)
    assert result == "did:peer:4zQmWbS8XogSNphdDuq8dJeg3z7u72k1hFb5v1b98uzUVbTu"

    # Test with non-peer:4 DID
    other_did = "did:sov:123456"
    result = _truncate_did_peer_4(other_did)
    assert result == "did:sov:123456"

    # Test with did:peer but not version 4
    peer_v2_did = "did:peer:2:abc123"
    result = _truncate_did_peer_4(peer_v2_did)
    assert result == "did:peer:2:abc123"

    # Test with None
    result = _truncate_did_peer_4(None)
    assert result is None

    # Test with empty string
    result = _truncate_did_peer_4("")
    assert result == ""


def test_validate_field():
    # Test valid protocol
    result = _validate_field("didexchange/1.0", Protocol, "protocol")
    assert result == "didexchange/1.0"

    # Test invalid protocol
    result = _validate_field("invalid_protocol", Protocol, "protocol")
    assert result is None

    # Test valid invitation mode
    result = _validate_field("once", InvitationMode, "invitation_mode")
    assert result == "once"

    # Test invalid invitation mode
    result = _validate_field("invalid_mode", InvitationMode, "invitation_mode")
    assert result is None

    # Test valid role
    result = _validate_field("inviter", Role, "role")
    assert result == "inviter"

    # Test invalid role
    result = _validate_field("invalid_role", Role, "role")
    assert result is None

    # Test valid state
    result = _validate_field("completed", State, "state")
    assert result == "completed"

    # Test invalid state
    result = _validate_field("invalid_state", State, "state")
    assert result is None

    # Test None value
    result = _validate_field(None, Protocol, "protocol")
    assert result is None


def test_conn_record_to_connection_minimal():
    # Test with minimal ConnRecord (only required fields)
    record = ConnRecord(connection_id="minimal-conn-id")

    connection = conn_record_to_connection(record)

    # Required field should be present
    assert connection.connection_id == "minimal-conn-id"
    # All other fields should be None for minimal record
    assert connection.alias is None
    assert connection.connection_protocol is None
    assert connection.created_at is None
    assert connection.error_msg is None
    assert connection.invitation_key is None
    assert connection.invitation_mode is None
    assert connection.invitation_msg_id is None
    assert connection.my_did is None
    assert connection.state is None
    assert connection.their_did is None
    assert connection.their_label is None
    assert connection.their_public_did is None
    assert connection.their_role is None
    assert connection.updated_at is None


def test_conn_record_to_connection_all_protocols():
    # Test all valid protocols
    for protocol in ["didexchange/1.0", "didexchange/1.1"]:
        record = ConnRecord(connection_id="test-conn-id", connection_protocol=protocol)
        connection = conn_record_to_connection(record)
        assert connection.connection_protocol == protocol


def test_conn_record_to_connection_all_invitation_modes():
    # Test all valid invitation modes
    for mode in ["once", "multi", "static"]:
        record = ConnRecord(connection_id="test-conn-id", invitation_mode=mode)
        connection = conn_record_to_connection(record)
        assert connection.invitation_mode == mode


def test_conn_record_to_connection_all_roles():
    # Test all valid roles
    for role in ["invitee", "requester", "inviter", "responder"]:
        record = ConnRecord(connection_id="test-conn-id", their_role=role)
        connection = conn_record_to_connection(record)
        assert connection.their_role == role


def test_conn_record_to_connection_all_states():
    # Test all valid states
    for state in [
        "start",
        "invitation-sent",
        "request-sent",
        "response-received",
        "completed",
        "abandoned",
    ]:
        record = ConnRecord(connection_id="test-conn-id", rfc23_state=state)
        connection = conn_record_to_connection(record)
        assert connection.state == state
