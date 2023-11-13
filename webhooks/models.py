from aries_cloudcontroller import (
    ConnRecord,
    IssuerCredRevRecord,
    IssuerRevRegRecord,
    OobRecord,
    V10CredentialExchange,
    V10PresentationExchange,
    V20CredExRecord,
    V20PresExRecord,
)

from shared.models.conversion import (
    conn_record_to_connection,
    credential_record_to_model_v1,
    credential_record_to_model_v2,
    presentation_record_to_model,
)
from shared.models.topics import (
    Connection,
    CredentialExchange,
    Endorsement,
    PresentationExchange,
    RedisItem,
)
from shared.models.topics.base import BasicMessage, ProblemReport


def to_basic_message_model(item: RedisItem) -> BasicMessage:
    return BasicMessage(**item.payload)


def to_connections_model(item: RedisItem) -> Connection:
    conn_record = ConnRecord(**item.payload)
    conn_record = conn_record_to_connection(connection_record=conn_record)

    return conn_record


def to_endorsement_model(item: RedisItem) -> Endorsement:
    if item.payload.get("state"):
        item.payload["state"] = item.payload["state"].replace("_", "-")
    return Endorsement(**item.payload)


def to_oob_model(item: RedisItem) -> OobRecord:
    return OobRecord(**item.payload)


def to_revocation_model(item: RedisItem) -> IssuerRevRegRecord:
    return IssuerRevRegRecord(**item.payload)


def to_issuer_cred_rev_model(item: RedisItem) -> IssuerCredRevRecord:
    return IssuerCredRevRecord(**item.payload)


def to_problem_report_model(item: RedisItem) -> ProblemReport:
    return ProblemReport(**item.payload)


def to_credential_model(item: RedisItem) -> CredentialExchange:
    # v1
    if item.acapy_topic == "issue_credential":
        cred_exchange = V10CredentialExchange(**item.payload)
        cred_model = credential_record_to_model_v1(cred_exchange)
    # v2
    elif item.acapy_topic == "issue_credential_v2_0":
        cred_exchange = V20CredExRecord(**item.payload)
        cred_model = credential_record_to_model_v2(cred_exchange)
    else:
        raise Exception(f"Unsupported credential acapy topic: `{item.acapy_topic}`.")

    return cred_model


def to_proof_model(item: RedisItem) -> PresentationExchange:
    # v1
    if item.acapy_topic == "present_proof":
        presentation_exchange = V10PresentationExchange(**item.payload)
        presentation_exchange = presentation_record_to_model(presentation_exchange)
    # v2
    elif item.acapy_topic == "present_proof_v2_0":
        presentation_exchange = V20PresExRecord(**item.payload)
        presentation_exchange = presentation_record_to_model(presentation_exchange)
    else:
        raise Exception(f"Unsupported proof acapy topic: `{item.acapy_topic}`.")

    return presentation_exchange
