from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from atlassian_cli.products.bitbucket.services.api import (
    ApiRequest,
    BitbucketApiService,
    normalize_api_endpoint,
)


@dataclass
class FakeResponse:
    payload: object | None = None
    content_type: str = "application/json"
    status_code: int = 200
    reason: str = "OK"
    headers: dict[str, str] = field(init=False)
    content: bytes = b""

    def __post_init__(self) -> None:
        self.headers = {"Content-Type": self.content_type}

    def json(self):
        if self.content_type != "application/json":
            raise ValueError("response is not JSON")
        return self.payload


class FakeProvider:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = iter(responses)
        self.calls: list[dict] = []

    def request_api(
        self,
        method,
        path,
        *,
        headers,
        params,
        json_body,
        data,
    ):
        self.calls.append(
            {
                "method": method,
                "path": path,
                "headers": headers,
                "params": params,
                "json_body": json_body,
                "data": data,
            }
        )
        return next(self.responses)


def make_request(
    *,
    endpoint: str = "projects/DEMO/repos/example-repo/compare/changes",
    method: str = "GET",
    headers: dict[str, str] | None = None,
    fields: dict[str, object] | None = None,
    input_body: bytes | None = None,
) -> ApiRequest:
    return ApiRequest(
        endpoint=endpoint,
        method=method,
        headers=headers or {},
        fields=fields
        or {
            "from": "feature/DEMO-1234/example-change",
            "to": "DEMO",
        },
        input_body=input_body,
    )


def test_normalize_api_endpoint_adds_default_api_root() -> None:
    assert (
        normalize_api_endpoint("projects/DEMO/repos/example-repo/compare/diff")
        == "rest/api/1.0/projects/DEMO/repos/example-repo/compare/diff"
    )


def test_normalize_api_endpoint_preserves_explicit_rest_root_and_query() -> None:
    assert (
        normalize_api_endpoint("/rest/build-status/1.0/commits/DEMO?limit=25")
        == "rest/build-status/1.0/commits/DEMO?limit=25"
    )


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://bitbucket.example.com/rest/api/1.0/projects/DEMO",
        "//bitbucket.example.com/rest/api/1.0/projects/DEMO",
        "graphql",
    ],
)
def test_normalize_api_endpoint_rejects_unsafe_or_unsupported_endpoint(endpoint: str) -> None:
    with pytest.raises(ValueError):
        normalize_api_endpoint(endpoint)


def test_api_service_sends_get_fields_as_query_parameters() -> None:
    provider = FakeProvider([FakeResponse()])
    service = BitbucketApiService(provider)

    responses = list(service.iter_responses(make_request(), paginate=False))

    assert len(responses) == 1
    assert provider.calls == [
        {
            "method": "GET",
            "path": "rest/api/1.0/projects/DEMO/repos/example-repo/compare/changes",
            "headers": {"Accept": "*/*"},
            "params": {
                "from": "feature/DEMO-1234/example-change",
                "to": "DEMO",
            },
            "json_body": None,
            "data": None,
        }
    ]


def test_api_service_sends_non_get_fields_as_json() -> None:
    provider = FakeProvider([FakeResponse()])
    service = BitbucketApiService(provider)

    list(service.iter_responses(make_request(method="POST"), paginate=False))

    assert provider.calls[0]["params"] is None
    assert provider.calls[0]["json_body"] == {
        "from": "feature/DEMO-1234/example-change",
        "to": "DEMO",
    }
    assert provider.calls[0]["headers"] == {
        "Accept": "*/*",
        "Content-Type": "application/json; charset=utf-8",
    }


def test_api_service_sends_input_body_unchanged_and_fields_as_query() -> None:
    provider = FakeProvider([FakeResponse()])
    service = BitbucketApiService(provider)

    list(
        service.iter_responses(
            make_request(method="PATCH", input_body=b"example response"),
            paginate=False,
        )
    )

    assert provider.calls[0]["params"] == {
        "from": "feature/DEMO-1234/example-change",
        "to": "DEMO",
    }
    assert provider.calls[0]["json_body"] is None
    assert provider.calls[0]["data"] == b"example response"


