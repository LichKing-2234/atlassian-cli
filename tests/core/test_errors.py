import pytest

from atlassian_cli.core.errors import NotFoundError, TransportError, exit_code_for_error
from atlassian_cli.core.exit_codes import EXIT_NETWORK, EXIT_NOT_FOUND, EXIT_UNKNOWN


def test_not_found_error_maps_to_exit_code_four() -> None:
    assert exit_code_for_error(NotFoundError("missing")) == EXIT_NOT_FOUND


def test_transport_error_maps_to_network_exit_code() -> None:
    assert exit_code_for_error(TransportError("timed out")) == EXIT_NETWORK


def test_unknown_error_maps_to_unknown_exit_code() -> None:
    assert exit_code_for_error(RuntimeError("boom")) == EXIT_UNKNOWN


def test_main_reports_cli_errors_without_traceback(monkeypatch, capsys) -> None:
    from atlassian_cli import main as main_module

    def raise_cli_error() -> None:
        raise TransportError("Jira issue response was not JSON")

    monkeypatch.setattr(main_module, "app", raise_cli_error)

    with pytest.raises(SystemExit) as exc_info:
        main_module.main()

    assert exc_info.value.code == EXIT_NETWORK
    captured = capsys.readouterr()
    assert captured.err == "Error: Jira issue response was not JSON\n"
