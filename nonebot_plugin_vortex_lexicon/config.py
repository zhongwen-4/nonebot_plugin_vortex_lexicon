from pydantic import BaseModel


class Config(BaseModel):
    vortex_lexicon_query_threshold: int = 5
