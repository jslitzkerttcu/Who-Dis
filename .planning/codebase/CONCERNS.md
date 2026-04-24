# Codebase Concerns

**Analysis Date:** 2026-04-24

## Tech Debt

**Event Loop Management in Flask Context:**
- Issue: `EmployeeProfilesRefreshService` initializes `asyncio.Semaphore` in `__init__` but relies on runtime event loop detection. Uses `asyncio.run()` which creates new event loops, but falls back to sync processing when loop is running. This creates complexity and potential race conditions.
- Files: `app/services/refresh_employee_profiles.py` (lines 37, 365-376)
- Impact: Unpredictable async/sync behavior across different execution contexts. If called from multiple places, semaphore may not work as intended.
- Fix approach: Either commit fully to async (use Celery/task queue) or remove async entirely and use ThreadPoolExecutor for concurrent photo fetching instead.

**Deprecated Service Not Fully Removed:**
- Issue: `DataWarehouseService` is marked deprecated but still imported and used by `EmployeeProfilesRefreshService`. Functionality was consolidated but code path remains.
- Files: `app/services/data_warehouse_service.py` (entire file), `app/services/refresh_employee_profiles.py` (lines 56-63)
- Impact: Confusion about which service to use for new features. Dead code path takes up maintenance burden.
- Fix approach: Remove `DataWarehouseService` entirely and consolidate all logic into `EmployeeProfilesRefreshService`. Update imports across codebase.

**Daemon Thread Token Refresh Without Graceful Shutdown:**
- Issue: `TokenRefreshService` uses daemon threads that don't guarantee cleanup on shutdown. No mechanism to flush pending token refreshes.
- Files: `app/services/token_refresh_service.py` (lines 41, 49, 61)
- Impact: Unfinished token refreshes may be lost on server restart. Tokens could expire during graceful shutdown.
- Fix approach: Implement proper shutdown hook in Flask app context to wait for pending refreshes before exit.

**Duplicate Application Initialization Logic:**
- Issue: Both `app/__init__.py` and `app/app_factory.py` contain nearly identical code for initializing services, loading configuration, and token refresh. This violates DRY principle.
- Files: `app/__init__.py`, `app/app_factory.py` (lines 30-160+ are duplicated)
- Impact: Bugs fixed in one place may not propagate to other. Maintenance burden increases.
- Fix approach: Consolidate to single factory function. Keep one version, remove the other.

## Known Bugs

**Search Cache Key Generation Uses MD5 (Deprecated):**
- Symptoms: Cache keys for search results use weak MD5 hashing
- Files: `app/blueprints/search/__init__.py` (line 43)
- Trigger: Any user search triggers caching via `_generate_search_cache_key()`
- Workaround: Cache still functions but cryptographically weak. Not a security issue for non-sensitive cache purposes.
- Fix: Use SHA256 for consistency with modern standards and encryption_service patterns.

**Future Cancellation May Leave Executor Threads Running:**
- Symptoms: Cancelled futures in `execute_concurrent_search()` don't guarantee thread termination. Threads continue executing in background.
- Files: `app/services/search_orchestrator.py` (lines 214, 263, 304)
- Trigger: Timeout occurs on any search (LDAP, Genesys, or Graph)
- Workaround: Threads eventually complete; timeout prevents blocking.
- Fix: Don't call `future.cancel()` - it doesn't terminate running threads. Instead, let executor context manager handle cleanup naturally.

**Asyncio.run() Creates New Event Loop in Flask Request Context:**
- Symptoms: httpx AsyncClient timeout configuration in photo fetching may cause issues
- Files: `app/services/refresh_employee_profiles.py` (line 372)
- Trigger: Calling refresh from any background job or scheduled task
- Workaround: Falls back to sync processing if loop detected; adds latency
- Fix: Use `asyncio.create_task()` with existing loop or fully migrate to sync httpx.

## Security Considerations

