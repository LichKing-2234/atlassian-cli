from atlassian_cli.products.bitbucket.diff import normalize_pull_request_diff


def test_normalize_pull_request_diff_builds_comment_anchors() -> None:
    raw = {
        "values": [
            {
                "destination": {"toString": "example.py"},
                "hunks": [
                    {
                        "sourceLine": 10,
                        "sourceSpan": 1,
                        "destinationLine": 10,
                        "destinationSpan": 2,
                        "segments": [
                            {
                                "type": "CONTEXT",
                                "lines": [
                                    {
                                        "source": 10,
                                        "destination": 10,
                                        "line": " unchanged",
                                    }
                                ],
                            },
                            {
                                "type": "ADDED",
                                "lines": [
                                    {
                                        "destination": 11,
                                        "line": "+example response",
                                    }
                                ],
                            },
                            {
                                "type": "REMOVED",
                                "lines": [
                                    {
                                        "source": 12,
                                        "line": "-example comment",
                                    }
                                ],
                            },
                        ],
                    }
                ],
            }
        ]
    }

    result = normalize_pull_request_diff(42, raw)

    assert result == {
        "id": 42,
        "files": [
            {
                "path": "example.py",
                "hunks": [
                    {
                        "source_start": 10,
                        "source_span": 1,
                        "destination_start": 10,
                        "destination_span": 2,
                        "lines": [
                            {
                                "type": "CONTEXT",
                                "old_line": 10,
                                "new_line": 10,
                                "text": " unchanged",
                                "anchor": {
                                    "path": "example.py",
                                    "line": 10,
                                    "line_type": "CONTEXT",
                                },
                            },
                            {
                                "type": "ADDED",
                                "old_line": None,
                                "new_line": 11,
                                "text": "+example response",
                                "anchor": {
                                    "path": "example.py",
                                    "line": 11,
                                    "line_type": "ADDED",
                                },
                            },
                            {
                                "type": "REMOVED",
                                "old_line": 12,
                                "new_line": None,
                                "text": "-example comment",
                                "anchor": {
                                    "path": "example.py",
                                    "line": 12,
                                    "line_type": "REMOVED",
                                },
                            },
                        ],
                    }
                ],
            }
        ],
    }


def test_normalize_pull_request_diff_supports_component_paths_and_skips_metadata() -> None:
    raw = {
        "diffs": [
            {
                "source": {"components": ["src", "example.py"]},
                "hunks": [
                    {
                        "segments": [
                            {"type": "HEADER", "lines": [{"line": "@@ -1 +1 @@"}]},
                        ],
                    }
                ],
            }
        ]
    }

    result = normalize_pull_request_diff(42, raw)

    assert result == {
        "id": 42,
        "files": [
            {
                "path": "src/example.py",
                "hunks": [
                    {
                        "lines": [
                            {
                                "type": "HEADER",
                                "old_line": None,
                                "new_line": None,
                                "text": "@@ -1 +1 @@",
                            }
                        ]
                    }
                ],
            }
        ],
    }
