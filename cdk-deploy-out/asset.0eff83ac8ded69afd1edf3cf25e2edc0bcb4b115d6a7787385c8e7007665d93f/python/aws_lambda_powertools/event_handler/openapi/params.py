from __future__ import annotations

import inspect
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseConfig
from pydantic.fields import FieldInfo
from typing_extensions import Annotated, get_args, get_origin

from aws_lambda_powertools.event_handler import Response
from aws_lambda_powertools.event_handler.openapi.compat import (
    ModelField,
    Required,
    Undefined,
    UndefinedType,
    copy_field_info,
    field_annotation_is_scalar,
    get_annotation_from_field_info,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from aws_lambda_powertools.event_handler.openapi.models import Example
    from aws_lambda_powertools.event_handler.openapi.types import CacheKey

"""
This turns the low-level function signature into typed, validated Pydantic models for consumption.
"""


class ParamTypes(Enum):
    query = "query"
    header = "header"
    path = "path"
    cookie = "cookie"


# MAINTENANCE: update when deprecating Pydantic v1, remove this alias
_Unset: Any = Undefined


class Dependant:
    """
    A class used internally to represent a dependency between path operation decorators and the path operation function.
    """

    def __init__(
        self,
        *,
        path_params: list[ModelField] | None = None,
        query_params: list[ModelField] | None = None,
        header_params: list[ModelField] | None = None,
        cookie_params: list[ModelField] | None = None,
        body_params: list[ModelField] | None = None,
        return_param: ModelField | None = None,
        response_extra_models: list[ModelField] | None = None,
        name: str | None = None,
        call: Callable[..., Any] | None = None,
        request_param_name: str | None = None,
        websocket_param_name: str | None = None,
        http_connection_param_name: str | None = None,
        response_param_name: str | None = None,
        background_tasks_param_name: str | None = None,
        path: str | None = None,
    ) -> None:
        self.path_params = path_params or []
        self.query_params = query_params or []
        self.header_params = header_params or []
        self.cookie_params = cookie_params or []
        self.body_params = body_params or []
        self.return_param = return_param or None
        self.response_extra_models = response_extra_models or []
        self.request_param_name = request_param_name
        self.websocket_param_name = websocket_param_name
        self.http_connection_param_name = http_connection_param_name
        self.response_param_name = response_param_name
        self.background_tasks_param_name = background_tasks_param_name
        self.name = name
        self.call = call
        # Store the path to be able to re-generate a dependable from it in overrides
        self.path = path
        # Save the cache key at creation to optimize performance
        self.cache_key: CacheKey = self.call


class Param(FieldInfo):
    """
    A class used internally to represent a parameter in a path operation.
    """

    in_: ParamTypes

    def __init__(
        self,
        default: Any = Undefined,
        *,
        default_factory: Callable[[], Any] | None = _Unset,
        annotation: Any | None = None,
        alias: str | None = None,
        alias_priority: int | None = _Unset,
        # MAINTENANCE: update when deprecating Pydantic v1, import these types
        # MAINTENANCE: validation_alias: str | AliasPath | AliasChoices | None
        validation_alias: str | None = None,
        serialization_alias: str | None = None,
        title: str | None = None,
        description: str | None = None,
        gt: float | None = None,
        ge: float | None = None,
        lt: float | None = None,
        le: float | None = None,
        min_length: int | None = None,
        max_length: int | None = None,
        pattern: str | None = None,
        discriminator: str | None = None,
        strict: bool | None = _Unset,
        multiple_of: float | None = _Unset,
        allow_inf_nan: bool | None = _Unset,
        max_digits: int | None = _Unset,
        decimal_places: int | None = _Unset,
        examples: list[Any] | None = None,
        openapi_examples: dict[str, Example] | None = None,
        deprecated: bool | None = None,
        include_in_schema: bool = True,
        json_schema_extra: dict[str, Any] | None = None,
        **extra: Any,
    ):
        """
        Constructs a new Param.

        Parameters
        ----------
        default: Any
            The default value of the parameter
        default_factory: Callable[[], Any], optional
            Callable that will be called when a default value is needed for this field
        annotation: Any, optional
            The type annotation of the parameter
        alias: str, optional
            The public name of the field
        alias_priority: int, optional
            Priority of the alias. This affects whether an alias generator is used
        validation_alias: str | AliasPath | AliasChoices | None, optional
            Alias to be used for validation only
        serialization_alias: str | AliasPath | AliasChoices | None, optional
            Alias to be used for serialization only
        title: str, optional
            The title of the parameter
        description: str, optional
            The description of the parameter
        gt: float, optional
            Only applies to numbers, required the field to be "greater than"
        ge: float, optional
            Only applies to numbers, required the field to be "greater than or equal"
        lt: float, optional
            Only applies to numbers, required the field to be "less than"
        le: float, optional
            Only applies to numbers, required the field to be "less than or equal"
        min_length: int, optional
            Only applies to strings, required the field to have a minimum length
        max_length: int, optional
            Only applies to strings, required the field to have a maximum length
        pattern: str, optional
            Only applies to strings, requires the field match against a regular expression pattern string
        discriminator: str, optional
            Parameter field name for discriminating the type in a tagged union
        strict: bool, optional
            Enables Pydantic's strict mode for the field
        multiple_of: float, optional
            Only applies to numbers, requires the field to be a multiple of the given value
        allow_inf_nan: bool, optional
            Only applies to numbers, requires the field to allow infinity and NaN values
        max_digits: int, optional
            Only applies to Decimals, requires the field to have a maxmium number of digits within the decimal.
        decimal_places: int, optional
            Only applies to Decimals, requires the field to have at most a number of decimal places
        examples: list[Any], optional
            A list of examples for the parameter
        deprecated: bool, optional
            If `True`, the parameter will be marked as deprecated
        include_in_schema: bool, optional
            If `False`, the parameter will be excluded from the generated OpenAPI schema
        json_schema_extra: dict[str, Any], optional
            Extra values to include in the generated OpenAPI schema
        """
        self.deprecated = deprecated
        self.include_in_schema = include_in_schema

        kwargs = dict(
            default=default,
            default_factory=default_factory,
            alias=alias,
            title=title,
            description=description,
            gt=gt,
            ge=ge,
            lt=lt,
            le=le,
            min_length=min_length,
            max_length=max_length,
            discriminator=discriminator,
            multiple_of=multiple_of,
            allow_nan=allow_inf_nan,
            max_digits=max_digits,
            decimal_places=decimal_places,
            **extra,
        )
        if examples is not None:
            kwargs["examples"] = examples

        if openapi_examples is not None:
            kwargs["openapi_examples"] = openapi_examples

        current_json_schema_extra = json_schema_extra or extra

        self.openapi_examples = openapi_examples

        kwargs.update(
            {
                "annotation": annotation,
                "alias_priority": alias_priority,
                "validation_alias": validation_alias,
                "serialization_alias": serialization_alias,
                "strict": strict,
                "json_schema_extra": current_json_schema_extra,
                "pattern": pattern,
            },
        )

        use_kwargs = {k: v for k, v in kwargs.items() if v is not _Unset}

        super().__init__(**use_kwargs)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.default})"


