from pydantic import BaseModel


class JiraPerson(BaseModel):
    display_name: str


class JiraFieldName(BaseModel):
    name: str


class JiraIssue(BaseModel):
    key: str
    summary: str
    status: JiraFieldName
    assignee: JiraPerson | None = None
    reporter: JiraPerson | None = None
    priority: JiraFieldName | None = None
    updated: str | None = None


class JiraProject(BaseModel):
    key: str
    name: str
    project_type: str | None = None


class JiraUser(BaseModel):
    username: str
    display_name: str
    email: str | None = None
