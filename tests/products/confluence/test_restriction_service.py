from atlassian_cli.products.confluence.services.restriction import RestrictionService


class FakeRestrictionProvider:
    def get_page_restrictions(self, page_id: str) -> dict:
        assert page_id == "1234"
        return {
            "read": {
                "restrictions": {
                    "user": {"results": [{"username": "~example-user"}]},
                    "group": {"results": [{"name": "reviewer-one"}]},
                }
            },
            "update": {
                "restrictions": {
                    "user": {"results": [{"name": "example-user-id"}]},
                    "group": {"results": [{"name": "reviewer-two"}]},
                }
            },
        }


def test_restriction_service_get_normalizes_view_and_edit_subjects() -> None:
    service = RestrictionService(provider=FakeRestrictionProvider())

    assert service.get("1234") == {
        "read": {"users": ["~example-user"], "groups": ["reviewer-one"]},
        "update": {"users": ["example-user-id"], "groups": ["reviewer-two"]},
    }
