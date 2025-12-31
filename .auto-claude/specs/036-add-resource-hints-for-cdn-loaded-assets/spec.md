# Add Resource Hints for CDN-Loaded Assets

## Overview

The base.html template loads Tailwind CSS (cdn.tailwindcss.com), Font Awesome (cdnjs.cloudflare.com), and HTMX (unpkg.com) from CDNs without any resource hints. Adding preconnect and dns-prefetch hints can reduce connection establishment time.

## Rationale

Browser needs to perform DNS lookup, TCP connection, and TLS negotiation for each CDN domain before downloading assets. Preconnect hints allow this to happen in parallel with HTML parsing, reducing blocking time by 100-300ms on initial page loads.

---
*This spec was created from ideation and is pending detailed specification.*