class Path(Param):
    """
    A class used internally to represent a path parameter in a path operation.
    """

    in_ = ParamTypes.path

    def __init__(
        self,
        default: Any = ...,
        *,
        default_factory: Callable[[], Any] | None = _Unset,
        annotation: Any | None = None,
        alias: str | None = None,
        alias_priority: int | None = _Unset,
        # MAINTENANCE: update when deprecating Pydantic v1, import these types
        # MAINTENANCE: validation_alias: str | AliasPath | AliasChoices | None
        validation_alias: str | None = None,
        serialization_alias: str | None = None,
        title: str | None = None,
        description: str | None = None,
        gt: float | None = None,
        ge: float | None = None,
        lt: float | None = None,
        le: float | None = None,
        min_length: int | None = None,
        max_length: int | None = None,
        pattern: str | None = None,
        discriminator: str | None = None,
        strict: bool | None = _Unset,
        multiple_of: float | None = _Unset,
        allow_inf_nan: bool | None = _Unset,
        max_digits: int | None = _Unset,
        decimal_places: int | None = _Unset,
        examples: list[Any] | None = None,
        openapi_examples: dict[str, Example] | None = None,
        deprecated: bool | None = None,
        include_in_schema: bool = True,
        json_schema_extra: dict[str, Any] | None = None,
        **extra: Any,
    ):
        """
        Constructs a new Path param.

        Parameters
        ----------
        default: Any
            The default value of the parameter
        default_factory: Callable[[], Any], optional
            Callable that will be called when a default value is needed for this field
        annotation: Any, optional
            The type annotation of the parameter
        alias: str, optional
            The public name of the field
        alias_priority: int, optional
            Priority of the alias. This affects whether an alias generator is used
        validation_alias: str | AliasPath | AliasChoices | None, optional
            Alias to be used for validation only
        serialization_alias: str | AliasPath | AliasChoices | None, optional
            Alias to be used for serialization only
        title: str, optional
            The title of the parameter
        description: str, optional
            The description of the parameter
        gt: float, optional
            Only applies to numbers, required the field to be "greater than"
        ge: float, optional
            Only applies to numbers, required the field to be "greater than or equal"
        lt: float, optional
            Only applies to numbers, required the field to be "less than"
        le: float, optional
            Only applies to numbers, required the field to be "less than or equal"
        min_length: int, optional
            Only applies to strings, required the field to have a minimum length
        max_length: int, optional
            Only applies to strings, required the field to have a maximum length
        pattern: str, optional
            Only applies to strings, requires the field match against a regular expression pattern string
        discriminator: str, optional
            Parameter field name for discriminating the type in a tagged union
        strict: bool, optional
            Enables Pydantic's strict mode for the field
        multiple_of: float, optional
            Only applies to numbers, requires the field to be a multiple of the given value
        allow_inf_nan: bool, optional
            Only applies to numbers, requires the field to allow infinity and NaN values
        max_digits: int, optional
            Only applies to Decimals, requires the field to have a maxmium number of digits within the decimal.
        decimal_places: int, optional
            Only applies to Decimals, requires the field to have at most a number of decimal places
        examples: list[Any], optional
            A list of examples for the parameter
        deprecated: bool, optional
            If `True`, the parameter will be marked as deprecated
        include_in_schema: bool, optional
            If `False`, the parameter will be excluded from the generated OpenAPI schema
        json_schema_extra: dict[str, Any], optional
            Extra values to include in the generated OpenAPI schema
        """
        if default is not ...:
            raise AssertionError("Path parameters cannot have a default value")

        super().__init__(
            default=default,
            default_factory=default_factory,
            annotation=annotation,
            alias=alias,
            alias_priority=alias_priority,
            validation_alias=validation_alias,
            serialization_alias=serialization_alias,
            title=title,
            description=description,
            gt=gt,
            ge=ge,
            lt=lt,
            le=le,
            min_length=min_length,
            max_length=max_length,
            pattern=pattern,
            discriminator=discriminator,
            strict=strict,
            multiple_of=multiple_of,
            allow_inf_nan=allow_inf_nan,
            max_digits=max_digits,
            decimal_places=decimal_places,
            deprecated=deprecated,
            examples=examples,
            openapi_examples=openapi_examples,
            include_in_schema=include_in_schema,
            json_schema_extra=json_schema_extra,
            **extra,
        )


