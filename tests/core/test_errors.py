from atlassian_cli.core.errors import NotFoundError, exit_code_for_error


def test_not_found_error_maps_to_exit_code_four() -> None:
    assert exit_code_for_error(NotFoundError("missing")) == 4
