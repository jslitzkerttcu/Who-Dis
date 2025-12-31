# Add Search Result Export Capability

## Overview

Add ability to export search results to CSV format. When a search returns results, provide a download button that exports the visible data to a CSV file.

## Rationale

The blocked_numbers blueprint already returns JSON data via API endpoints. SearchCache stores result_data as JSONB. The SerializableMixin provides to_dict() for all models. Flask can easily serve CSV content. This combines existing patterns into a new feature.

---
*This spec was created from ideation and is pending detailed specification.*
