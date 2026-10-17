"""Routing failures exercised at both the HTTP boundary and the Trips API."""

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest


@pytest.fixture(
    params=[
        "invalid-json",
        "list",
        "null",
        "missing-id",
        "missing-distance",
        "missing-duration",
        "wrong-id",
        "id-type",
        "http-error",
        "timeout",
        *[
            f"{field}:{value}"
            for field in ("distanceMeters", "durationSeconds")
            for value in ("negative", "string", "float", "bool", "null", "object", "overflow")
        ],
    ]
)
def routing_failure(request: pytest.FixtureRequest) -> Callable[[httpx.Request], httpx.Response]:
    case = request.param

    def handler(message: httpx.Request) -> httpx.Response:
        if case == "timeout":
            raise httpx.ReadTimeout("Routing timed out", request=message)
        if case == "http-error":
            return httpx.Response(503)
        if case == "invalid-json":
            return httpx.Response(200, content=b"not JSON")
        if case == "list":
            return httpx.Response(200, json=[])
        if case == "null":
            return httpx.Response(200, content=b"null")
        data: dict[str, Any] = {
            "tripId": json.loads(message.content)["tripId"],
            "distanceMeters": 6000,
            "durationSeconds": 900,
        }
        missing = {
            "missing-id": "tripId",
            "missing-distance": "distanceMeters",
            "missing-duration": "durationSeconds",
        }
        if case in missing:
            del data[missing[case]]
        elif case == "wrong-id":
            data["tripId"] = "00000000-0000-0000-0000-000000000000"
        elif case == "id-type":
            data["tripId"] = 12
        else:
            field, value = case.split(":")
            data[field] = {
                "negative": -1,
                "string": "123",
                "float": 1.5,
                "bool": True,
                "null": None,
                "object": {},
                "overflow": 2**31,
            }[value]
        return httpx.Response(200, json=data)

    return handler
