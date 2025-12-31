# Add Input Validation and Length Limits on Search Terms

## Overview

The search endpoint at app/blueprints/search/search_refactored.py accepts search terms with only `.strip()` applied. While LDAP injection is prevented by escape_filter_chars() in ldap_service.py, there are no length limits or character restrictions on search input, which could cause resource exhaustion.

## Rationale

Extremely long search terms or search terms with special patterns could cause denial of service through: 1) Memory exhaustion when processing very long strings, 2) Expensive regex operations in wildcard LDAP searches, 3) Backend API timeouts from complex queries. A 3-character minimum is enforced for fuzzy LDAP search but no maximum exists.

---
*This spec was created from ideation and is pending detailed specification.*
