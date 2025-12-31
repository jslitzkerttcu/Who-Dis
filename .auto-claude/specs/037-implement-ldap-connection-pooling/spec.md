# Implement LDAP Connection Pooling

## Overview

Each LDAP search operation creates a new Server and Connection object, performs the search, then closes the connection. Connection establishment to LDAP servers involves TCP handshake, TLS negotiation, and BIND authentication, adding ~50-200ms per request.

## Rationale

LDAP connections are expensive to establish. The ldap3 library supports connection pooling which maintains a pool of authenticated connections ready for reuse. This eliminates connection overhead for subsequent requests and is particularly valuable for the concurrent search pattern where LDAP, Genesys, and Graph run simultaneously.

---
*This spec was created from ideation and is pending detailed specification.*
