from atlassian_cli.core.errors import NotFoundError, TransportError, exit_code_for_error
from atlassian_cli.core.exit_codes import EXIT_NETWORK, EXIT_NOT_FOUND, EXIT_UNKNOWN


def test_not_found_error_maps_to_exit_code_four() -> None:
    assert exit_code_for_error(NotFoundError("missing")) == EXIT_NOT_FOUND


def test_transport_error_maps_to_network_exit_code() -> None:
    assert exit_code_for_error(TransportError("timed out")) == EXIT_NETWORK


def test_unknown_error_maps_to_unknown_exit_code() -> None:
    assert exit_code_for_error(RuntimeError("boom")) == EXIT_UNKNOWN
