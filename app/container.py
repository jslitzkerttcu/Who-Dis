"""Dependency injection container for service management."""

import logging
from typing import Dict, Any, Callable, Optional, Type, List
from threading import Lock
from abc import ABC


logger = logging.getLogger(__name__)


class ServiceContainer:
    """
    Thread-safe dependency injection container.

    Manages service lifecycle and dependencies:
    - Lazy instantiation of services
    - Singleton pattern for services
    - Dependency resolution
    """

    def __init__(self) -> None:
        self._services: Dict[str, Any] = {}
        self._factories: Dict[str, Callable[["ServiceContainer"], Any]] = {}
        self._lock = Lock()

    def register(self, name: str, factory: Callable[["ServiceContainer"], Any]) -> None:
        """
        Register a service factory.

        Args:
            name: Service name for retrieval
            factory: Callable that takes the container and returns a service instance
        """
        with self._lock:
            self._factories[name] = factory
            logger.debug(f"Registered service factory: {name}")

    def get(self, name: str) -> Any:
        """
        Get or create a service instance.

        Args:
            name: Service name

        Returns:
            Service instance

        Raises:
            KeyError: If service is not registered
        """
        with self._lock:
            if name not in self._services:
                if name not in self._factories:
                    raise KeyError(f"Service '{name}' not registered")

                # Create service instance using factory
                logger.debug(f"Creating service instance: {name}")
                self._services[name] = self._factories[name](self)

            return self._services[name]

    def get_all_by_interface(self, interface: Type[ABC]) -> List[Any]:
        """
        Get all services that implement a specific interface.

        Args:
            interface: The interface class to check against

        Returns:
            List of services implementing the interface
        """
        services = []

        with self._lock:
            # Ensure all services are instantiated
            for name in self._factories:
                if name not in self._services:
                    self._services[name] = self._factories[name](self)

            # Filter by interface
            for service in self._services.values():
                if isinstance(service, interface):
                    services.append(service)

        return services

    def reset(self) -> None:
        """Reset the container, clearing all service instances."""
        with self._lock:
            self._services.clear()
            logger.debug("Container reset - all service instances cleared")

    def is_registered(self, name: str) -> bool:
        """Check if a service is registered."""
        return name in self._factories

    def list_services(self) -> List[str]:
        """List all registered service names."""
        return list(self._factories.keys())


# Global container instance
_container: Optional[ServiceContainer] = None


def get_container() -> ServiceContainer:
    """Get the global service container instance."""
    global _container
    if _container is None:
        _container = ServiceContainer()
    return _container


def register_services(container: ServiceContainer) -> None:
    """
    Register all application services.

    This function should be called during application initialization
    to register all service factories.
    """
    # Import services here to avoid circular imports
    from app.services.configuration_service import configuration_service
    from app.services.ldap_service import LDAPService
    from app.services.genesys_service import GenesysCloudService
    from app.services.graph_service import GraphService
    from app.services.audit_service_postgres import PostgresAuditService
    from app.services.token_refresh_service import TokenRefreshService
    from app.services.genesys_cache_db import GenesysCacheDB
    from app.services.encryption_service import EncryptionService
    from app.services.data_warehouse_service import DataWarehouseService

    # Configuration service (use singleton instance)
    container.register("config", lambda c: configuration_service)

    # Encryption service
    container.register("encryption", lambda c: EncryptionService())

    # Audit services (create new instance that implements both interfaces)
    audit_service_instance = PostgresAuditService()
    container.register("audit_logger", lambda c: audit_service_instance)
    container.register("audit_query", lambda c: audit_service_instance)

    # Cache service
    container.register("genesys_cache", lambda c: GenesysCacheDB())

    # Search services (depend on config)
    container.register("ldap_service", lambda c: LDAPService())
    container.register("genesys_service", lambda c: GenesysCloudService())
    container.register("graph_service", lambda c: GraphService())
    container.register("data_warehouse_service", lambda c: DataWarehouseService())

    # Token refresh service (depends on container for dynamic discovery)
    container.register("token_refresh", lambda c: TokenRefreshService(container))

    logger.info(f"Registered {len(container.list_services())} services")


def inject_dependencies(app) -> None:
    """
    Inject the service container into the Flask app.

    Args:
        app: Flask application instance
    """
    container = get_container()
    register_services(container)
    app.container = container

    # Make container available in templates
    @app.context_processor
    def inject_container() -> Dict[str, Any]:
        return {"container": container}
