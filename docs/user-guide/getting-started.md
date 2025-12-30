# Getting Started with WhoDis

Welcome to WhoDis! This guide will help you get started with using the identity lookup service.

## What is WhoDis?

WhoDis is an enterprise identity search platform that provides unified search across multiple identity providers:
- **Active Directory** (LDAP) - Corporate directory
- **Microsoft Graph** (Azure AD) - Enhanced user profiles and photos
- **Genesys Cloud** - Contact center data

## Accessing WhoDis

### Login

1. Navigate to your WhoDis URL (e.g., `https://whodis.example.com`)
2. You'll be automatically redirected to **Azure AD login**
3. Sign in with your corporate credentials
4. After successful login, you'll see the search interface

**Note:** WhoDis uses Azure AD Single Sign-On (SSO). Your corporate account must have access to WhoDis to log in.

### First-Time Login

When you log in for the first time:
1. WhoDis automatically creates your user account
2. You're assigned a default role (typically "Viewer")
3. Your session begins with a 15-minute timeout

If you need different permissions, contact your WhoDis administrator to update your role.

## Understanding User Roles

WhoDis has three user roles with different permissions:

### Viewer
- **Can**: Search for users, view search results
- **Cannot**: Make changes, access admin functions
- **Use for**: Regular users who need to look up contact information

### Editor
- **Can**: Everything Viewer can do, plus edit certain data (e.g., blocked numbers)
- **Cannot**: Manage users, change configuration
- **Use for**: Help desk staff who need to make operational changes

### Admin
- **Can**: Everything Editor can do, plus full system administration
- **Access**: User management, configuration, audit logs, job role compliance
- **Use for**: System administrators and compliance officers

You can see your current role in the top right corner of the interface.

## Interface Overview

### Header

```
┌─────────────────────────────────────────────────────────────┐
│ WhoDis Logo          [Search Box]         user@example.com ▼│
└─────────────────────────────────────────────────────────────┘
```

- **Logo**: Click to return to home page
- **Search Box**: Always visible for quick searches
- **User Menu**: Your email with dropdown for Logout/Admin (if admin)

### Navigation Menu

- **Home**: Search interface (default landing page)
- **Admin**: System administration (admin role only)
  - Users: Manage user accounts and roles
  - Configuration: System settings
  - Audit Logs: View all system activity
  - Cache: API token and cache management
  - Job Role Compliance: Manage role mappings (if enabled)
- **Utilities**: Additional tools (editor/admin only)
  - Blocked Numbers: Manage Genesys blocked numbers

## Your First Search

Let's search for a user:

1. **Enter search term** in the search box
   - Email address: `john.doe@example.com`
   - Name: `John Doe`
   - Username: `jdoe`
   - Partial name: `john` (will search all fields)

2. **Click "Search" or press Enter**

3. **View results** - You'll see two main sections:
   - **Azure AD / LDAP**: Corporate directory information
   - **Genesys Cloud**: Contact center data (if user exists)

4. **Review user information**:
   - Profile photo (if available)
   - Contact information (phone numbers, email)
   - Account status and details
   - Department and location information

## Understanding Search Results

### Azure AD / LDAP Card (Blue)

Shows information from your corporate directory:

**Basic Information:**
- Name and email address
- Job title and department
- Office location
- Profile photo from Microsoft Graph

**Account Status:**
- **Enabled/Disabled**: Account status
- **Locked/Not Locked**: Security lockout status
- **Password Last Set**: When password was changed
- **Password Expires**: When password will expire

**Contact Information:**
- **DID** (Direct Inward Dial): Direct phone number
- **Ext** (Extension): Internal extension
- **Cell Phone**: Mobile number
- **Office**: Office phone

Each phone number has a badge showing its source:
- **Blue "Teams"**: Microsoft Teams/Office 365
- **Blue "AD"**: Active Directory
- **Gray "Legacy"**: Historical data

**Hover over badges** to see which database fields provide each number.

### Genesys Cloud Card (Orange)

Shows contact center information (if user is a Genesys agent):

**Agent Information:**
- Genesys username and ID
- Agent status and state
- Department and title

**Contact Center Details:**
- **Skills**: Agent's assigned skills and proficiency
- **Queues**: Which queues the agent handles
- **Groups**: Organizational groups
- **Location**: Physical location

**Contact Information:**
- Phone numbers with Genesys data
- Extension information

### User Type Badges

Users may have badges indicating their system access:
- **Blue "Teams User"**: Has Microsoft Teams phone number
- **Orange "Genesys User"**: Has Genesys contact center access
- **Both badges**: Dual user with access to both systems

## Multiple Results

If your search matches multiple users, you'll see:

1. **Result count**: "Found 5 matching users"
2. **Selection list**: Click on the user you want to view
3. **Preview**: Each result shows name, email, department
4. **Full details**: Click to see complete information

**Tip:** Use more specific search terms (full email or last name) to reduce multiple matches.

## Search Tips

### Effective Searching

**Email addresses** (most specific):
```
john.doe@example.com
```

**Full names** (good specificity):
```
John Doe
Doe, John
```