class Query(Param):
    """
    A class used internally to represent a query parameter in a path operation.
    """

    in_ = ParamTypes.query

    def __init__(
        self,
        default: Any = _Unset,
        *,
        default_factory: Callable[[], Any] | None = _Unset,
        annotation: Any | None = None,
        alias: str | None = None,
        alias_priority: int | None = _Unset,
        validation_alias: str | None = None,
        serialization_alias: str | None = None,
        title: str | None = None,
        description: str | None = None,
        gt: float | None = None,
        ge: float | None = None,
        lt: float | None = None,
        le: float | None = None,
        min_length: int | None = None,
        max_length: int | None = None,
        pattern: str | None = None,
        discriminator: str | None = None,
        strict: bool | None = _Unset,
        multiple_of: float | None = _Unset,
        allow_inf_nan: bool | None = _Unset,
        max_digits: int | None = _Unset,
        decimal_places: int | None = _Unset,
        examples: list[Any] | None = None,
        openapi_examples: dict[str, Example] | None = None,
        deprecated: bool | None = None,
        include_in_schema: bool = True,
        json_schema_extra: dict[str, Any] | None = None,
        **extra: Any,
    ):
        """
        Constructs a new Query param.

        Parameters
        ----------
        default: Any
            The default value of the parameter
        default_factory: Callable[[], Any], optional
            Callable that will be called when a default value is needed for this field
        annotation: Any, optional
            The type annotation of the parameter
        alias: str, optional
            The public name of the field
        alias_priority: int, optional
            Priority of the alias. This affects whether an alias generator is used
        validation_alias: str | AliasPath | AliasChoices | None, optional
            Alias to be used for validation only
        serialization_alias: str | AliasPath | AliasChoices | None, optional
            Alias to be used for serialization only
        title: str, optional
            The title of the parameter
        description: str, optional
            The description of the parameter
        gt: float, optional
            Only applies to numbers, required the field to be "greater than"
        ge: float, optional
            Only applies to numbers, required the field to be "greater than or equal"
        lt: float, optional
            Only applies to numbers, required the field to be "less than"
        le: float, optional
            Only applies to numbers, required the field to be "less than or equal"
        min_length: int, optional
            Only applies to strings, required the field to have a minimum length
        max_length: int, optional
            Only applies to strings, required the field to have a maximum length
        pattern: str, optional
            Only applies to strings, requires the field match against a regular expression pattern string
        discriminator: str, optional
            Parameter field name for discriminating the type in a tagged union
        strict: bool, optional
            Enables Pydantic's strict mode for the field
        multiple_of: float, optional
            Only applies to numbers, requires the field to be a multiple of the given value
        allow_inf_nan: bool, optional
            Only applies to numbers, requires the field to allow infinity and NaN values
        max_digits: int, optional
            Only applies to Decimals, requires the field to have a maxmium number of digits within the decimal.
        decimal_places: int, optional
            Only applies to Decimals, requires the field to have at most a number of decimal places
        examples: list[Any], optional
            A list of examples for the parameter
        deprecated: bool, optional
            If `True`, the parameter will be marked as deprecated
        include_in_schema: bool, optional
            If `False`, the parameter will be excluded from the generated OpenAPI schema
        json_schema_extra: dict[str, Any], optional
            Extra values to include in the generated OpenAPI schema
        """
        super().__init__(
            default=default,
            default_factory=default_factory,
            annotation=annotation,
            alias=alias,
            alias_priority=alias_priority,
            validation_alias=validation_alias,
            serialization_alias=serialization_alias,
            title=title,
            description=description,
            gt=gt,
            ge=ge,
            lt=lt,
            le=le,
            min_length=min_length,
            max_length=max_length,
            pattern=pattern,
            discriminator=discriminator,
            strict=strict,
            multiple_of=multiple_of,
            allow_inf_nan=allow_inf_nan,
            max_digits=max_digits,
            decimal_places=decimal_places,
            deprecated=deprecated,
            examples=examples,
            openapi_examples=openapi_examples,
            include_in_schema=include_in_schema,
            json_schema_extra=json_schema_extra,
            **extra,
        )


