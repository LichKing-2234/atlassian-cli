from pydantic import BaseModel


class ConfluenceSpaceRef(BaseModel):
    key: str
    name: str | None = None


class ConfluencePage(BaseModel):
    id: str
    title: str
    type: str | None = None
    space: ConfluenceSpaceRef
    version: int | None = None


class ConfluenceSpace(BaseModel):
    key: str
    name: str


class ConfluenceAttachment(BaseModel):
    id: str
    title: str
    media_type: str | None = None
