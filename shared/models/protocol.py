from enum import Enum

from shared.exceptions.cloudapi_value_error import CloudApiValueError


class PresentProofProtocolVersion(str, Enum):
    V2 = "v2"


class IssueCredentialProtocolVersion(str, Enum):
    V2 = "v2"


def pres_id_no_version(proof_id: str) -> str:
    if proof_id.startswith("v2-"):
        return proof_id[3:]
    else:
        raise CloudApiValueError("proof_id must start with prefix `v2-`.")
