---
phase: 01-foundation
plan: 04
type: execute
wave: 2
depends_on: [01]
files_modified:
  - app/middleware/request_id.py
  - app/__init__.py
  - requirements.txt
autonomous: true
requirements: [OPS-02]
must_haves:
  truths:
    - "Every HTTP request has a request_id available on flask.g and echoed back in the X-Request-ID response header"
    - "Inbound X-Request-ID header is honored when well-formed (UUID hex); otherwise a UUID4 is generated"
    - "Every log line emitted via the standard logging module includes the request_id field in JSON output"
  artifacts:
    - path: "app/middleware/request_id.py"
      provides: "init_request_id(app) registrar + RequestIdFilter logging filter"
      contains: "class RequestIdFilter"
    - path: "requirements.txt"
      provides: "python-json-logger dependency pinned"
      contains: "python-json-logger"
  key_links:
    - from: "app/__init__.py"
      to: "app/middleware/request_id.py"
      via: "init_request_id(app) call inside create_app()"
      pattern: "init_request_id"
    - from: "logging root handler"
      to: "RequestIdFilter"
      via: "logging.getLogger().addFilter() + JsonFormatter with request_id field"
      pattern: "RequestIdFilter|JsonFormatter"
---

<objective>
Add request-ID propagation through Flask + JSON-structured logging so every log line is traceable to a single request. Satisfies OPS-02.

Purpose: Diagnosing user-reported issues currently requires correlating timestamps across log lines. Request IDs make a single user action one grep away.
Output: New `request_id` middleware module, JSON formatter wired in `app/__init__.py`, `python-json-logger` added to requirements.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/01-foundation/01-CONTEXT.md
@.planning/phases/01-foundation/01-PATTERNS.md
@CLAUDE.md
@app/middleware/audit_logger.py
@app/__init__.py
@requirements.txt
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create request_id middleware (UUID gen + Flask hooks + log filter)</name>
  <read_first>
    - app/middleware/audit_logger.py (analog — small middleware module per PATTERNS.md)
    - app/__init__.py lines 158–166 (existing before_request pattern)
    - app/__init__.py lines 17–20 (existing logging.basicConfig call to replace)
  </read_first>
  <action>
    Per D-05 / D-06 / D-07:

    1. Create `app/middleware/request_id.py`:
       ```python
       import logging
       import re
       import uuid
       from flask import Flask, g, request

       logger = logging.getLogger(__name__)

       _UUID_HEX_RE = re.compile(r"^[0-9a-fA-F-]{8,64}$")

       class RequestIdFilter(logging.Filter):
           """Injects g.request_id into every LogRecord as record.request_id."""
           def filter(self, record: logging.LogRecord) -> bool:
               try:
                   from flask import g as _g  # local import: filter runs outside request too
                   record.request_id = getattr(_g, "request_id", "-")
               except RuntimeError:
                   record.request_id = "-"
               return True

           def __repr__(self) -> str:  # for debug
               return "RequestIdFilter"

       def init_request_id(app: Flask) -> None:
           @app.before_request
           def _set_request_id() -> None:
               inbound = request.headers.get("X-Request-ID", "")
               if inbound and _UUID_HEX_RE.match(inbound):
                   g.request_id = inbound[:64]
               else:
                   g.request_id = uuid.uuid4().hex

           @app.after_request
           def _echo_request_id(response):
               rid = getattr(g, "request_id", None)
               if rid:
                   response.headers["X-Request-ID"] = rid
               return response
       ```
    2. Add `python-json-logger>=2.0.7,<3` to `requirements.txt` (pin like other entries).
    3. Modify `app/__init__.py`:
       - Replace the existing `logging.basicConfig(... format="%(asctime)s ...")` block with:
         ```python
         import logging
         from pythonjsonlogger import jsonlogger
         from app.middleware.request_id import RequestIdFilter, init_request_id

         _root = logging.getLogger()
         _root.setLevel(logging.INFO)
         # Clear pre-existing handlers (avoid duplicate output under reloader)
         for h in list(_root.handlers):
             _root.removeHandler(h)
         _handler = logging.StreamHandler()
         _handler.setFormatter(jsonlogger.JsonFormatter(
             "%(asctime)s %(levelname)s %(name)s %(request_id)s %(message)s",
             rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
         ))
         _handler.addFilter(RequestIdFilter())
         _root.addHandler(_handler)
         logging.getLogger("urllib3").setLevel(logging.WARNING)  # preserved from DEBT-01 migration
         ```
       - Inside `create_app()`, after `app.config` is loaded and BEFORE blueprint registration, call `init_request_id(app)`.
    4. CONFIRM the third-party logger quieting (urllib3, etc.) preserved by Plan 01 still appears.
  </action>
  <verify>
    <automated>grep -q 'class RequestIdFilter' app/middleware/request_id.py &amp;&amp; grep -q 'init_request_id' app/__init__.py &amp;&amp; grep -q 'python-json-logger' requirements.txt &amp;&amp; grep -q 'JsonFormatter' app/__init__.py &amp;&amp; python -c 'from app import create_app; app=create_app(); c=app.test_client(); r=c.get(\"/health/live\", headers={\"X-Request-ID\":\"abcd1234abcd1234abcd1234abcd1234\"}); assert r.headers.get(\"X-Request-ID\") == \"abcd1234abcd1234abcd1234abcd1234\", r.headers.get(\"X-Request-ID\")'</automated>
  </verify>
  <acceptance_criteria>
    - `app/middleware/request_id.py` exists with `class RequestIdFilter` and `def init_request_id`
    - `grep -n "python-json-logger" requirements.txt` matches with pinned version
    - `grep -n "JsonFormatter" app/__init__.py` matches
    - `grep -n "init_request_id(app)" app/__init__.py` matches
    - Inbound `X-Request-ID: abcd1234abcd1234abcd1234abcd1234` is echoed back verbatim in response headers
    - When NO inbound header, response has `X-Request-ID` set to a 32-hex-char UUID
    - JSON log lines include `"request_id"` key (verify by capturing stderr during a request and grepping for `"request_id"`)
    - `urllib3` is quieted to WARNING (still suppressed)
  </acceptance_criteria>
  <done>Every request has a propagated request_id; structured JSON logs include the field; inbound IDs honored when well-formed.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| upstream proxy → Flask app | Inbound X-Request-ID header is attacker-controllable |
