from atlassian_cli.models.base import ApiModel, TimestampMixin


class DemoModel(ApiModel):
    id: str
    name: str
    optional: str | None = None

    @classmethod
    def from_api_response(cls, data, **kwargs):
        return cls(id=str(data["id"]), name=data["name"], optional=data.get("optional"))


def test_api_model_to_simplified_dict_excludes_none() -> None:
    model = DemoModel.from_api_response({"id": 7, "name": "demo"})

    assert model.to_simplified_dict() == {"id": "7", "name": "demo"}


def test_timestamp_mixin_formats_server_timestamp() -> None:
    formatted = TimestampMixin.format_timestamp("2026-04-23T09:15:00.000+0000")

    assert formatted == "2026-04-23 09:15:00"
