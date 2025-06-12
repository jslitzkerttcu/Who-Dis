# Phone Number Matching and User Identification Rules

This document describes the comprehensive phone number processing logic and user type identification rules used in WhoDis.

## Overview

WhoDis integrates with multiple identity systems (LDAP/Active Directory, Genesys Cloud, Microsoft Graph) and implements sophisticated logic to identify user types, format phone numbers consistently, and merge data from multiple sources.

## Phone Number Formatting Logic

**Location**: `app/blueprints/search/__init__.py:1631-1679`

### Formatting Rules
- **4-digit numbers**: Kept as extensions (e.g., "1234")
- **10-digit numbers**: Formatted as "+1 XXX-XXX-XXXX" (adds US country code)
- **11-digit numbers starting with 1**: Formatted as "+1 XXX-XXX-XXXX"
- **Invalid formats**: Returns original value unchanged

### Display Labels
- `mobile` → "Cell Phone"
- `business` → "Business" 
- `teams` → "Office"
- `teams_did` → "DID"
- `genesys_did` → "DID"
- `genesys_ext` → "Ext"
- `genesys` → "Office"

### Service Badges with Tooltips
- Teams numbers: Blue "Teams" badge with tooltip showing raw AD field sources
- Genesys numbers: Orange "Genesys" badge with tooltip showing both AD and Genesys field sources  
- AD numbers: Blue "AD" badge with tooltip showing raw AD field sources
- Legacy numbers: Gray "Legacy" badge with tooltip showing legacy field sources

### Tooltip Content
Each badge includes detailed tooltips showing raw field mappings:
- **Format**: "[AD] fieldName; [Genesys] fieldName" for combined sources
- **Examples**: 
  - "[AD] telephoneNumber" for Teams DID
  - "[AD] extensionAttribute4; [Genesys] primaryContactInfo[mediaType=PHONE].address" for Genesys DID
  - "[AD] pager; [Genesys] addresses[type=WORK2].extension" for extensions
  - "[AD] ExclaimerMobile; [Graph] mobilePhone; [Genesys] addresses[type=MOBILE].address" for mobile

## User Type Classification from LDAP/Active Directory

**Location**: `app/services/ldap_service.py:387-476`

### AD Attributes Used
- `telephoneNumber`: Primary business phone
- `extensionAttribute4`: Custom attribute for DID numbers
- `pager`: Extension numbers  
- `ExclaimerMobile`: Mobile phone numbers
- `ipPhone`: Legacy extension field

### Classification Rules

#### 1. Genesys Extension Only Users
**Criteria**: 
- `telephoneNumber` = "918-749-8828" (main switchboard) AND has `pager` value

**Phone Mapping**:
- `genesys_ext` = pager value

**Display**: Main number + extension badge

#### 2. Genesys DID Users
**Criteria**:
- Has `extensionAttribute4` value
- No `telephoneNumber` OR `telephoneNumber` matches `extensionAttribute4`

**Phone Mapping**:
- `genesys_did` = extensionAttribute4
- `genesys_ext` = pager (if present)

#### 3. Teams Users
**Criteria**:
- Has `telephoneNumber` but no `pager` or `extensionAttribute4`

**Phone Mapping**:
- `teams_did` = telephoneNumber

#### 4. Dual Users (Teams + Genesys)
**Criteria**:
- Has both `telephoneNumber` and `extensionAttribute4` with different values

**Phone Mapping**:
- `teams_did` = telephoneNumber
- `genesys_did` = extensionAttribute4
- `genesys_ext` = pager (if present)

#### 5. Legacy Extension Users
**Criteria**:
- Has `ipPhone` field value

**Phone Mapping**:
- Custom handling with "Legacy" badge

#### 6. Mobile Numbers
**Criteria**:
- Has `ExclaimerMobile` value

**Phone Mapping**:
- `mobile` = ExclaimerMobile

## Genesys Phone Number Extraction

**Location**: `app/services/genesys_service.py:386-479`

### Data Sources

#### Primary Contact Info
- Looks for `mediaType: "PHONE"` in `primaryContactInfo` array
- Maps to `primary` phone type

