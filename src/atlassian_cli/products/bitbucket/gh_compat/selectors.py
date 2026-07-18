import re
from dataclasses import dataclass
from urllib.parse import unquote, urlparse

from atlassian_cli.core.errors import ValidationError

_SLUG_RE = re.compile(r"^[A-Za-z0-9._~-]+$")
_SCP_RE = re.compile(r"^(?:[^@/]+@)?(?P<host>[^:/]+):(?P<path>.+)$")
_WEB_RE = re.compile(
    r"/(?:projects/(?P<project>[^/]+)|users/(?P<user>[^/]+))/repos/(?P<repo>[^/]+)(?:/|$)",
    re.IGNORECASE,
)
_PR_RE = re.compile(
    r"/(?:projects/(?P<project>[^/]+)|users/(?P<user>[^/]+))/repos/(?P<repo>[^/]+)/pull-requests/(?P<number>[0-9]+)(?:/|$)",
    re.IGNORECASE,
)


class RepositoryHostMismatchError(ValidationError):
    pass


@dataclass(frozen=True)
class ServerIdentity:
    scheme: str
    host: str
    port: int | None
    context_path: str

    @classmethod
    def from_url(cls, value: str) -> "ServerIdentity":
        parsed = urlparse(value.rstrip("/"))
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValidationError(f"invalid Bitbucket server URL: {value}")
        return cls(parsed.scheme, parsed.hostname.lower(), parsed.port, parsed.path.rstrip("/"))

    @property
    def authority(self) -> str:
        return f"{self.host}:{self.port}" if self.port is not None else self.host

    @property
    def base_url(self) -> str:
        return f"{self.scheme}://{self.authority}{self.context_path}"

    def require_host(self, host: str | None, port: int | None, *, clone: bool = False) -> None:
        effective_port = port or ({"http": 80, "https": 443}.get(self.scheme))
        server_port = self.port or ({"http": 80, "https": 443}.get(self.scheme))
        if (
            host is None
            or host.lower() != self.host
            or (not clone and effective_port != server_port)
        ):
            raise RepositoryHostMismatchError(
                "repository host does not match the configured Bitbucket server"
            )

    def require_web_origin(self, scheme: str, host: str | None, port: int | None) -> None:
        if scheme not in {"http", "https"}:
            raise ValidationError("repository URL must use HTTP or HTTPS")
        if scheme != self.scheme:
            raise RepositoryHostMismatchError(
                "repository host does not match the configured Bitbucket server"
            )
        self.require_host(host, port)

    def strip_context_path(self, path: str) -> str:
        if not self.context_path:
            return path
        if path == self.context_path:
            return "/"
        prefix = self.context_path + "/"
        if not path.startswith(prefix):
            raise ValidationError(
                "repository URL does not use the configured Bitbucket context path"
            )
        return path[len(self.context_path) :]


@dataclass(frozen=True)
class RepositoryRef:
    server: ServerIdentity
    project_key: str
    repo_slug: str

    @property
    def slug(self) -> str:
        return f"{self.project_key}/{self.repo_slug}"


@dataclass(frozen=True)
class PullRequestRef:
    repository: RepositoryRef
    number: int


def _repository(project: str, repo: str, server: ServerIdentity) -> RepositoryRef:
    project = unquote(project)
    repo = unquote(repo).removesuffix(".git")
    if not _SLUG_RE.fullmatch(project) or not _SLUG_RE.fullmatch(repo):
        raise ValidationError("repository must use PROJECT/REPOSITORY syntax")
    return RepositoryRef(server, project, repo)


def _web_or_clone(value: str, server: ServerIdentity) -> RepositoryRef | None:
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"}:
        server.require_web_origin(parsed.scheme, parsed.hostname, parsed.port)
        path = server.strip_context_path(parsed.path)
    elif parsed.scheme == "ssh":
        server.require_host(parsed.hostname, parsed.port, clone=True)
        path = parsed.path
    elif match := _SCP_RE.fullmatch(value):
        server.require_host(match.group("host"), None, clone=True)
        path = "/" + match.group("path")
    else:
        return None
    if match := _WEB_RE.search(path):
        project = match.group("project") or f"~{match.group('user')}"
        return _repository(project, match.group("repo"), server)
    if match := re.search(r"/(?:scm/)?(?P<project>~?[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$", path):
        return _repository(match.group("project"), match.group("repo"), server)
    raise ValidationError("repository must use PROJECT/REPOSITORY syntax")


def parse_repository_selector(value: str, server: ServerIdentity) -> RepositoryRef:
    value = value.strip()
    parts = value.split("/")
    if len(parts) == 3:
        if parts[0].lower() != server.authority.lower():
            raise RepositoryHostMismatchError(
                "repository host does not match the configured Bitbucket server"
            )
        return _repository(parts[1], parts[2], server)
    if parsed := _web_or_clone(value, server):
        return parsed
    if len(parts) != 2:
        raise ValidationError("repository must use PROJECT/REPOSITORY syntax")
    return _repository(parts[0], parts[1], server)


def parse_pull_request_url(value: str, server: ServerIdentity) -> PullRequestRef:
    parsed = urlparse(value)
    server.require_web_origin(parsed.scheme, parsed.hostname, parsed.port)
    match = _PR_RE.search(server.strip_context_path(parsed.path))
    if match is None:
        raise ValidationError("invalid Bitbucket pull request URL")
    project = match.group("project") or f"~{match.group('user')}"
    return PullRequestRef(
        _repository(project, match.group("repo"), server),
        int(match.group("number")),
    )
