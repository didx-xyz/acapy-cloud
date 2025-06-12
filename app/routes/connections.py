from aries_cloudcontroller import (
    DIDRotateRequestJSON,
    DIDXRejectRequest,
    Hangup,
    Rotate,
)
from fastapi import APIRouter, Depends

from app.dependencies.acapy_clients import client_from_auth
from app.dependencies.auth import AcaPyAuth, acapy_auth_from_header
from app.exceptions import handle_acapy_call
from app.util.pagination import (
    descending_query_parameter,
    limit_query_parameter,
    offset_query_parameter,
    order_by_query_parameter,
)
from shared.log_config import get_logger
from shared.models.connection_record import (
    Connection,
    Protocol,
    Role,
    State,
    conn_record_to_connection,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/v1/connections", tags=["connections"])


@router.get("", summary="Fetch Connection Records")
async def get_connections(  # pylint: disable=R0913,R0917
    limit: int | None = limit_query_parameter,
    offset: int | None = offset_query_parameter,
    order_by: str | None = order_by_query_parameter,
    descending: bool = descending_query_parameter,
    alias: str | None = None,
    connection_protocol: Protocol | None = None,
    invitation_key: str | None = None,
    invitation_msg_id: str | None = None,
    my_did: str | None = None,
    state: State | None = None,
    their_did: str | None = None,
    their_public_did: str | None = None,
    their_role: Role | None = None,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> list[Connection]:
    """Fetch a list of connection records
    ---
    The records contain information about connections with other tenants, such as the state of the connection,
    the alias of the connection, the label and the did of the other party, and other metadata.

    The following query parameters can be used to filter the connection records to fetch.

    Parameters (Optional):
    ---
        limit: int - The maximum number of records to retrieve
        offset: int - The offset to start retrieving records from
        descending: bool - Whether to return results in descending order. Results are ordered by record created time.
        alias: str
        connection_protocol: Protocol: "didexchange/1.0", "didexchange/1.1"
        invitation_key: str
        invitation_msg_id: str
        my_did: str
        state: State: "active", "response", "request", "start", "completed", "init", "error", "invitation", "abandoned"
        their_did: str
        their_public_did: str
        their_role: Role: "invitee", "requester", "inviter", "responder"

    Returns
    -------
        List[Connection]
            A list of connection records

    """
    logger.debug("GET request received: Get connections")

    async with client_from_auth(auth) as aries_controller:
        connections = await handle_acapy_call(
            logger=logger,
            acapy_call=aries_controller.connection.get_connections,
            limit=limit,
            offset=offset,
            order_by=order_by,
            descending=descending,
            alias=alias,
            connection_protocol=connection_protocol,
            invitation_key=invitation_key,
            invitation_msg_id=invitation_msg_id,
            my_did=my_did,
            state=state,
            their_did=their_did,
            their_public_did=their_public_did,
            their_role=their_role,
        )

    result = (
        [conn_record_to_connection(connection) for connection in connections.results]
        if connections.results
        else []
    )
    logger.debug("Successfully returned connections.")
    return result


@router.get("/{connection_id}", summary="Fetch a Connection Record")
async def get_connection_by_id(  # noqa: D417
    connection_id: str,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> Connection:
    """Fetch a connection record by id
    ---
    A connection record contains information about a connection with other tenants, such as the state of the connection,
    the alias of the connection, the label and the did of the other party, and other metadata.

    Parameters
    ----------
        connection_id: str
            The identifier of the connection record that you want to fetch

    Returns
    -------
        Connection
            The connection record

    """
    bound_logger = logger.bind(body={"connection_id": connection_id})
    bound_logger.debug("GET request received: Get connection by ID")
    async with client_from_auth(auth) as aries_controller:
        connection = await handle_acapy_call(
            logger=bound_logger,
            acapy_call=aries_controller.connection.get_connection,
            conn_id=connection_id,
        )

    result = conn_record_to_connection(connection)
    bound_logger.debug("Successfully got connection by ID.")
    return result


@router.delete(
    "/{connection_id}", summary="Delete a Connection Record", status_code=204
)
async def delete_connection_by_id(  # noqa: D417
    connection_id: str,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> None:
    """Delete connection record by id
    ---
    This endpoint deletes a connection record by id.

    If the connection uses the didexchange protocol, then we hangup the connection, such that the other party also has
    their record deleted.

    Parameters
    ----------
        connection_id: str
            The identifier of the connection record that you want to delete

    Returns
    -------
        status_code: 204

    """
    bound_logger = logger.bind(body={"connection_id": connection_id})
    bound_logger.debug("DELETE request received: Delete connection by ID")

    async with client_from_auth(auth) as aries_controller:
        # Fetch connection record, and check if it uses didexchange protocol
        conn_record = await handle_acapy_call(
            logger=bound_logger,
            acapy_call=aries_controller.connection.get_connection,
            conn_id=connection_id,
        )
        connection_protocol = conn_record.connection_protocol or ""
        is_did_exchange_protocol = "didexchange" in connection_protocol

        if is_did_exchange_protocol:
            # If it uses didexchange protocol, then we hangup the connection
            await handle_acapy_call(
                logger=bound_logger,
                acapy_call=aries_controller.did_rotate.hangup,
                conn_id=connection_id,
            )
            bound_logger.debug("Successfully hung up connection.")
        else:
            # If it uses connections protocol, then we just delete the record
            await handle_acapy_call(
                logger=bound_logger,
                acapy_call=aries_controller.connection.delete_connection,
                conn_id=connection_id,
            )
            bound_logger.debug("Successfully deleted connection by ID.")


@router.post(
    "/did-exchange/create-request",
    summary="Create a DID Exchange Request",
)
async def create_did_exchange_request(  # noqa: D417
    their_public_did: str,
    alias: str | None = None,
    goal: str | None = None,
    goal_code: str | None = None,
    my_label: str | None = None,
    use_did: str | None = None,
    use_did_method: str | None = None,
    use_public_did: bool = False,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> Connection:
    """Create a DID Exchange request
    ---
    This endpoint allows you to initiate a DID Exchange request with another party using their public DID.

    The goal and goal_code parameters provide additional context for the request.

    Only one of `use_did`, `use_did_method` or `use_public_did` should be specified. If none of these are specified,
    a new local DID will be created for this connection.

    Parameters
    ----------
        their_public_did: str
            The DID of the party you want to connect to.
        alias: str, optional
            An alias for the connection. Defaults to None.
        goal: str, optional
            Optional self-attested string for sharing the intent of the connection.
        goal_code: str, optional
            Optional self-attested code for sharing the intent of the connection.
        my_label: str, optional
            Your label for the request.
        use_did: str, optional
            Your local DID to use for the connection.
        use_did_method: str, optional
            The method to use for the connection: "did:peer:2" or "did:peer:4".
        use_public_did: bool
            Use your public DID for this connection. Defaults to False.

    Returns
    -------
        Connection
            The connection record created by the DID exchange request.

    """
    bound_logger = logger.bind(
        body={
            "their_public_did": their_public_did,
            "alias": alias,
            "goal": goal,
            "goal_code": goal_code,
            "my_label": my_label,
            "use_did": use_did,
            "use_did_method": use_did_method,
            "use_public_did": use_public_did,
        }
    )
    bound_logger.debug("POST request received: Create DID exchange request")

    async with client_from_auth(auth) as aries_controller:
        connection_record = await handle_acapy_call(
            logger=bound_logger,
            acapy_call=aries_controller.did_exchange.create_request,
            their_public_did=their_public_did,
            alias=alias,
            auto_accept=True,
            goal=goal,
            goal_code=goal_code,
            my_label=my_label,
            protocol="didexchange/1.1",
            use_did=use_did,
            use_did_method=use_did_method,
            use_public_did=use_public_did,
        )

    result = conn_record_to_connection(connection_record)
    bound_logger.debug("Successfully created DID exchange request.")
    return result


@router.post(
    "/did-exchange/accept-request",
    summary="Accept a DID Exchange Request",
)
async def accept_did_exchange_request(  # noqa: D417
    connection_id: str,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> Connection:
    """Accept a stored DID Exchange request
    ---
    This endpoint allows you to accept a request by providing the connection ID.

    Parameters
    ----------
        connection_id: str
            The ID of the connection request you want to accept.

    Returns
    -------
        Connection
            The connection record created by accepting the DID exchange request.

    """
    bound_logger = logger.bind(body={"connection_id": connection_id})
    bound_logger.debug("POST request received: Accept DID exchange request")

    async with client_from_auth(auth) as aries_controller:
        connection_record = await handle_acapy_call(
            logger=bound_logger,
            acapy_call=aries_controller.did_exchange.accept_request,
            conn_id=connection_id,
            use_public_did=False,
            # todo: if use_public_did=True, then agent raises:
            # DIDXManagerError: did_rotate~attach required if no signed doc attachment
        )

    result = conn_record_to_connection(connection_record)
    bound_logger.debug("Successfully accepted DID exchange request.")
    return result


@router.post(
    "/did-exchange/reject",
    summary="Reject or Abandon a DID Exchange",
)
async def reject_did_exchange(
    connection_id: str,
    body: DIDXRejectRequest | None = None,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> Connection:
    """Reject or abandon a DID Exchange
    ---
    This endpoint allows you to reject or abandon a DID Exchange request. You can optionally provide a reason
    for the rejection.

    Returns
    -------
        Connection
            The connection record after rejecting the DID exchange request.

    """
    bound_logger = logger.bind(body={"connection_id": connection_id})
    bound_logger.debug("POST request received: Reject DID exchange")

    async with client_from_auth(auth) as aries_controller:
        connection_record = await handle_acapy_call(
            logger=bound_logger,
            acapy_call=aries_controller.did_exchange.reject,
            conn_id=connection_id,
            body=body,
        )

    result = conn_record_to_connection(connection_record)
    bound_logger.debug("Successfully rejected DID exchange.")
    return result


@router.post(
    "/did-rotate",
    summary="Begin DID Rotation",
)
async def rotate_did(  # noqa: D417
    connection_id: str,
    to_did: str,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> Rotate:
    """Begin the rotation of a DID as a rotator.
    ---
    This endpoint allows you to begin the DID rotation for an existing connection. The `to_did` parameter specifies
    the new DID that the rotating party is rotating to.

    Parameters
    ----------
        connection_id: str
            The ID of the connection for which the DID is to be rotated.
        to_did: str
            The new DID that the rotating party is rotating to.

    Returns
    -------
        Rotate
            The record after the DID rotation is initiated.

    """
    bound_logger = logger.bind(body={"connection_id": connection_id, "to_did": to_did})
    bound_logger.debug("POST request received: Rotate DID")

    async with client_from_auth(auth) as aries_controller:
        rotate = await handle_acapy_call(
            logger=bound_logger,
            acapy_call=aries_controller.did_rotate.rotate,
            conn_id=connection_id,
            body=DIDRotateRequestJSON(to_did=to_did),
        )

    bound_logger.debug("Successfully initiated DID rotation.")
    return rotate


@router.post(
    "/did-rotate/hangup",
    summary="Hangup DID Rotation",
)
async def hangup_did_rotation(  # noqa: D417
    connection_id: str,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> Hangup:
    """Send a hangup for a DID rotation as the rotator.
    ---
    This endpoint allows you to hangup a DID rotation process for an existing connection.

    Parameters
    ----------
        connection_id: str
            The ID of the connection for which the DID rotation is being hung up.

    Returns
    -------
        Hangup
            The record after the DID rotation is hung up.

    """
    bound_logger = logger.bind(body={"connection_id": connection_id})
    bound_logger.debug("POST request received: Hangup DID rotation")

    async with client_from_auth(auth) as aries_controller:
        hangup = await handle_acapy_call(
            logger=bound_logger,
            acapy_call=aries_controller.did_rotate.hangup,
            conn_id=connection_id,
        )

    bound_logger.debug("Successfully hung up DID rotation.")
    return hangup