class Header(Param):
    """
    A class used internally to represent a header parameter in a path operation.
    """

    in_ = ParamTypes.header

    def __init__(
        self,
        default: Any = Undefined,
        *,
        default_factory: Callable[[], Any] | None = _Unset,
        annotation: Any | None = None,
        alias: str | None = None,
        alias_priority: int | None = _Unset,
        # MAINTENANCE: update when deprecating Pydantic v1, import these types
        # str | AliasPath | AliasChoices | None
        validation_alias: str | None = None,
        serialization_alias: str | None = None,
        convert_underscores: bool = True,
        title: str | None = None,
        description: str | None = None,
        gt: float | None = None,
        ge: float | None = None,
        lt: float | None = None,
        le: float | None = None,
        min_length: int | None = None,
        max_length: int | None = None,
        pattern: str | None = None,
        discriminator: str | None = None,
        strict: bool | None = _Unset,
        multiple_of: float | None = _Unset,
        allow_inf_nan: bool | None = _Unset,
        max_digits: int | None = _Unset,
        decimal_places: int | None = _Unset,
        examples: list[Any] | None = None,
        openapi_examples: dict[str, Example] | None = None,
        deprecated: bool | None = None,
        include_in_schema: bool = True,
        json_schema_extra: dict[str, Any] | None = None,
        **extra: Any,
    ):
        """
        Constructs a new Query param.

        Parameters
        ----------
        default: Any
            The default value of the parameter
        default_factory: Callable[[], Any], optional
            Callable that will be called when a default value is needed for this field
        annotation: Any, optional
            The type annotation of the parameter
        alias: str, optional
            The public name of the field
        alias_priority: int, optional
            Priority of the alias. This affects whether an alias generator is used
        validation_alias: str | AliasPath | AliasChoices | None, optional
            Alias to be used for validation only
        serialization_alias: str | AliasPath | AliasChoices | None, optional
            Alias to be used for serialization only
        convert_underscores: bool
            If true convert "_" to "-"
            See RFC: https://www.rfc-editor.org/rfc/rfc9110.html#name-field-name-registry
        title: str, optional
            The title of the parameter
        description: str, optional
            The description of the parameter
        gt: float, optional
            Only applies to numbers, required the field to be "greater than"
        ge: float, optional
            Only applies to numbers, required the field to be "greater than or equal"
        lt: float, optional
            Only applies to numbers, required the field to be "less than"
        le: float, optional
            Only applies to numbers, required the field to be "less than or equal"
        min_length: int, optional
            Only applies to strings, required the field to have a minimum length
        max_length: int, optional
            Only applies to strings, required the field to have a maximum length
        pattern: str, optional
            Only applies to strings, requires the field match against a regular expression pattern string
        discriminator: str, optional
            Parameter field name for discriminating the type in a tagged union
        strict: bool, optional
            Enables Pydantic's strict mode for the field
        multiple_of: float, optional
            Only applies to numbers, requires the field to be a multiple of the given value
        allow_inf_nan: bool, optional
            Only applies to numbers, requires the field to allow infinity and NaN values
        max_digits: int, optional
            Only applies to Decimals, requires the field to have a maxmium number of digits within the decimal.
        decimal_places: int, optional
            Only applies to Decimals, requires the field to have at most a number of decimal places
        examples: list[Any], optional
            A list of examples for the parameter
        deprecated: bool, optional
            If `True`, the parameter will be marked as deprecated
        include_in_schema: bool, optional
            If `False`, the parameter will be excluded from the generated OpenAPI schema
        json_schema_extra: dict[str, Any], optional
            Extra values to include in the generated OpenAPI schema
        """
        self.convert_underscores = convert_underscores
        self._alias = alias

        super().__init__(
            default=default,
            default_factory=default_factory,
            annotation=annotation,
            alias=self._alias,
            alias_priority=alias_priority,
            validation_alias=validation_alias,
            serialization_alias=serialization_alias,
            title=title,
            description=description,
            gt=gt,
            ge=ge,
            lt=lt,
            le=le,
            min_length=min_length,
            max_length=max_length,
            pattern=pattern,
            discriminator=discriminator,
            strict=strict,
            multiple_of=multiple_of,
            allow_inf_nan=allow_inf_nan,
            max_digits=max_digits,
            decimal_places=decimal_places,
            deprecated=deprecated,
            examples=examples,
            openapi_examples=openapi_examples,
            include_in_schema=include_in_schema,
            json_schema_extra=json_schema_extra,
            **extra,
        )

    @property
    def alias(self):
        return self._alias

    @alias.setter
    def alias(self, value: str | None = None):
        if value is not None:
            # Headers are case-insensitive according to RFC 7540 (HTTP/2), so we lower the parameter name
            # This ensures that customers can access headers with any casing, as per the RFC guidelines.
            # Reference: https://www.rfc-editor.org/rfc/rfc7540#section-8.1.2
            self._alias = value.lower()


