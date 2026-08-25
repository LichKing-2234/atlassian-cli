import pytest

from atlassian_cli.products.jira.services.link import IssueLinkService

LINK_TYPE = {
    "id": "10000",
    "name": "Cloners",
    "inward": "is cloned by",
    "outward": "clones",
}


def issue_link(
    *,
    link_id: str = "10001",
    direction: str = "outward",
    other_issue: str = "DEMO-1234",
) -> dict:
    return {
        "id": link_id,
        "type": LINK_TYPE,
        f"{direction}Issue": {
            "key": other_issue,
            "fields": {"summary": "Example issue summary"},
        },
    }


class FakeLinkProvider:
    def __init__(self, links: list[dict] | None = None) -> None:
        self.links = list(links or [])
        self.created_payloads: list[dict] = []
        self.deleted_ids: list[str] = []

    def get_issue_link_types(self) -> list[dict]:
        return [LINK_TYPE]

    def list_issue_links(self, issue_key: str) -> list[dict]:
        return self.links

    def create_issue_link(self, data: dict) -> None:
        self.created_payloads.append(data)
        self.links.append(issue_link())

    def delete_issue_link(self, link_id: str) -> None:
        self.deleted_ids.append(link_id)


def test_issue_link_service_normalizes_both_directions() -> None:
    outward_service = IssueLinkService(FakeLinkProvider([issue_link()]))
    inward_service = IssueLinkService(
        FakeLinkProvider([issue_link(direction="inward", other_issue="DEMO-1")])
    )

    outward = outward_service.list("DEMO-1")["results"][0]
    inward = inward_service.list("DEMO-1234")["results"][0]

    assert outward == {
        "id": "10001",
        "type": "Cloners",
        "inward": "is cloned by",
        "outward": "clones",
        "inward_issue": "DEMO-1",
        "outward_issue": "DEMO-1234",
        "direction": "outward",
        "relationship": "clones",
        "linked_issue": {"key": "DEMO-1234", "summary": "Example issue summary"},
    }
    assert inward["inward_issue"] == "DEMO-1"
    assert inward["outward_issue"] == "DEMO-1234"
    assert inward["direction"] == "inward"
    assert inward["relationship"] == "is cloned by"


def test_issue_link_service_create_sends_direction_and_reads_link_back() -> None:
    provider = FakeLinkProvider()
    service = IssueLinkService(provider)

    result = service.create(
        inward_issue="DEMO-1",
        outward_issue="DEMO-1234",
        link_type="Cloners",
        comment="example comment",
        comment_visibility={"type": "group", "value": "reviewer-one"},
    )

    assert result["status"] == "created"
    assert result["created"] is True
    assert result["link"]["id"] == "10001"
    assert provider.created_payloads == [
        {
            "type": {"name": "Cloners"},
            "inwardIssue": {"key": "DEMO-1"},
            "outwardIssue": {"key": "DEMO-1234"},
            "comment": {
                "body": "example comment",
                "visibility": {"type": "group", "value": "reviewer-one"},
            },
        }
    ]


def test_issue_link_service_identical_link_is_deterministic() -> None:
    provider = FakeLinkProvider([issue_link()])
    service = IssueLinkService(provider)

    result = service.create(
        inward_issue="DEMO-1",
        outward_issue="DEMO-1234",
        link_type="Cloners",
    )

    assert result == {
        "status": "existing",
        "created": False,
        "link": service.list("DEMO-1")["results"][0],
    }
    assert provider.created_payloads == []


def test_issue_link_service_raw_create_preserves_composed_responses() -> None:
    service = IssueLinkService(FakeLinkProvider())

    result = service.create_raw(
        inward_issue="DEMO-1",
        outward_issue="DEMO-1234",
        link_type="Cloners",
    )

    assert result["create_response"] is None
    assert result["link_type_response"] == [LINK_TYPE]
    assert result["issue_link_response"] == [issue_link()]
    assert result["link"] == issue_link()


def test_issue_link_service_rejects_unknown_type_before_create() -> None:
    provider = FakeLinkProvider()
    service = IssueLinkService(provider)

    with pytest.raises(ValueError, match="Unknown Jira issue link type.*Cloners"):
        service.create(
            inward_issue="DEMO-1",
            outward_issue="DEMO-1234",
            link_type="Unknown",
        )

    assert provider.created_payloads == []


def test_issue_link_service_rejects_ambiguous_readback() -> None:
    class AmbiguousProvider(FakeLinkProvider):
        def create_issue_link(self, data: dict) -> None:
            self.links.extend([issue_link(link_id="10001"), issue_link(link_id="10002")])

    service = IssueLinkService(AmbiguousProvider())

    with pytest.raises(RuntimeError, match="read-back was ambiguous"):
        service.create(
            inward_issue="DEMO-1",
            outward_issue="DEMO-1234",
            link_type="Cloners",
        )


def test_issue_link_service_lists_types_and_deletes() -> None:
    provider = FakeLinkProvider()
    service = IssueLinkService(provider)

    assert service.types() == {"results": [LINK_TYPE]}
    assert service.delete("10001") == {"id": "10001", "deleted": True}
    assert provider.deleted_ids == ["10001"]


def test_issue_link_service_filters_types_case_insensitively() -> None:
    class MultipleTypeProvider(FakeLinkProvider):
        def get_issue_link_types(self) -> list[dict]:
            return [LINK_TYPE, {"id": "10002", "name": "Blocks"}]

    service = IssueLinkService(MultipleTypeProvider())

    assert service.types(name_filter="clone") == {"results": [LINK_TYPE]}
    assert service.types_raw(name_filter="CLONE") == [LINK_TYPE]
