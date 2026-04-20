from pydantic import BaseModel


class ConfluencePage(BaseModel):
    id: str
    title: str
    space_key: str
    version: int | None = None


class ConfluenceSpace(BaseModel):
    key: str
    name: str


class ConfluenceAttachment(BaseModel):
    id: str
    title: str
    media_type: str | None = None
