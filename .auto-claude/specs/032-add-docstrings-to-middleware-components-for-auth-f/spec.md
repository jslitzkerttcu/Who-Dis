# Add docstrings to middleware components for auth flow clarity

## Overview

The middleware components (authentication_handler.py, role_resolver.py, user_provisioner.py, session_manager.py) lack comprehensive docstrings explaining their purpose, dependencies, and interaction patterns. The auth.py file uses these but the flow isn't clearly documented inline.

## Rationale

Authentication is a critical security boundary. Developers modifying auth behavior need to understand the complete middleware pipeline. Without clear docstrings, there's risk of introducing security vulnerabilities by misunderstanding the authentication flow.

---
*This spec was created from ideation and is pending detailed specification.*
