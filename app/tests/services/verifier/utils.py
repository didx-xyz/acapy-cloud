from aries_cloudcontroller import (
    AnonCredsPresentationReqAttrSpec,
    AnonCredsPresentationRequestNonRevoked,
    AnonCredsPresSpec,
    AnonCredsRequestedCredsRequestedAttr,
    AnonCredsRequestedCredsRequestedPred,
    AttachDecorator,
    AttachDecoratorData,
    DIFProofRequest,
    PresentationDefinition,
    V20Pres,
    V20PresExRecord,
    V20PresExRecordByFormat,
    V20PresFormat,
    V20PresProposal,
)

from app.models.verifier import AnonCredsPresentationRequest
from shared.tests.models.test_presentation_exchange import (
    anoncreds_pres,
    anoncreds_pres_proposal,
    anoncreds_pres_request,
)

anoncreds_by_format = V20PresExRecordByFormat(
    pres={"anoncreds": anoncreds_pres},
    pres_proposal={"anoncreds": anoncreds_pres_proposal},
    pres_request={"anoncreds": anoncreds_pres_request},
)


def sample_anoncreds_proof_request(restrictions=None) -> AnonCredsPresentationRequest:
    return AnonCredsPresentationRequest(
        name="string",
        non_revoked=AnonCredsPresentationRequestNonRevoked(),
        nonce="12345",
        requested_attributes={
            "0_speed_uuid": AnonCredsPresentationReqAttrSpec(
                name="speed",
                restrictions=restrictions,
            )
        },
        requested_predicates={},
        version="1.0",
    )


dif_proof_request = DIFProofRequest(
    options=None, presentation_definition=PresentationDefinition()
)

v20_presentation_exchange_records = [
    V20PresExRecord(
        auto_present=False,
        by_format=anoncreds_by_format,
        connection_id="abc",
        created_at="2021-09-15 13:49:47Z",
        error_msg=None,
        initiator="self",
        pres=V20Pres(
            formats=[V20PresFormat(attach_id="1234", format="anoncreds")],
            presentationsattach=[
                AttachDecorator(
                    data=AttachDecoratorData(base64="asdf"),
                )
            ],
            pres_ex_id="abcd",
            pres_proposal=V20PresProposal(
                formats=[V20PresFormat(attach_id="1234", format="anoncreds")],
                proposalsattach=[
                    AttachDecorator(
                        data=AttachDecoratorData(base64="asdf"),
                    )
                ],
            ),
        ),
        pres_request=None,
        role="prover",
        state="proposal-sent",
        thread_id=None,
        trace=None,
        updated_at=None,
        verified="false",
    ),
]


anoncreds_pres_spec = AnonCredsPresSpec(
    requested_attributes={
        "0_string_uuid": AnonCredsRequestedCredsRequestedAttr(cred_id="0_string_uuid")
    },
    requested_predicates={
        "0_string_GE_uuid": AnonCredsRequestedCredsRequestedPred(
            cred_id="0_string_GE_uuid"
        )
    },
    self_attested_attributes={"sth": "sth_else"},
)