class Body(FieldInfo):
    """
    A class used internally to represent a body parameter in a path operation.
    """

    def __init__(
        self,
        default: Any = Undefined,
        *,
        default_factory: Callable[[], Any] | None = _Unset,
        annotation: Any | None = None,
        embed: bool = False,
        media_type: str = "application/json",
        alias: str | None = None,
        alias_priority: int | None = _Unset,
        # MAINTENANCE: update when deprecating Pydantic v1, import these types
        # str | AliasPath | AliasChoices | None
        validation_alias: str | None = None,
        serialization_alias: str | None = None,
        title: str | None = None,
        description: str | None = None,
        gt: float | None = None,
        ge: float | None = None,
        lt: float | None = None,
        le: float | None = None,
        min_length: int | None = None,
        max_length: int | None = None,
        pattern: str | None = None,
        discriminator: str | None = None,
        strict: bool | None = _Unset,
        multiple_of: float | None = _Unset,
        allow_inf_nan: bool | None = _Unset,
        max_digits: int | None = _Unset,
        decimal_places: int | None = _Unset,
        examples: list[Any] | None = None,
        openapi_examples: dict[str, Example] | None = None,
        deprecated: bool | None = None,
        include_in_schema: bool = True,
        json_schema_extra: dict[str, Any] | None = None,
        **extra: Any,
    ):
        self.embed = embed
        self.media_type = media_type
        self.deprecated = deprecated
        self.include_in_schema = include_in_schema
        kwargs = dict(
            default=default,
            default_factory=default_factory,
            alias=alias,
            title=title,
            description=description,
            gt=gt,
            ge=ge,
            lt=lt,
            le=le,
            min_length=min_length,
            max_length=max_length,
            discriminator=discriminator,
            multiple_of=multiple_of,
            allow_nan=allow_inf_nan,
            max_digits=max_digits,
            decimal_places=decimal_places,
            **extra,
        )
        if examples is not None:
            kwargs["examples"] = examples
        current_json_schema_extra = json_schema_extra or extra

        kwargs.update(
            {
                "annotation": annotation,
                "alias_priority": alias_priority,
                "validation_alias": validation_alias,
                "serialization_alias": serialization_alias,
                "strict": strict,
                "json_schema_extra": current_json_schema_extra,
                "pattern": pattern,
            },
        )

        use_kwargs = {k: v for k, v in kwargs.items() if v is not _Unset}

        super().__init__(**use_kwargs)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.default})"


