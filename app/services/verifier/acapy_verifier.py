from abc import ABC, abstractmethod

from aries_cloudcontroller import AcaPyClient

from app.models.verifier import (
    AcceptProofRequest,
    CreateProofRequest,
    CredPrecis,
    RejectProofRequest,
    SendProofRequest,
)
from shared.models.presentation_exchange import PresentationExchange


class Verifier(ABC):
    """Abstract proof interface"""

    @classmethod
    @abstractmethod
    async def create_proof_request(
        cls,
        controller: AcaPyClient,
        create_proof_request: CreateProofRequest,
    ) -> PresentationExchange:
        """
        Create proof request

        Parameters:
        -----------
        controller: AcaPyClient
            The aries_cloudcontroller object
        create_proof_request: CreateProofRequest
            The proof request object

        Returns:
        --------
        exchange_record: PresentationExchange
            The proof exchange record
        """

    @classmethod
    @abstractmethod
    async def send_proof_request(
        cls,
        controller: AcaPyClient,
        send_proof_request: SendProofRequest,
    ) -> PresentationExchange:
        """
        Request proof from a connection ID.

        Parameters:
        -----------
        controller: AcaPyClient
            The aries_cloudcontroller object
        send_proof_request: SendProofRequest
            The proof request object

        Returns:
        --------
        exchange_record: PresentationExchange
            The proof exchange record
        """

    @classmethod
    @abstractmethod
    async def accept_proof_request(
        cls, controller: AcaPyClient, accept_proof_request: AcceptProofRequest
    ) -> PresentationExchange:
        """
        Accept proof request

        Parameters:
        -----------
        controller: AcaPyClient
            The aries_cloudcontroller object
        accept_proof_request: AcceptProofRequest
            The proof request object

        Returns:
        --------
        exchange_record: PresentationExchange
            The proof exchange record
        """

    @classmethod
    @abstractmethod
    async def reject_proof_request(
        cls, controller: AcaPyClient, reject_proof_request: RejectProofRequest
    ) -> None:
        """
        Reject proof request

        Parameters:
        -----------
        controller: AcaPyClient
            The aries_cloudcontroller object
        reject_proof_request: RejectProofRequest
            The proof request object

        Returns:
        --------
        None
            Returns None on successful request rejection.
        """

    @classmethod
    @abstractmethod
    async def get_proof_records(
        cls,
        controller: AcaPyClient,
        limit: int | None = None,
        offset: int | None = None,
        order_by: str | None = "id",
        descending: bool = True,
        connection_id: str | None = None,
        role: str | None = None,
        state: str | None = None,
        thread_id: str | None = None,
    ) -> list[PresentationExchange]:
        """Get all proof records.

        Parameters
        ----------
        controller: AcaPyClient
            The aries_cloudcontroller object used to interact with the ACA-Py API.
        limit: Optional[int]
            The maximum number of records to return. If not specified, returns maximum possible (10'000).
        offset: Optional[int]
            The starting index from where to return records. Useful for pagination.
        order_by: Optional[str]
            The field by which to order the results. Default is "id".
        descending: bool
            If True, the results are sorted in descending order. Default is True (descending order).
        connection_id: Optional[str]
            Filter by the connection ID associated with the proof records.
        role: Optional[str]
            Filter by the role of the agent in the proof exchange (e.g., "prover", "verifier").
        state: Optional[str]
            Filter by the state of the proof exchange (e.g., "request_sent", "presentation_acked").
        thread_id: Optional[str]
            Filter by the thread ID associated with the proof exchange.

        Returns:
        --------
        List[PresentationExchange]
            A list of presentation exchange records.
        """

    @classmethod
    @abstractmethod
    async def get_proof_record(
        cls, controller: AcaPyClient, proof_id: str
    ) -> PresentationExchange:
        """
        Get a specific proof record

        Parameters:
        -----------
        controller: AcaPyClient
            The aries_cloudcontroller object
        proof_id: str
            The presentation exchange ID

        Returns:
        --------
        PresentationExchange
            A presentation exchange records
        """

    @classmethod
    @abstractmethod
    async def delete_proof(cls, controller: AcaPyClient, proof_id: str) -> None:
        """
        Delete proof request

        Parameters:
        -----------
        controller: AcaPyClient
            The aries_cloudcontroller object
        proof_id: str
            The proof record exchange id

        Returns:
        --------
        None
            Returns None on successful record deletion.
        """

    @classmethod
    @abstractmethod
    async def get_credentials_by_proof_id(
        cls, controller: AcaPyClient, proof_id: str
    ) -> list[CredPrecis]:
        """Retrieve the credentials for a proof

        Parameters
        ----------
        controller: AcaPyClient
            The aries_cloudcontroller object
        proof_id: str
            The proof id

        Returns:
        --------
        [CredPrecis]
            A list of presentation exchange records
        """