| log sink → operator console | Structured JSON may be parsed by downstream tooling |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-04-01 | Tampering | Inbound X-Request-ID | mitigate | Validate against `^[0-9a-fA-F-]{8,64}$` regex; truncate to 64 chars; otherwise generate fresh UUID4. Prevents log injection via newline/control chars. |
| T-01-04-02 | Information Disclosure | JSON log payload | mitigate | Formatter emits only `timestamp, level, logger, request_id, message` — does NOT auto-include extras. Sensitive values (passwords, tokens) are already redacted at the call site per CLAUDE.md "Logging" guidelines. |
| T-01-04-03 | Repudiation | Request without an ID | mitigate | Server always generates a UUID4 fallback when inbound is missing or malformed; "-" sentinel only used outside request context (background threads). |
</threat_model>

<verification>
- Send `curl -i -H 'X-Request-ID: 12345678abcd1234abcd1234abcd1234' http://localhost:5000/health/live` → response includes `X-Request-ID: 12345678abcd1234abcd1234abcd1234`
- Send `curl -i http://localhost:5000/health/live` (no inbound) → response has a fresh 32-hex `X-Request-ID`
- Send `curl -i -H 'X-Request-ID: ../../etc/passwd' http://localhost:5000/health/live` → response has a freshly-generated UUID (malformed inbound rejected)
- Tail server log: every line is valid JSON containing `"request_id"`
</verification>

<success_criteria>
OPS-02 acceptance criterion satisfied: every request gets a unique request ID propagated through all logs.
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundation/01-04-SUMMARY.md`.
</output>