class _Form(Body):
    """
    A class used internally to represent a form parameter in a path operation.
    """

    def __init__(
        self,
        default: Any = Undefined,
        *,
        default_factory: Callable[[], Any] | None = _Unset,
        annotation: Any | None = None,
        media_type: str = "application/x-www-form-urlencoded",
        alias: str | None = None,
        alias_priority: int | None = _Unset,
        # MAINTENANCE: update when deprecating Pydantic v1, import these types
        # str | AliasPath | AliasChoices | None
        validation_alias: str | None = None,
        serialization_alias: str | None = None,
        title: str | None = None,
        description: str | None = None,
        gt: float | None = None,
        ge: float | None = None,
        lt: float | None = None,
        le: float | None = None,
        min_length: int | None = None,
        max_length: int | None = None,
        pattern: str | None = None,
        discriminator: str | None = None,
        strict: bool | None = _Unset,
        multiple_of: float | None = _Unset,
        allow_inf_nan: bool | None = _Unset,
        max_digits: int | None = _Unset,
        decimal_places: int | None = _Unset,
        examples: list[Any] | None = None,
        deprecated: bool | None = None,
        include_in_schema: bool = True,
        json_schema_extra: dict[str, Any] | None = None,
        **extra: Any,
    ):
        super().__init__(
            default=default,
            default_factory=default_factory,
            annotation=annotation,
            embed=True,
            media_type=media_type,
            alias=alias,
            alias_priority=alias_priority,
            validation_alias=validation_alias,
            serialization_alias=serialization_alias,
            title=title,
            description=description,
            gt=gt,
            ge=ge,
            lt=lt,
            le=le,
            min_length=min_length,
            max_length=max_length,
            pattern=pattern,
            discriminator=discriminator,
            strict=strict,
            multiple_of=multiple_of,
            allow_inf_nan=allow_inf_nan,
            max_digits=max_digits,
            decimal_places=decimal_places,
            deprecated=deprecated,
            examples=examples,
            include_in_schema=include_in_schema,
            json_schema_extra=json_schema_extra,
            **extra,
        )


