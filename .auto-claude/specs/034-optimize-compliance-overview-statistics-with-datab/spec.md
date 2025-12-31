# Optimize Compliance Overview Statistics with Database Aggregation

## Overview

The api_compliance_overview() function loads ALL compliance violations into memory and then iterates through them multiple times to calculate statistics (grouping by severity, counting violation types). This is extremely inefficient for large datasets.

## Rationale

When compliance checks run on hundreds or thousands of employees, loading all violations into Python memory and iterating multiple times (once for employee UPN extraction, once for each severity level, once for violation types) causes significant memory pressure and slow response times. Database aggregation is orders of magnitude more efficient.

---
*This spec was created from ideation and is pending detailed specification.*