**Partial names** (may return multiple results):
```
John
Doe
```

**Usernames** (if known):
```
jdoe
john.doe
```

### What You Can Search For

WhoDis searches these fields:
- Email addresses
- First and last names
- Display names
- Usernames/SAM account names
- Employee IDs (if configured)

### Search Best Practices

1. **Start specific**: Use email address when you know it
2. **Use last name**: More unique than first name
3. **Try different formats**: "John Doe" vs "Doe, John"
4. **Be patient**: Searches across multiple systems take 1-3 seconds
5. **Check spelling**: Typos will return no results

## Understanding Phone Numbers

WhoDis displays phone numbers with consistent formatting:

### Phone Number Format

**DIDs** (Direct numbers):
```
+1 918-749-1234  [Teams] DID
```

**Extensions**:
```
1234  [Genesys] Ext
```

### Phone Number Types

- **DID**: Direct Inward Dial number (external callers can dial directly)
- **Ext**: Extension (internal-only, usually 4 digits)
- **Cell Phone**: Mobile number
- **Office**: General office line
- **Business**: Primary business number

### Service Badges

Colored badges show where each number comes from:
- **Teams** (blue): Microsoft Teams/Office 365 number
- **Genesys** (orange): Genesys Cloud contact center
- **AD** (blue): Active Directory data
- **Legacy** (gray): Historical/deprecated systems

**Hover over badges** to see the exact database field providing that number.

## Session Management

### Session Timeout

For security, your session will expire after **15 minutes of inactivity**.

**Inactivity** means no:
- Mouse movement
- Keyboard input
- Scrolling
- Clicking

### Timeout Warning

**2 minutes before timeout**, you'll see a warning modal:
```
┌─────────────────────────────────────┐
│ Session Expiring Soon              │
│                                     │
│ Your session will expire in:        │
│          01:45                      │
│                                     │
│ [Extend Session]     [Logout]      │
└─────────────────────────────────────┘
```

**Actions:**
- **Extend Session**: Resets timeout, keeps you logged in
- **Logout**: Immediately ends your session
- **Do nothing**: Automatic logout when timer reaches 0:00

### Activity Tracking

These actions reset the timeout:
- Moving your mouse
- Typing on keyboard
- Scrolling the page
- Clicking anywhere

**Tip:** If you're reading results without interacting, the timeout will still count down. Move your mouse occasionally to stay active.

### Manual Logout

To log out manually:
1. Click your email in the top right
2. Select "Logout" from dropdown
3. You'll be returned to the login page

## Privacy and Security

### What Gets Logged

WhoDis logs all searches for **security and audit purposes**:
- Your email address
- Search term used
- Timestamp
- Results found
- IP address

**Administrators can view** all searches in the audit log.

### Appropriate Use

WhoDis should be used for:
- ✅ Looking up colleagues for business purposes
- ✅ Finding contact information for work tasks
- ✅ Verifying account status for support tickets
- ✅ Checking phone numbers for internal directories

WhoDis should **NOT** be used for:
- ❌ Personal curiosity about coworkers
- ❌ Gathering data for non-work purposes
- ❌ Bulk downloading contact information
- ❌ Any unauthorized access or data collection

**Your searches may be reviewed.** Use WhoDis responsibly and for legitimate business purposes only.

### Data Accuracy

Search results are cached for **30 minutes** for performance. This means:
- Recent changes (< 30 min) might not appear immediately
- Phone number updates may take up to 30 minutes to show
- Account status changes reflect within 30 minutes

For the most current data, wait 30+ minutes after changes are made.

## Getting Help

### Common Questions

**Q: Why can't I find a user I know exists?**
- Verify spelling of name/email
- Try different search terms (email, last name, username)
- Check if user account is in Active Directory
- Contact your administrator if issue persists

**Q: Why are phone numbers missing?**
- User may not have phone numbers assigned
- Numbers may not be synchronized from source systems
- Genesys users need to be provisioned in Genesys Cloud

**Q: Why is my session expiring so quickly?**
- Session timeout is 15 minutes (configurable by admin)
- Any mouse movement resets the timer
- Contact admin if timeout is too short for your workflow

**Q: Can I export search results?**
- Export functionality is in development
- Currently, you can manually copy information needed
- Contact admin about bulk export requirements

### Reporting Issues

If you encounter problems:

1. **Note the details**:
   - What you were trying to do
   - What happened instead
   - Any error messages
   - Screenshot if helpful

2. **Contact support**:
   - Email your IT helpdesk
   - Include your WhoDis username (email)
   - Include timestamp of issue
   - Describe steps to reproduce

3. **For urgent issues**:
   - Contact your system administrator
   - Provide error details
   - Mention if it's blocking critical work

## Next Steps

Now that you know the basics, explore more features:

- **[Search Guide](search.md)**: Advanced search techniques and tips
- **[Admin Guide](admin-tasks.md)**: For administrators (requires admin role)
- **[Troubleshooting](../troubleshooting.md)**: Common issues and solutions

---

*Last Updated: December 29, 2025*
