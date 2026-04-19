from pydantic import BaseModel


class BitbucketProject(BaseModel):
    key: str
    name: str


class BitbucketRepo(BaseModel):
    project_key: str
    slug: str
    name: str
    state: str


class BitbucketPullRequest(BaseModel):
    id: int
    title: str
    state: str