def test_api_service_preserves_explicit_accept_and_content_type_headers() -> None:
    provider = FakeProvider([FakeResponse()])
    service = BitbucketApiService(provider)

    list(
        service.iter_responses(
            make_request(
                method="POST",
                headers={
                    "accept": "application/json",
                    "content-type": "application/example",
                },
            ),
            paginate=False,
        )
    )

    assert provider.calls[0]["headers"] == {
        "accept": "application/json",
        "content-type": "application/example",
    }


def test_api_service_paginates_with_limit_and_next_page_start() -> None:
    provider = FakeProvider(
        [
            FakeResponse(
                {
                    "size": 1,
                    "limit": 100,
                    "isLastPage": False,
                    "nextPageStart": 100,
                    "values": [{"id": "DEMO-1"}],
                    "start": 0,
                }
            ),
            FakeResponse(
                {
                    "size": 1,
                    "limit": 100,
                    "isLastPage": True,
                    "values": [{"id": "DEMO-1234"}],
                    "start": 100,
                }
            ),
        ]
    )
    service = BitbucketApiService(provider)

    responses = list(service.iter_responses(make_request(), paginate=True))

    assert len(responses) == 2
    assert provider.calls[0]["params"] == {
        "from": "feature/DEMO-1234/example-change",
        "to": "DEMO",
        "limit": 100,
    }
    assert provider.calls[1]["params"] == {
        "from": "feature/DEMO-1234/example-change",
        "to": "DEMO",
        "limit": 100,
        "start": 100,
    }


def test_api_service_preserves_user_limit_from_endpoint() -> None:
    provider = FakeProvider(
        [FakeResponse({"size": 0, "limit": 25, "isLastPage": True, "values": []})]
    )
    service = BitbucketApiService(provider)

    list(
        service.iter_responses(
            make_request(endpoint="projects/DEMO/repos/example-repo/compare/changes?limit=25"),
            paginate=True,
        )
    )

    assert provider.calls[0]["path"].endswith("?limit=25")
    assert "limit" not in provider.calls[0]["params"]


@pytest.mark.parametrize(
    "response",
    [
        FakeResponse({"values": [{"id": "DEMO"}]}),
        FakeResponse(None, content_type="text/plain"),
    ],
)
def test_api_service_stops_when_response_is_not_a_standard_page(response: FakeResponse) -> None:
    provider = FakeProvider([response])

    responses = list(BitbucketApiService(provider).iter_responses(make_request(), paginate=True))

    assert responses == [response]
    assert len(provider.calls) == 1


@pytest.mark.parametrize(
    "pages",
    [
        [FakeResponse({"isLastPage": False, "values": []})],
        [
            FakeResponse({"isLastPage": False, "nextPageStart": 100, "values": []}),
            FakeResponse({"isLastPage": False, "nextPageStart": 100, "values": []}),
        ],
        [
            FakeResponse({"isLastPage": False, "nextPageStart": 100, "values": []}),
            FakeResponse({"isLastPage": False, "nextPageStart": 50, "values": []}),
        ],
    ],
)
def test_api_service_rejects_missing_or_non_advancing_next_page(pages) -> None:
    provider = FakeProvider(pages)

    with pytest.raises(ValueError, match="nextPageStart"):
        list(BitbucketApiService(provider).iter_responses(make_request(), paginate=True))


def test_api_service_rejects_non_get_pagination_before_request() -> None:
    provider = FakeProvider([])

    with pytest.raises(ValueError, match="non-GET"):
        list(
            BitbucketApiService(provider).iter_responses(
                make_request(method="POST"),
                paginate=True,
            )
        )

    assert provider.calls == []