class _File(_Form):
    """
    A class used internally to represent a file parameter in a path operation.
    """

    def __init__(
        self,
        default: Any = Undefined,
        *,
        default_factory: Callable[[], Any] | None = _Unset,
        annotation: Any | None = None,
        media_type: str = "multipart/form-data",
        alias: str | None = None,
        alias_priority: int | None = _Unset,
        # MAINTENANCE: update when deprecating Pydantic v1, import these types
        # str | AliasPath | AliasChoices | None
        validation_alias: str | None = None,
        serialization_alias: str | None = None,
        title: str | None = None,
        description: str | None = None,
        gt: float | None = None,
        ge: float | None = None,
        lt: float | None = None,
        le: float | None = None,
        min_length: int | None = None,
        max_length: int | None = None,
        pattern: str | None = None,
        discriminator: str | None = None,
        strict: bool | None = _Unset,
        multiple_of: float | None = _Unset,
        allow_inf_nan: bool | None = _Unset,
        max_digits: int | None = _Unset,
        decimal_places: int | None = _Unset,
        examples: list[Any] | None = None,
        deprecated: bool | None = None,
        include_in_schema: bool = True,
        json_schema_extra: dict[str, Any] | None = None,
        **extra: Any,
    ):
        super().__init__(
            default=default,
            default_factory=default_factory,
            annotation=annotation,
            media_type=media_type,
            alias=alias,
            alias_priority=alias_priority,
            validation_alias=validation_alias,
            serialization_alias=serialization_alias,
            title=title,
            description=description,
            gt=gt,
            ge=ge,
            lt=lt,
            le=le,
            min_length=min_length,
            max_length=max_length,
            pattern=pattern,
            discriminator=discriminator,
            strict=strict,
            multiple_of=multiple_of,
            allow_inf_nan=allow_inf_nan,
            max_digits=max_digits,
            decimal_places=decimal_places,
            deprecated=deprecated,
            examples=examples,
            include_in_schema=include_in_schema,
            json_schema_extra=json_schema_extra,
            **extra,
        )


def get_flat_dependant(
    dependant: Dependant,
    visited: list[CacheKey] | None = None,
) -> Dependant:
    """
    Flatten a recursive Dependant model structure.

    This function recursively concatenates the parameter fields of a Dependant model and its dependencies into a flat
    Dependant structure. This is useful for scenarios like parameter validation where the nested structure is not
    relevant.

    Parameters
    ----------
    dependant: Dependant
        The dependant model to flatten
    visited: list[CacheKey], optional
        Keeps track of visited Dependents to avoid infinite recursion. Defaults to empty list.

    Returns
    -------
    Dependant
        The flattened Dependant model
    """
    if visited is None:
        visited = []
    visited.append(dependant.cache_key)

    return Dependant(
        path_params=dependant.path_params.copy(),
        query_params=dependant.query_params.copy(),
        header_params=dependant.header_params.copy(),
        cookie_params=dependant.cookie_params.copy(),
        body_params=dependant.body_params.copy(),
        path=dependant.path,
    )


def analyze_param(
    *,
    param_name: str,
    annotation: Any,
    value: Any,
    is_path_param: bool,
    is_response_param: bool,
) -> ModelField | None:
    """
    Analyze a parameter annotation and value to determine the type and default value of the parameter.

    Parameters
    ----------
    param_name: str
        The name of the parameter
    annotation
        The annotation of the parameter
    value
        The value of the parameter
    is_path_param
        Whether the parameter is a path parameter
    is_response_param
        Whether the parameter is the return annotation

    Returns
    -------
    ModelField | None
        The type annotation and the Pydantic field representing the parameter
    """
    field_info, type_annotation = get_field_info_and_type_annotation(
        annotation,
        value,
        is_path_param,
        is_response_param,
    )

    # If the value is a FieldInfo, we use it as the FieldInfo for the parameter
    if isinstance(value, FieldInfo):
        if field_info is not None:
            raise AssertionError("Cannot use a FieldInfo as a parameter annotation and pass a FieldInfo as a value")
        field_info = value

        field_info.annotation = type_annotation  # type: ignore[attr-defined,unused-ignore]

    # If we didn't determine the FieldInfo yet, we create a default one
    if field_info is None:
        default_value = value if value is not inspect.Signature.empty else Required

        # Check if the parameter is part of the path. Otherwise, defaults to query.
        if is_path_param:
            field_info = Path(annotation=type_annotation)
        elif not field_annotation_is_scalar(annotation=type_annotation):
            field_info = Body(annotation=type_annotation, default=default_value)
        else:
            field_info = Query(annotation=type_annotation, default=default_value)

    # When we have a response field, we need to set the default value to Required
    if is_response_param:
        field_info.default = Required

    field = _create_model_field(field_info, type_annotation, param_name, is_path_param)
    return field


