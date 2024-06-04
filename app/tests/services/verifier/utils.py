from aries_cloudcontroller import (
    AttachDecorator,
    AttachDecoratorData,
    DIFProofRequest,
    IndyPresSpec,
    IndyProof,
    IndyProofProof,
    IndyProofReqAttrSpec,
    IndyProofRequestedProof,
    IndyProofRequestNonRevoked,
    IndyRequestedCredsRequestedAttr,
    IndyRequestedCredsRequestedPred,
    PresentationDefinition,
    V10PresentationExchange,
    V20Pres,
    V20PresExRecord,
    V20PresExRecordByFormat,
    V20PresFormat,
    V20PresProposal,
)

from app.models.verifier import IndyProofRequest

indy_proof = IndyProof(
    identifiers=[],
    proof=IndyProofProof(aggregated_proof=None, proofs=None),
    requested_proof=IndyProofRequestedProof(),
)

indy_proof_request_empty = IndyProofRequest(
    non_revoked=None,
    nonce=None,
    requested_attributes={},
    requested_predicates={},
)

v10_presentation_exchange_records = [
    V10PresentationExchange(
        auto_present=False,
        connection_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
        created_at="2021-09-15 13:49:47Z",
        error_msg=None,
        initiator="self",
        presentation=indy_proof,
        presentation_exchange_id="dabc8f4e-164a-410f-bd10-471b090f65a5",
        presentation_proposal_dict=None,
        presentation_request=indy_proof_request_empty,
        presentation_request_dict=None,
        role="prover",
        state="proposal_sent",
        thread_id=None,
        trace=False,
        updated_at=None,
        verified="false",
    ),
]


def sample_indy_proof_request(restrictions=None) -> IndyProofRequest:
    return IndyProofRequest(
        name="string",
        non_revoked=IndyProofRequestNonRevoked(var_from=0, to=20),
        nonce="12345",
        requested_attributes={
            "0_speed_uuid": IndyProofReqAttrSpec(
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
        by_format=V20PresExRecordByFormat(
            pres={"indy": {"hello": "world"}},
            pres_proposal={"indy": {"hello": "world"}},
            pres_request={"indy": sample_indy_proof_request().to_dict()},
        ),
        connection_id="abc",
        created_at="2021-09-15 13:49:47Z",
        error_msg=None,
        initiator="self",
        pres=V20Pres(
            formats=[V20PresFormat(attach_id="1234", format="indy")],
            presentationsattach=[
                AttachDecorator(
                    data=AttachDecoratorData(base64="asdf"),
                )
            ],
            pres_ex_id="abcd",
            pres_proposal=V20PresProposal(
                formats=[V20PresFormat(attach_id="1234", format="indy")],
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


indy_pres_spec = IndyPresSpec(
    requested_attributes={
        "0_string_uuid": IndyRequestedCredsRequestedAttr(cred_id="0_string_uuid")
    },
    requested_predicates={
        "0_string_GE_uuid": IndyRequestedCredsRequestedPred(cred_id="0_string_GE_uuid")
    },
    self_attested_attributes={"sth": "sth_else"},
)
