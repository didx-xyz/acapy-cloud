from abc import ABC, abstractmethod

from aries_cloudcontroller import AcaPyClient

from app.models.issuer import CredentialBase, CredentialWithConnection
from shared.models.credential_exchange import CredentialExchange


class Issuer(ABC):
    """Abstract issuer interface."""

    @classmethod
    @abstractmethod
    async def send_credential(
        cls, controller: AcaPyClient, credential: CredentialWithConnection
    ) -> CredentialExchange:
        """Create and send credential using Issue Credential protocol. Automating the entire flow.

        Parameters
        ----------
        controller: AcaPyClient
            The aries_cloudcontroller object
        credential: Credential
            Credential to issue

        Returns
        -------
        cred_ex_record:
            The credential record

        """

    @classmethod
    @abstractmethod
    async def create_offer(
        cls, controller: AcaPyClient, credential: CredentialBase
    ) -> CredentialExchange:
        """Create a credential offer not bound to a connection.

        Parameters
        ----------
        controller: AcaPyClient
            The aries_cloudcontroller object
        credential: CredentialNoConnection
            Credential offer to create

        Returns
        -------
        cred_ex_record:
            The credential record

        """

    @classmethod
    @abstractmethod
    async def request_credential(
        cls,
        controller: AcaPyClient,
        credential_exchange_id: str,
        auto_remove: bool | None = None,
    ) -> CredentialExchange:
        """Request credential

        Parameters
        ----------
        controller: AcaPyClient
            The aries_cloudcontroller object
        credential_exchange_id: str
            The credential_exchange_id of the exchange
        auto_remove: Optional[bool]
            Whether to override environment setting for auto-deleting cred ex records. Default is None (use environment
            setting)

        Returns
        -------
        cred_ex_record:
            The credential record

        """

    @classmethod
    @abstractmethod
    async def store_credential(
        cls, controller: AcaPyClient, credential_exchange_id: str
    ) -> CredentialExchange:
        """Store credential

        Parameters
        ----------
        controller: AcaPyClient
            The aries_cloudcontroller object
        credential_exchange_id:
            The credential_exchange_id of the exchange

        Returns
        -------
        cred_ex_record:
            The credential record

        """

    @classmethod
    @abstractmethod
    async def delete_credential_exchange_record(
        cls, controller: AcaPyClient, credential_exchange_id: str
    ) -> None:
        """Delete credential record.

        Parameters
        ----------
        controller: AcaPyClient
            The aries_cloudcontroller object
        credential_exchange_id:
            The credential_exchange_id of the exchange

        """

    @classmethod
    @abstractmethod
    async def get_records(
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
    ) -> list[CredentialExchange]:
        """Get a list of credential records.

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
            Filter by the connection ID associated with the credential records.
        role: Optional[str]
            Filter by the role of the agent in the credential exchange (e.g., "issuer", "holder").
        state: Optional[str]
            Filter by the state of the credential exchange (e.g., "offer_sent", "credential_issued").
        thread_id: Optional[str]
            Filter by the thread ID associated with the credential exchange.

        Returns
        -------
        List[CredentialExchange]
            A list of credential exchange records.

        """

    @classmethod
    @abstractmethod
    async def get_record(
        cls, controller: AcaPyClient, credential_exchange_id: str
    ) -> CredentialExchange:
        """Get credential record.

        Parameters
        ----------
        controller: AcaPyClient
            The aries_cloudcontroller object
        credential_exchange_id:
            The credential_exchange_id of the exchange

        """
