# Implement Rate Limiting on Authentication and Search Endpoints

## Overview

The application lacks rate limiting on critical endpoints including authentication (/login, auth decorators), search (/search/user), and admin API routes. This was confirmed by searching for 'rate_limit' or 'throttl' which returned no matches in the app directory.

## Rationale

Without rate limiting, attackers can perform brute-force attacks on authentication, enumerate users through the search API, or cause denial-of-service by overwhelming the LDAP, Graph, and Genesys services with concurrent requests. The ThreadPoolExecutor pattern already shows search operations are computationally expensive.

---
*This spec was created from ideation and is pending detailed specification.*