#### Address-based Phone Numbers
Processes `addresses` array for phone entries based on `name` and `type` fields:

- **"work phone 2"** or `type: "WORK2"` → `extension` and `work2`
- **"work phone 3"** or `type: "WORK3"` → `work3`
- **"work"** or `type: "WORK"` → `work`
- **"mobile"/"cell"** or `type: "MOBILE"` → `mobile`
- **"home"** or `type: "HOME"` → `home`

### Special Handling
- For WORK2 type: Extension is in the `extension` field, not `address` field
- All Genesys numbers receive orange "Genesys" service badge in UI

## Microsoft Graph Phone Processing

**Location**: `app/services/graph_service.py:326-329`

### Data Sources
- `businessPhones`: Array of business phone numbers
- `mobilePhone`: Mobile phone number

These are merged into the unified phone numbers structure via the result merger.

## Phone Number Merging Logic

**Location**: `app/services/result_merger.py:145-161`

The result merger combines phone numbers from LDAP and Graph sources:

```python
def _merge_phone_numbers(self, merged, graph_data):
    phone_numbers = merged.get("phoneNumbers", {})
    
    if graph_data.get("phoneNumbers"):
        for phone_type, number in graph_data["phoneNumbers"].items():
            if phone_type == "mobile":
                phone_numbers["mobile"] = number
            elif phone_type.startswith("business"):
                phone_numbers["business"] = number
            else:
                phone_numbers[phone_type] = number
    
    merged["phoneNumbers"] = phone_numbers
```

## User Type Badge Display Logic

**Location**: `app/blueprints/search/__init__.py:874-893`

The UI displays user type badges based on phone number analysis:

```python
phone_numbers = user_data.get("phoneNumbers", {})
has_teams = any("teams" in str(k).lower() for k in phone_numbers.keys())
has_genesys = any("genesys" in str(k).lower() for k in phone_numbers.keys())

if has_teams:
    # Shows blue "Teams User" badge
if has_genesys:
    # Shows orange "Genesys User" badge
```

## Extension vs DID Logic

### Extensions
- **Format**: 4-digit numbers
- **Sources**: `pager` field or Genesys WORK2 addresses
- **Display**: Raw number with "Ext" label

### DIDs (Direct Inward Dial)
- **Format**: 10/11-digit formatted phone numbers
- **Sources**: `telephoneNumber`, `extensionAttribute4`, or Genesys primary contact
- **Display**: "+1 XXX-XXX-XXXX" format with "DID" label

### Legacy Extensions
- **Source**: `ipPhone` field
- **Display**: Raw number with "Legacy" badge

## Phone Type Priority and Hierarchy

### Display Priority
1. **Teams DID**: Primary business number for Teams users
2. **Genesys DID**: Primary business number for Genesys users
3. **Genesys Extension**: Secondary for Genesys users
4. **Mobile**: Personal/mobile numbers
5. **Legacy**: Historical extension numbers

### Service Integration Priority
1. **Graph API**: Takes priority for enhanced fields when available
2. **LDAP**: Primary source for phone number classification
3. **Genesys**: Supplementary contact information

## Search Result Display Structure

Phone numbers in search results include:
- **Consistent formatting**: "+1 XXX-XXX-XXXX" for DIDs, raw for extensions
- **Service-specific badges**: Teams (blue), Genesys (orange), AD (blue)
- **Type-specific labels**: Cell Phone, Office, DID, Ext, etc.
- **Color-coded UI elements**: Visual distinction between services

## Implementation Notes

### Key Functions
- `_format_phone_number()`: Handles all number formatting
- `_get_phone_label()`: Maps phone types to display labels
- `_get_phone_badge()`: Adds service-specific badges
- `_merge_phone_numbers()`: Combines data from multiple sources

### Performance Considerations
- Phone number processing is done during search result compilation
- Caching is implemented at the service level for API responses
- UI updates use HTMX for dynamic content without full page refreshes

### Error Handling
- Invalid phone formats are preserved and displayed as-is
- Missing fields are handled gracefully with fallbacks
- Service failures don't prevent display of available phone data

This comprehensive system ensures accurate user type identification and consistent phone number display across all identity providers integrated with WhoDis.