**Salt File Stored in Version Control:**
- Risk: `.whodis_salt` file is committed to repository. While not the encryption key itself, it's part of the encryption scheme.
- Files: `.whodis_salt` exists at repo root
- Current mitigation: `.gitignore` lists it but file is already tracked
- Recommendations: Remove from git history (`git rm --cached .whodis_salt`), regenerate on fresh installs, document in SECURITY.md that salt should never be committed in production.

**Encryption Key Rotation Unimplemented:**
- Risk: No safe way to rotate `WHODIS_ENCRYPTION_KEY` without data loss
- Files: `app/services/encryption_service.py` (line 23), `app/services/configuration_service.py`
- Current mitigation: Documentation says "export config before key changes" but no tooling
- Recommendations: Implement dual-key period for encryption key rotation. Create CLI tool for safe key migration with verification.

**Token Expiration Logic Assumes UTC but May Compare Naive Datetimes:**
- Risk: Timezone mismatch in token expiration comparison could cause tokens to be considered expired when still valid
- Files: `app/services/token_refresh_service.py` (lines 93-98)
- Current mitigation: Code has explicit timezone UTC checks
- Recommendations: Add strict type hints and tests for all datetime comparisons across services.

**Headers Trusted Without Validation:**
- Risk: Azure AD header `X-MS-CLIENT-PRINCIPAL-NAME` is trusted directly without validation in non-Azure environments
- Files: `app/middleware/authentication_handler.py` (lines 16-18)
- Current mitigation: Header only available from Azure App Service
- Recommendations: Add environment-based validation. In dev/test, require explicit header allowlist or disable header auth.

## Performance Bottlenecks

**No Pagination on Administrative List Views:**
- Problem: Admin database page loads all records without pagination. `User.query.order_by(...).all()` and similar patterns load entire tables into memory.
- Files: `app/blueprints/admin/users.py` (line 23, 35), `app/blueprints/admin/admin_users.py` (line 25), `app/blueprints/admin/database.py` (multiple)
- Cause: Table views implemented with simple `.all()` queries
- Improvement path: Implement pagination for tables with 100+ rows. Use `offset()/limit()` pattern. Limit default page size to 50 records.

**Search Result Caching Duration Not Configurable:**
- Problem: Search cache hardcoded to 1 hour TTL. Frequently accessed results cache too briefly; rarely accessed clutter cache.
- Files: `app/blueprints/search/__init__.py` (lines 63, 69)
- Cause: `expiration_hours=1` hardcoded in `_cache_search_result()`
- Improvement path: Move to configuration service. Allow per-user override via `config_get("search.cache_ttl_hours", 1)`.

**Concurrent Photo Fetching Limited to Semaphore but No Rate Limiting:**
- Problem: `EmployeeProfilesRefreshService` limits concurrent requests to 5 but doesn't handle rate limiting from httpx
- Files: `app/services/refresh_employee_profiles.py` (lines 36-37, 305-306)
- Cause: Semaphore controls concurrency but not request rate (requests/second)
- Improvement path: Add exponential backoff for 429 responses. Implement leaky bucket rate limiter if hitting external API limits.

**N+1 Query Risk in ComplianceCheck Loop:**
- Problem: Iterating over compliance violations and accessing related job codes/system roles could trigger N+1 queries
- Files: `app/blueprints/admin/job_role_compliance.py` (lines 427-429)
- Cause: While there's awareness of N+1 risks (line 58), not all queries use `joinedload()`
- Improvement path: Audit all loop queries. Add `joinedload()` to all many-to-one relationships in list views.

**Database Pool Not Tuned for Concurrent Requests:**
- Problem: Pool size set to 10 with max_overflow 20. For 3 concurrent searches + background tasks, may exhaust pool.
- Files: `app/database.py` (lines 37-41)
- Cause: Conservative defaults. With Flask Gunicorn workers, each worker needs pool connections.
- Improvement path: Document pool sizing formula: `(gunicorn_workers * 2) + 5` for base pool. Implement pool monitoring in admin dashboard.

## Fragile Areas

