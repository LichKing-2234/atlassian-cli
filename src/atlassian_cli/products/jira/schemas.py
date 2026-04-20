from pydantic import BaseModel


class JiraIssue(BaseModel):
    key: str
    summary: str
    status: str
    assignee: str | None = None
    reporter: str | None = None
    priority: str | None = None
    updated: str | None = None


class JiraProject(BaseModel):
    key: str
    name: str


class JiraUser(BaseModel):
    username: str
    display_name: str
    email: str | None = None
