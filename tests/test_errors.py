"""Mapping of HTTP statuses and error codes onto exception classes."""

from __future__ import annotations

import pytest

from conftest import error_body

from whagent import errors


@pytest.mark.parametrize("status,code,expected", [
    (401, 190, errors.AuthenticationError),
    (400, 100, errors.InvalidRequestError),
    (404, 100, errors.MediaNotFoundError),
    (400, 131009, errors.InvalidRequestError),
    (400, 131053, errors.MediaUploadError),
    (403, 131005, errors.ForbiddenError),
    (429, 130429, errors.RateLimitError),
    (503, 131016, errors.NotDeliveredError),
    (409, 1752041, errors.PollReplacedError),
    (500, 2, errors.ServerError),
])
def test_documented_codes_map_to_classes(status, code, expected):
    error = errors.error_from_response(status, error_body(code))

    assert isinstance(error, expected)
    assert error.code == code
    assert error.status == status
    assert error.fbtrace_id == "AW7bqWj4"


@pytest.mark.parametrize("status,expected", [
    (400, errors.InvalidRequestError),
    (401, errors.AuthenticationError),
    (403, errors.ForbiddenError),
    (404, errors.NotFoundError),
    (429, errors.RateLimitError),
    (500, errors.ServerError),
    (502, errors.ServerError),
])
def test_unknown_codes_fall_back_to_the_status(status, expected):
    assert isinstance(errors.error_from_response(status, {}), expected)


def test_media_upload_error_is_an_invalid_request():
    assert issubclass(errors.MediaUploadError, errors.InvalidRequestError)
    assert issubclass(errors.MediaNotFoundError, errors.NotFoundError)


def test_only_transient_failures_are_marked_retryable():
    retryable = (errors.RateLimitError, errors.NotDeliveredError, errors.ServerError)
    not_retryable = (errors.AuthenticationError, errors.InvalidRequestError,
                     errors.ForbiddenError, errors.PollReplacedError)

    assert all(cls.retryable for cls in retryable)
    assert not any(cls.retryable for cls in not_retryable)


def test_retry_after_is_read_from_the_header():
    error = errors.error_from_response(429, error_body(130429), {"Retry-After": "2.5"})

    assert error.retry_after == 2.5


def test_a_malformed_retry_after_is_ignored():
    error = errors.error_from_response(429, error_body(130429), {"Retry-After": "soon"})

    assert error.retry_after is None


def test_a_length_cap_rejection_carries_only_the_field_name():
    # The manual notes that error.message is the field name in this case.
    error = errors.error_from_response(400, {"error": {"message": "text.body", "code": 100}})

    assert isinstance(error, errors.InvalidRequestError)
    assert "text.body" in str(error)


def test_string_body_is_preserved_in_the_message():
    error = errors.error_from_response(502, "<html>bad gateway</html>")

    assert "bad gateway" in str(error)


def test_every_error_is_a_whagent_error():
    assert issubclass(errors.APIError, errors.WhagentError)
    assert issubclass(errors.ValidationError, errors.WhagentError)
    assert issubclass(errors.ValidationError, ValueError)
    assert issubclass(errors.TransportError, errors.WhagentError)
