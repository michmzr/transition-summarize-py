from pydantic import BaseModel

class YtVideoRequest(BaseModel):
    url: str
    # type is optional, default is TLDR
    type: str = "TLDR"
