# Search Guide

This guide provides detailed information on using WhoDis's search features effectively.

## Table of Contents
- [Basic Search](#basic-search)
- [Search Strategies](#search-strategies)
- [Understanding Results](#understanding-results)
- [Advanced Features](#advanced-features)
- [Performance Tips](#performance-tips)

## Basic Search

### Performing a Search

1. **Locate the search box** at the top of any page
2. **Type your search term** (name, email, or username)
3. **Press Enter** or click the **Search button**
4. **Wait 1-3 seconds** for results from all systems
5. **Review results** in the Azure AD and Genesys Cloud cards

### What Gets Searched

WhoDis searches across multiple systems simultaneously:

**Active Directory (LDAP)**:
- Email addresses (`mail`)
- Display names (`displayName`)
- First names (`givenName`)
- Last names (`sn`)
- SAM account names (`sAMAccountName`)
- User principal names (`userPrincipalName`)

**Microsoft Graph (Azure AD)**:
- Enhanced profile data
- Photo information
- Additional user properties

**Genesys Cloud**:
- Agent names
- Email addresses
- Usernames

### Search Syntax

WhoDis supports various search formats:

**Exact email**:
```
john.doe@example.com
john.doe@corp.example.com
```

**Full name** (various formats):
```
John Doe
Doe, John
john doe
```

**Partial name** (wildcard search in LDAP):
```
john
doe
jdoe
```

**Username**:
```
jdoe
john.doe
```

**Note:** Searches are **case-insensitive** across all systems.

## Search Strategies

### Finding Specific Users

#### When You Know the Email
**Best approach:** Use the full email address
```
john.doe@example.com
```
**Why:** Most specific, fastest results, single match

#### When You Know the Full Name
**Try different formats:**
```
1. John Doe
2. Doe, John
3. john doe
```
**Why:** Different systems may store names differently

#### When You Only Have Partial Information
**Start with last name:**
```
Doe
```
**Why:** Last names are more unique than first names

**Add first initial if too many results:**
```
J Doe
John D
```

### Handling Multiple Results

When your search returns multiple matches:

1. **Review the list** of matching users
2. **Check department** or **job title** for clues
3. **Verify email domain** if multiple domains exist
4. **Click on a user** to see full details
5. **Use the back button** to try a different match

**Tip:** Look for distinguishing information:
- Different departments
- Different office locations
- Different job titles

### Searching for Former Employees

**Disabled accounts** still appear in search results with status indicators:
- **Status: Disabled** badge
- **Account locked** indicator
- Grayed-out or warning colors

To find former employees:
1. Search by their name or email
2. Look for "Disabled" status
3. Check "Password Last Set" date for clues

**Note:** Disabled accounts may have limited information depending on retention policies.

## Understanding Results

### Result Layout

Search results appear in two cards:

```
┌─────────────────────────────────────┐
│ Azure AD / LDAP                     │
│ (Blue header with AD icon)          │
│                                      │
│ [Profile Photo]  Name               │
│                  Title, Department  │
│                  Contact Info       │
│                  Account Status     │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ Genesys Cloud                       │
│ (Orange header with Genesys icon)   │
│                                      │
│ Agent Information                   │
│ Skills and Queues                   │
│ Contact Information                 │
└─────────────────────────────────────┘
```

### Azure AD / LDAP Card

**Profile Information:**
- **Photo**: From Microsoft Graph (if available)
- **Name**: Display name from AD
- **Email**: Primary email address
- **Title**: Job title
- **Department**: Organizational department
- **Office Location**: Physical office or building

**Account Status Indicators:**

Status badges show account health:
- **✓ Enabled** (green): Account is active
- **✗ Disabled** (red): Account is disabled
- **🔒 Locked** (orange): Account is locked out
- **🔓 Not Locked** (green): Account is not locked

**Password Information:**
- **Password Last Set**: When password was changed
  - Format: "6Yr 8Mo ago" (relative time)
- **Password Expires**: When password will expire
  - Shows date or "Never" if non-expiring

**Phone Numbers:**

Each phone has:
- **Formatted number**: "+1 XXX-XXX-XXXX" for DIDs, "XXXX" for extensions
- **Type label**: DID, Ext, Cell Phone, Office, etc.
- **Service badge**: Teams, AD, or Legacy (colored)
- **Tooltip**: Hover to see source database fields

Example:
```
+1 918-749-1234  [Teams] DID
1234             [Genesys] Ext
+1 918-555-5678  [AD] Cell Phone
```

**Collapsible Sections:**

Click to expand:
- **AD Groups**: All Active Directory groups
- **Additional Information**: Extended attributes

### Genesys Cloud Card

Only appears if user is a Genesys agent.

**Agent Information:**
- **Name**: Agent display name in Genesys
- **Email**: Genesys email (may differ from AD)
- **Username**: Genesys username/login
- **Agent ID**: Unique Genesys identifier
- **Division**: Genesys organizational division
- **State**: Current agent state (active, inactive)

**Contact Center Details:**

**Skills** (collapsible):
- List of assigned skills
- Proficiency levels (if configured)
- Skill priorities

**Queues** (collapsible):
- Queues the agent can handle
- Queue priorities and routing

**Groups** (collapsible):
- Organizational groups
- Team assignments

**Locations:**
- Physical location
- Site information

**Contact Information:**
- Phone numbers from Genesys
- Extensions
- DIDs

### User Type Badges

Appears at the top of results:
- **Teams User** (blue): Has Teams/Office 365 phone system
- **Genesys User** (orange): Has Genesys Cloud agent account
- **Both**: Dual-system user

### Data Source Indicators

**Service Badges:**
- **Teams** (blue): Microsoft Teams/Office 365 data
- **Genesys** (orange): Genesys Cloud data
- **AD** (blue): Active Directory data
- **Legacy** (gray): Historical/deprecated data

**Hover tooltips** show exact field sources:
```
[AD] telephoneNumber
[AD] extensionAttribute4; [Genesys] primaryContactInfo[mediaType=PHONE].address
```

## Advanced Features

### Smart Data Merging

WhoDis automatically combines data from multiple sources:

**Priority Rules:**
1. **Microsoft Graph** data takes priority for enhanced fields
2. **LDAP** provides phone number classification logic
3. **Genesys** adds contact center-specific information

**Example:** If a user has:
- Teams DID from AD: `+1 918-749-1234`
- Genesys DID from Genesys: `+1 918-749-5678`
- Genesys Ext from both: `1234`

WhoDis shows:
```
+1 918-749-1234  [Teams] DID
+1 918-749-5678  [Genesys] DID
1234             [Genesys] Ext
```

### Phone Number Intelligence

**Automatic Formatting:**
- 10-digit → `+1 XXX-XXX-XXXX` (adds US country code)
- 11-digit (starts with 1) → `+1 XXX-XXX-XXXX`
- 4-digit → `XXXX` (treated as extension)
- Invalid → Preserved as-is

**Type Detection:**
- DIDs: 10/11-digit numbers
- Extensions: 4-digit numbers
- Mobile: From specific AD attributes or Graph API
- Office: Primary business lines

**Source Tracking:**
Every phone number shows:
- Service badge (where it came from)
- Type label (what kind of number)
- Tooltip with raw field name

### Cached Results

Search results are **cached for 30 minutes** to improve performance:

**Benefits:**
- Faster repeat searches
- Reduced load on backend systems
- Consistent results during troubleshooting

**Implications:**
- Recent changes may take up to 30 minutes to appear
- Force refresh: Hard refresh browser (Ctrl+Shift+R)
- Cache clears automatically after 30 minutes

**Cache indicator:**
Look for "Cached XX minutes ago" in results (if configured to show)

### Result Context

**Relative Dates:**
Dates are shown in human-readable format:
```
Password Last Set: 6Yr 8Mo ago
Last Logon: 2 days ago
Created: 3Yr 1Mo ago
```

**Absolute Dates:**
Hover over relative dates to see exact timestamp (if configured).

## Performance Tips

### Fast Searches

**Use specific search terms:**
- ✅ **Good**: `john.doe@example.com` (< 1 second)
- ⚠️ **Okay**: `John Doe` (1-2 seconds)
- ❌ **Slow**: `john` (2-3+ seconds, many results)

**Why?**
- Email searches are indexed and fast
- Partial name searches use wildcard matching
- More specific = faster and fewer results

### Search Best Practices

1. **Start with most specific term** you know (email > full name > partial name)
2. **Use full names** when possible instead of first name only
3. **Be patient** - multi-system searches take time (1-3 seconds is normal)
4. **Refine broad searches** - if too many results, add more details
5. **Try different formats** - "John Doe" vs "Doe, John" vs "john.doe"

### When Searches Are Slow

Normal search times:
- **< 1 second**: Email address lookups
- **1-2 seconds**: Full name searches, typical
- **2-3 seconds**: Partial name, high result count
- **> 5 seconds**: System issue, report to admin

If consistently slow (> 5 seconds):
1. Check your network connection
2. Try a different browser
3. Clear browser cache
4. Report to administrator

Administrators can check:
- API token expiration
- Database performance
- Network latency to identity providers

### Browser Tips

**Supported Browsers:**
- Chrome 90+ (recommended)
- Edge 90+
- Firefox 88+
- Safari 14+

**For Best Performance:**
- Keep browser updated
- Clear cache if experiencing issues
- Disable unnecessary browser extensions
- Use hard refresh (Ctrl+Shift+R) if results seem stale

**Mobile Browsers:**
WhoDis is mobile-responsive but optimized for desktop use.
- Works on iPhone Safari and Android Chrome
- Some features may be harder to access on small screens
- Consider using desktop for complex searches

## Interpreting Search Results

### No Results Found

If search returns no results:

**Check for:**
1. **Typos** in name or email
2. **Wrong domain** (using wrong email domain)
3. **Account doesn't exist** in Active Directory
4. **Recently created** account (< 30 minutes, cache may not be updated)
5. **Service accounts** (may not be searchable)

**Try:**
- Different search terms
- Different name formats
- Partial name instead of full name
- Just last name

**Still nothing?** Contact your administrator.

### Unexpected Results

**Multiple users with same name:**
- Common names may return many results
- Check department, location, or email domain to identify correct person

**Missing Genesys card:**
- User is not a Genesys agent
- Genesys account not created yet
- Genesys data not synchronized

**Missing profile photo:**
- User hasn't uploaded photo to Microsoft 365
- Photo sync not enabled
- Privacy settings may prevent photo access

**Disabled account:**
- Former employee
- Suspended account
- Pending deletion

### Data Discrepancies

**Different emails in AD and Genesys:**
- Systems may use different email formats
- Genesys may use username instead of email
- This is normal for some deployments

**Different phone numbers:**
- User may have multiple phone systems
- Teams users have different numbers than Genesys users
- Office moved → new number not synchronized yet

**Outdated information:**
- Data cached (< 30 minutes old)
- Source system not updated
- Synchronization delay between systems

## Common Search Scenarios

### Scenario 1: Finding a Colleague's Extension

**Goal:** Need to call John in Sales but only know first name

**Search:**
```
John
```

**Result:** 15 users named John

**Refine:**
```
John Sales
```
or narrow by last name if known

**Find:** Locate John from Sales department, note extension

### Scenario 2: Looking Up Phone Number for Directory

**Goal:** Need to add contact to company directory

**Search:**
```
jane.smith@example.com
```

**Result:** Single user found

**Extract:**
- DID: `+1 918-749-5678`
- Ext: `5678`
- Cell: `+1 918-555-1234`
- Title: "Customer Service Manager"
- Department: "Customer Service"

### Scenario 3: Verifying Account Status

**Goal:** User can't log in, check if account is locked

**Search:**
```
problematic.user@example.com
```

**Check:**
- **Status**: Enabled or Disabled?
- **Lock Status**: Locked or Not Locked?
- **Password Last Set**: Recent or months ago?

**Action:** Report findings to IT support

### Scenario 4: Finding Support Agent

**Goal:** Need to reach on-call support agent by name

**Search:**
```
Smith
```

**Filter:** Look for "Genesys User" badge (orange)

**Find:** Multiple Smiths, check department "Technical Support"

**Contact:** Use Genesys extension or phone number

## Accessibility Features

### Keyboard Navigation

- **Tab**: Move between search box and results
- **Enter**: Submit search
- **Esc**: Close modals
- **Arrow keys**: Navigate multiple results

### Screen Reader Support

WhoDis uses semantic HTML and ARIA labels for screen readers:
- Form labels
- Status indicators
- Section headings
- Interactive elements

### Visual Accessibility

- **High contrast**: Status badges with clear colors
- **Readable fonts**: Standard system fonts, adequate size
- **Scalable**: Works with browser zoom (100%-200%)
- **No color-only indicators**: Icons accompany colors

## Privacy and Compliance

### What Gets Logged

Every search is logged with:
- Your email address
- Search term
- Timestamp
- Results count
- IP address
- User agent (browser)

**Audit purpose:** Security monitoring and compliance

### Data Retention

- **Search results**: Cached 30 minutes, then refreshed
- **Audit logs**: Retained 90 days (configurable)
- **User data**: Synchronized from source systems

### Appropriate Use Policy

✅ **Appropriate:**
- Looking up colleagues for work tasks
- Finding contact information for projects
- Verifying account status for support
- Building internal directories

❌ **Inappropriate:**
- Personal curiosity about coworkers
- Bulk data collection without authorization
- Unauthorized access to sensitive information
- Using search data for non-work purposes

**Remember:** All searches may be reviewed by administrators.

## Getting Help

For search-related questions:
- **Documentation**: [Getting Started Guide](getting-started.md)
- **Admin Guide**: [Admin Tasks](admin-tasks.md)
- **Troubleshooting**: [Troubleshooting Guide](../troubleshooting.md)
- **IT Support**: Contact your help desk
- **System Admin**: Contact WhoDis administrators

---

*Last Updated: December 29, 2025*
