/**
 * Search Utility Functions
 * Common utilities for phone number formatting, date formatting, etc.
 */

// Format phone numbers consistently
function formatPhoneNumber(phone) {
    if (!phone) return phone;

    // Remove all non-digits
    const cleaned = phone.replace(/\D/g, '');

    // If it's a 4-digit extension, leave it as is
    if (cleaned.length === 4) {
        return cleaned;
    }

    // Handle 10-digit numbers (add US country code)
    if (cleaned.length === 10) {
        return `+1 ${cleaned.substr(0, 3)}-${cleaned.substr(3, 3)}-${cleaned.substr(6, 4)}`;
    }

    // Handle 11-digit numbers starting with 1
    if (cleaned.length === 11 && cleaned.startsWith('1')) {
        return `+1 ${cleaned.substr(1, 3)}-${cleaned.substr(4, 3)}-${cleaned.substr(7, 4)}`;
    }

    // Handle numbers that already have country code
    if (cleaned.length === 11) {
        return `+${cleaned.substr(0, 1)} ${cleaned.substr(1, 3)}-${cleaned.substr(4, 3)}-${cleaned.substr(7, 4)}`;
    }

    // For any other format, try to parse what we can
    if (cleaned.length > 10) {
        const countryCode = cleaned.substr(0, cleaned.length - 10);
        const areaCode = cleaned.substr(-10, 3);
        const prefix = cleaned.substr(-7, 3);
        const lineNumber = cleaned.substr(-4, 4);
        return `+${countryCode} ${areaCode}-${prefix}-${lineNumber}`;
    }

    // Return original if we can't format it
    return phone;
}

// Format date information with smart relative time display
function formatDateInfo(dateValue, label, showDaysInfo = true) {
    if (!dateValue) return null;

    const date = new Date(dateValue);
    const now = new Date();

    // Format date as M/D/YYYY
    const dateStr = `${date.getMonth() + 1}/${date.getDate()}/${date.getFullYear()}`;

    // Format time in 24-hour format without seconds
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    const timeStr = `${hours}:${minutes}`;

    // Calculate smart date difference
    let daysInfo = '';
    let daysClass = '';
    if (showDaysInfo) {
        // Calculate time difference in milliseconds
        const timeDiff = date - now;
        const msPerDay = 1000 * 60 * 60 * 24;

        // Check if dates are on the same day
        const dateDay = date.toDateString();
        const nowDay = now.toDateString();
        const isToday = dateDay === nowDay;

        // Calculate difference in days (use ceil for past dates to avoid -0 days)
        const daysDiff = timeDiff < 0 ? Math.ceil(timeDiff / msPerDay) : Math.floor(timeDiff / msPerDay);
        const absDays = Math.abs(daysDiff);

        // For very recent dates, show hours
        const absHours = Math.abs(timeDiff) / (1000 * 60 * 60);

        // Calculate years, months, and remaining days
        const years = Math.floor(absDays / 365);
        const months = Math.floor((absDays % 365) / 30);
        const days = absDays % 30;

        // Build the string based on what's significant - use abbreviated units
        let parts = [];
        if (isToday) {
            // Same day - show as "Today" or hours if very recent
            if (absHours < 1) {
                const minutes = Math.floor(Math.abs(timeDiff) / (1000 * 60));
                parts.push(`${minutes}m`);
            } else if (absHours < 24) {
                parts.push(`${Math.floor(absHours)}h`);
            }
        } else if (years > 0) {
            parts.push(`${years}Yr`);
            if (months > 0) {
                parts.push(`${months}Mo`);
            }
        } else if (months > 0) {
            parts.push(`${months}Mo`);
            if (days > 0 && months < 3) {
                parts.push(`${days}d`);
            }
        } else if (absDays > 0) {
            parts.push(`${absDays}d`);
        }

        // Format based on past or future
        if (timeDiff < 0) {
            daysInfo = isToday ? (parts.length > 0 ? parts.join(' ') + ' ago' : 'Today') : parts.join(' ') + ' ago';
        } else if (isToday) {
            daysInfo = parts.length > 0 ? 'in ' + parts.join(' ') : 'Today';
        } else {
            daysInfo = 'in ' + parts.join(' ');
            // Add color classes for expiration warnings
            if (label.includes('Expires')) {
                if (daysDiff < 7) daysClass = 'text-danger';
                else if (daysDiff < 30) daysClass = 'text-warning';
            }
        }
    }

    return { label, dateStr, timeStr, daysInfo, daysClass };
}

// Note: getCSRFToken() is now provided by security-utils.js which is loaded before this script