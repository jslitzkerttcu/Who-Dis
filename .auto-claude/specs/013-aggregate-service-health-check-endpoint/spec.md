# Aggregate Service Health Check Endpoint

## Overview

Add a /api/health endpoint that aggregates connection status from all registered services (LDAP, Genesys, Graph) into a single health check response. Returns detailed status per service plus overall system health.

## Rationale

Each service already implements test_connection() method via the ISearchService interface. The ServiceContainer has get_all_by_interface() method to discover services. The pattern for aggregating service calls exists in SearchOrchestrator. This is just combining existing patterns into a new endpoint.

---
*This spec was created from ideation and is pending detailed specification.*
