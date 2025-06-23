"""Dependency injection container for the revocation service."""

from dependency_injector import containers, providers

from revocation_service.services.rev_reg_manager import RevRegManager


class Container(containers.DeclarativeContainer):
    """Dependency injection container for the revocation service."""

    # Revocation registry service
    rev_reg_manager = providers.Singleton(RevRegManager)
