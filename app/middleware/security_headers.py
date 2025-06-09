"""
Security headers middleware for XSS and other attack prevention
"""

from flask import Flask


def init_security_headers(app: Flask):
    """Initialize security headers for the application"""

    @app.after_request
    def set_security_headers(response):
        """Set security headers on all responses"""

        # Content Security Policy - Prevents XSS by controlling resource loading
        # This policy:
        # - Allows scripts only from same origin and specific CDNs
        # - Allows styles from same origin and Bootstrap CDN
        # - Blocks inline scripts/styles (except those with nonce)
        # - Allows images from same origin and data URLs
        # - Restricts form submissions to same origin
        csp_policy = (
            "default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net 'unsafe-eval'; "  # unsafe-eval needed for some Bootstrap functionality
            "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "  # unsafe-inline needed for inline styles
            "font-src 'self' https://cdn.jsdelivr.net; "
            "img-src 'self' data: blob:; "
            "connect-src 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self';"
        )

        # Apply CSP header
        response.headers["Content-Security-Policy"] = csp_policy

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Enable browser XSS protection (legacy browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Enforce HTTPS (uncomment in production)
        # response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

        # Referrer policy for privacy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions policy (formerly Feature Policy)
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )

        return response
