"""Marshmallow schemas for REST API request/response serialization.

Defines the D-04 envelope format and all response shapes used
by the API endpoints.
"""

from marshmallow import Schema, fields


class MetaSchema(Schema):
    """Pagination metadata."""

    page = fields.Integer()
    page_size = fields.Integer()
    total = fields.Integer()


class ErrorDetailSchema(Schema):
    """Single error detail within the D-07 error envelope."""

    code = fields.String(required=True)
    message = fields.String(required=True)
    details = fields.Dict(keys=fields.String(), values=fields.Raw())


class SearchResultItemSchema(Schema):
    """A single search result entry."""

    email = fields.String()
    display_name = fields.String()
    department = fields.String()
    title = fields.String()
    source = fields.String()


class SearchQuerySchema(Schema):
    """Query parameters for the search endpoint."""

    q = fields.String(required=True)
    page = fields.Integer(load_default=1)
    page_size = fields.Integer(load_default=25)


class SearchResponseSchema(Schema):
    """D-04 envelope for search results."""

    data = fields.List(fields.Nested(SearchResultItemSchema))
    meta = fields.Nested(MetaSchema)
    errors = fields.List(
        fields.Nested(ErrorDetailSchema), load_default=None
    )


class ProfileResponseSchema(Schema):
    """D-04 envelope for a single profile."""

    data = fields.Dict(keys=fields.String(), values=fields.Raw())
    meta = fields.Nested(MetaSchema)
    errors = fields.List(
        fields.Nested(ErrorDetailSchema), load_default=None
    )


class ErrorResponseSchema(Schema):
    """Top-level error response (D-07 format)."""

    error = fields.Nested(ErrorDetailSchema)
