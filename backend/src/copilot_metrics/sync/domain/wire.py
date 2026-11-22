"""Shared base for GitHub billing responses, which use camelCase on the wire."""

from pydantic import AliasGenerator, BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(frozen=True, alias_generator=AliasGenerator(validation_alias=to_camel))
