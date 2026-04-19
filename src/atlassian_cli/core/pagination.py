from pydantic import BaseModel


class Pagination(BaseModel):
    start: int = 0
    limit: int = 25