**Search Orchestrator Timeout Configuration Magic Numbers:**
- Files: `app/services/search_orchestrator.py` (lines 50-68)
- Why fragile: Each service has different timeout (3s LDAP, 5s Genesys, 4s Graph, 8s overall). No validation that individual timeouts don't exceed overall timeout. Easy to misconfigure.
- Safe modification: Add assertions in `__init__`: `assert ldap_timeout + graph_timeout < overall_timeout`. Add type hints documenting timeout units.
- Test coverage: No tests for timeout edge cases or cancellation behavior.

**Authentication Middleware Chain Order Matters But Not Documented:**
- Files: `app/app_factory.py` (lines 170-179), `app/middleware/`
- Why fragile: Order of middleware registration affects behavior. Role resolver depends on authentication handler completing first. No comments explain dependency.
- Safe modification: Document middleware order in docstring. Add runtime assertion that required middleware are registered.
- Test coverage: No integration tests for middleware interaction.

**Configuration Service Cache Invalidation Not Explicit:**
- Files: `app/services/configuration_service.py`
- Why fragile: Configuration loaded once at startup but `_clear_config_cache()` exists but not called from obvious places. Cache inconsistencies possible.
- Safe modification: Add context manager for config updates: `with config_service.transaction(): config_set(...)` ensures cache is cleared.
- Test coverage: No tests for config cache invalidation.

**Result Merger Combines Data from Inconsistent Sources:**
- Files: `app/services/result_merger.py` (537 lines)
- Why fragile: Merges LDAP, Genesys, and Graph results with complex matching logic. Small changes to field names break merging.
- Safe modification: Add schema validation layer. Define interfaces for merged result structure. Add unit tests for each provider's field transformation.
- Test coverage: No unit tests for merger logic.

**Job Role Compliance Check Runs in Daemon Thread:**
- Files: `app/services/compliance_checking_service.py` (lines 535-560)
- Why fragile: Daemon thread can be interrupted mid-operation. No transaction support for multi-step checks.
- Safe modification: Migrate to task queue (Celery/RQ) with explicit retries. Implement idempotent check operations.
- Test coverage: No tests for concurrent compliance checks.

## Scaling Limits

**Single Background Token Refresh Thread for All Services:**
- Current capacity: Refreshes ~3 services (Genesys, Graph, LDAP) every 5 minutes
- Limit: If token refresh latency exceeds 5 minutes or service count increases beyond 5, tokens expire during refresh
- Scaling path: Implement per-service refresh threads or migrate to job queue. Monitor refresh duration in admin dashboard. Alert if refresh takes >80% of check interval.

**Search Cache Stored in PostgreSQL Without Cleanup Job:**
- Current capacity: Unbounded growth; no automatic expiration cleanup
- Limit: Cache table grows indefinitely. After 100K+ entries, scan for expired records becomes slow
- Scaling path: Implement scheduled cleanup job (daily at off-peak). Add index on `expires_at` column for efficient filtering. Implement LRU eviction if table exceeds threshold.

**Concurrent Photo Fetching Limited to Single Thread Context:**
- Current capacity: Max 5 concurrent httpx requests per refresh cycle
- Limit: Large employee directory (1000+ employees) takes hours to process
- Scaling path: Use httpx connection pooling with larger limits. Implement incremental refresh (only changed records). Add queue system for profile updates.

**ThreadPoolExecutor Default 3 Workers for All Searches:**
- Current capacity: 3 concurrent searches (LDAP, Genesys, Graph) per request
- Limit: Under load, executor queue grows. Flask request timeout hits before slow searches complete.
- Scaling path: Make max_workers configurable. Use process pools for CPU-intensive merging. Monitor queue depth.

## Dependencies at Risk

**Deprecated asyncio Pattern with Python 3.10+:**
- Risk: `asyncio.get_event_loop()` and `asyncio.run()` behavior changed in Python 3.10+. Current code may break with future Python versions.
- Impact: Employee profile refresh may fail on Python 3.11+
- Migration plan: Replace `asyncio.get_event_loop()` with `asyncio.get_running_loop()` for validation. Use `asyncio.Runner()` for better control in Flask context.

