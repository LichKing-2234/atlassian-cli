import json
from pathlib import Path

CONTRACT_PATH = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "gh-v2.96.0"
    / "bitbucket-pr-read-contract.json"
)


def load_contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text())


def test_pr_read_contract_has_fixed_baselines() -> None:
    assert load_contract()["baseline"] == {
        "bitbucket": "6.7.2",
        "gh": "2.96.0",
        "gh_commit": "b300f2ec7ec9dc9addc39b2ad88c54097ded7ca0",
    }


def test_pr_read_contract_status_sets_are_consistent() -> None:
    contract = load_contract()
    accepted = set(contract["json_fields"])
    blocked = set(contract["blocked_json_fields"])
    assert len(accepted) == 36
    assert blocked <= accepted
    assert set(contract["excluded_options"]).isdisjoint(contract["commands"]["list"]["options"])
    assert set(contract["deferred_options"]).isdisjoint(contract["commands"]["list"]["options"])
    assert set(contract["deferred_options"]).isdisjoint(contract["commands"]["view"]["options"])


def test_pr_read_contract_keeps_only_documented_blockers() -> None:
    assert load_contract()["blocked_json_fields"] == {
        "latestReviews": "B30",
        "mergeCommit": "B31",
        "potentialMergeCommit": "B25",
        "reviews": "B30",
    }


def test_web_and_json_match_the_pinned_oracle_conflict() -> None:
    assert load_contract()["errors"]["web_json"] == "cannot use `--web` with `--json`"