def get_field_info_and_type_annotation(
    annotation,
    value,
    is_path_param: bool,
    is_response_param: bool,
) -> tuple[FieldInfo | None, Any]:
    """
    Get the FieldInfo and type annotation from an annotation and value.
    """
    field_info: FieldInfo | None = None
    type_annotation: Any = Any

    if annotation is not inspect.Signature.empty:
        # If the annotation is an Annotated type, we need to extract the type annotation and the FieldInfo
        if get_origin(annotation) is Annotated:
            field_info, type_annotation = get_field_info_annotated_type(annotation, value, is_path_param)
        # If the annotation is a Response type, we recursively call this function with the inner type
        elif get_origin(annotation) is Response:
            field_info, type_annotation = get_field_info_response_type(annotation, value)
        # If the response param is a tuple with two elements, we use the first element as the type annotation,
        # just like we did in the APIGateway._to_response
        elif is_response_param and get_origin(annotation) is tuple and len(get_args(annotation)) == 2:
            field_info, type_annotation = get_field_info_tuple_type(annotation, value)
        # If the annotation is not an Annotated type, we use it as the type annotation
        else:
            type_annotation = annotation

    return field_info, type_annotation


def get_field_info_tuple_type(annotation, value) -> tuple[FieldInfo | None, Any]:
    (inner_type, _) = get_args(annotation)

    # If the inner type is an Annotated type, we need to extract the type annotation and the FieldInfo
    if get_origin(inner_type) is Annotated:
        return get_field_info_annotated_type(inner_type, value, False)

    return None, inner_type


def get_field_info_response_type(annotation, value) -> tuple[FieldInfo | None, Any]:
    # Example: get_args(Response[inner_type]) == (inner_type,)  # noqa: ERA001
    (inner_type,) = get_args(annotation)

    # Recursively resolve the inner type
    return get_field_info_and_type_annotation(inner_type, value, False, True)


def get_field_info_annotated_type(annotation, value, is_path_param: bool) -> tuple[FieldInfo | None, Any]:
    """
    Get the FieldInfo and type annotation from an Annotated type.
    """
    field_info: FieldInfo | None = None
    annotated_args = get_args(annotation)
    type_annotation = annotated_args[0]
    powertools_annotations = [arg for arg in annotated_args[1:] if isinstance(arg, FieldInfo)]

    if len(powertools_annotations) > 1:
        raise AssertionError("Only one FieldInfo can be used per parameter")

    powertools_annotation = next(iter(powertools_annotations), None)

    if isinstance(powertools_annotation, FieldInfo):
        # Copy `field_info` because we mutate `field_info.default` later
        field_info = copy_field_info(
            field_info=powertools_annotation,
            annotation=annotation,
        )
        if field_info.default not in [Undefined, Required]:
            raise AssertionError("FieldInfo needs to have a default value of Undefined or Required")

        if value is not inspect.Signature.empty:
            if is_path_param:
                raise AssertionError("Cannot use a FieldInfo as a path parameter and pass a value")
            field_info.default = value
        else:
            field_info.default = Required

    return field_info, type_annotation


def create_response_field(
    name: str,
    type_: type[Any],
    default: Any | None = Undefined,
    required: bool | UndefinedType = Undefined,
    model_config: type[BaseConfig] = BaseConfig,
    field_info: FieldInfo | None = None,
    alias: str | None = None,
    mode: Literal["validation", "serialization"] = "validation",
) -> ModelField:
    """
    Create a new response field. Raises if type_ is invalid.
    """
    field_info = field_info or FieldInfo(
        annotation=type_,
        default=default,
        alias=alias,
    )

    kwargs = {"name": name, "field_info": field_info, "mode": mode}

    return ModelField(**kwargs)  # type: ignore[arg-type]


def _create_model_field(
    field_info: FieldInfo | None,
    type_annotation: Any,
    param_name: str,
    is_path_param: bool,
) -> ModelField | None:
    """
    Create a new ModelField from a FieldInfo and type annotation.
    """
    if field_info is None:
        return None

    if is_path_param:
        if not isinstance(field_info, Path):
            raise AssertionError("Path parameters must be of type Path")
    elif isinstance(field_info, Param) and getattr(field_info, "in_", None) is None:
        field_info.in_ = ParamTypes.query

    # If the field_info is a Param, we use the `in_` attribute to determine the type annotation
    use_annotation = get_annotation_from_field_info(type_annotation, field_info, param_name)

    # If the field doesn't have a defined alias, we use the param name
    if not field_info.alias and getattr(field_info, "convert_underscores", None):
        alias = param_name.replace("_", "-")
    else:
        alias = field_info.alias or param_name
    field_info.alias = alias

    return create_response_field(
        name=param_name,
        type_=use_annotation,
        default=field_info.default,
        alias=alias,
        required=field_info.default in (Required, Undefined),
        field_info=field_info,
    )
