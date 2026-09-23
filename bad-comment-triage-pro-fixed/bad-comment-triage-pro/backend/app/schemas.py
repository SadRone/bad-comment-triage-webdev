from typing import Literal
from pydantic import BaseModel, Field, field_validator

ProviderName = Literal['youtube', 'brave', 'google']


class JobCreate(BaseModel):
    target: str = Field(min_length=1, max_length=200)
    aliases: list[str] = Field(default_factory=list, max_length=20)
    keywords: list[str] = Field(default_factory=list, max_length=30)
    providers: list[ProviderName] = Field(default_factory=list, max_length=3)
    limit: int = Field(default=200, ge=10, le=1000)

    @field_validator('target')
    @classmethod
    def strip_target(cls, v: str):
        return v.strip()

    @field_validator('aliases', 'keywords')
    @classmethod
    def clean_list(cls, values: list[str]):
        out = []
        seen = set()
        for raw in values:
            value = raw.strip()
            if value and value.casefold() not in seen:
                out.append(value[:200])
                seen.add(value.casefold())
        return out


class ManualAnalyzeRequest(BaseModel):
    target: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=10000)
    context: str = Field(default='', max_length=5000)


class ProviderStatus(BaseModel):
    name: ProviderName
    configured: bool
    description: str