**ldap3 Library Pinned to 2.9.1:**
- Risk: No active maintenance since 2021. Security issues may not be patched.
- Impact: Potential LDAP injection vulnerabilities or authentication bypasses
- Migration plan: Monitor for security updates. Plan migration to `ldap` (python-ldap) if ldap3 no longer maintained.

**httpx Not Listed as Required Dependency:**
- Risk: httpx is imported in `EmployeeProfilesRefreshService` but only mentioned in comments as optional
- Impact: Profile refresh silently fails if httpx not installed, falls back to sync without clear warning
- Migration plan: Add httpx to requirements.txt as required dependency or implement graceful degradation with clear logging.

**Pinned psutil Without Upper Bound:**
- Risk: No version constraint. Future psutil versions may break Windows-specific code in `database.py` pool monitoring
- Impact: Admin database status page may crash
- Migration plan: Pin to `psutil>=5.9,<7.0` to allow security updates but prevent major breaking changes.

## Missing Critical Features

**No Health Check Endpoint:**
- Problem: No way to verify application is healthy without making auth-protected request
- Blocks: Kubernetes/Docker health probes, monitoring systems, load balancer checks
- Solution: Implement `/health` endpoint that returns `{"status": "ok"}` with database connectivity check. Document in README.

**No Request ID Tracking:**
- Problem: Logs across multiple requests mixed together; impossible to trace single user action through system
- Blocks: Debugging multi-step failures; correlating UI issues with backend logs
- Solution: Add Flask before_request to generate unique request ID. Pass through all logs and async tasks.

**No Configuration Validation on Startup:**
- Problem: Missing required config values discovered at first use, not application start
- Blocks: Long deployment cycles waiting for config issues to surface
- Solution: Implement startup validation script that checks all required configs. Run as part of app initialization with clear error messages.

**No Rate Limiting on Search Endpoint:**
- Problem: No protection against search abuse or DOS via exhaustion of database/external API resources
- Blocks: Cannot prevent malicious repeated searches
- Solution: Implement Flask-Limiter with per-user rate limits. Document in SECURITY.md.

**No Async Task Queue for Long-Running Operations:**
- Problem: Employee profile refresh, compliance checks, and token refresh all block Flask thread
- Blocks: Cannot scale to large deployments without request queue buildup
- Solution: Implement Celery or RQ task queue. Move background operations out of request cycle.

## Test Coverage Gaps

**No Unit Tests for Search Orchestrator:**
- What's not tested: Timeout handling, concurrent cancellation, error propagation across multiple failures
- Files: `app/services/search_orchestrator.py` (332 lines, 0% coverage)
- Risk: Timeout logic bugs go undetected until production. Cancellation may leak threads.
- Priority: High - core search path

**No Unit Tests for Result Merger:**
- What's not tested: Edge cases in field mapping (missing fields, type mismatches), duplicate detection logic
- Files: `app/services/result_merger.py` (537 lines, 0% coverage)
- Risk: Merge logic can silently drop data or crash on unexpected input format
- Priority: High - data loss risk

**No Integration Tests for Middleware Chain:**
- What's not tested: Authentication -> role resolution -> audit logging interaction
- Files: `app/middleware/*.py` (no test coverage)
- Risk: Middleware order changes silently break security checks
- Priority: Medium

**No Tests for Concurrent Token Refresh:**
- What's not tested: Race conditions when multiple workers refresh same token simultaneously
- Files: `app/services/token_refresh_service.py`, `app/models/api_token.py`
- Risk: Token updates can overwrite each other; expired tokens returned to requests
- Priority: Medium

**No Tests for Database Pool Exhaustion:**
- What's not tested: Behavior when connection pool exhausted under load
- Files: `app/database.py`
- Risk: Silent connection queue buildup, request timeouts, undiagnosed failures
- Priority: Low - but important for production

**No Tests for Encryption Key Rotation:**
- What's not tested: Migration of encrypted values with key change; decryption failures
- Files: `app/services/encryption_service.py`
- Risk: Key rotation causes complete configuration loss
- Priority: High - catastrophic if broken

---

*Concerns audit: 2026-04-24*
