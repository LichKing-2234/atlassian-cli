from pydantic import BaseModel, Field


class BitbucketNamedRef(BaseModel):
    display_id: str


class BitbucketReviewer(BaseModel):
    display_name: str
    approved: bool = False


class BitbucketProject(BaseModel):
    key: str
    name: str


class BitbucketRepo(BaseModel):
    project: BitbucketProject
    slug: str
    name: str
    state: str


class BitbucketPullRequest(BaseModel):
    id: int
    title: str
    state: str
    author: dict[str, str] | None = None
    from_ref: BitbucketNamedRef | None = None
    to_ref: BitbucketNamedRef | None = None
    reviewers: list[BitbucketReviewer] = Field(default_factory=list)
