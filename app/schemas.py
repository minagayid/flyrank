from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.config import MAX_METER_QUANTITY


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TokenUsage(StrictModel):
    input_tokens: int = Field(default=0, ge=0, le=MAX_METER_QUANTITY)
    cached_input_tokens: int = Field(default=0, ge=0, le=MAX_METER_QUANTITY)
    output_tokens: int = Field(default=0, ge=0, le=MAX_METER_QUANTITY)
    reasoning_tokens: int = Field(default=0, ge=0, le=MAX_METER_QUANTITY)

    @model_validator(mode="after")
    def has_billable_usage(self) -> "TokenUsage":
        if self.total_tokens <= 0:
            raise ValueError("At least one token count must be greater than zero.")
        if self.total_tokens > MAX_METER_QUANTITY:
            raise ValueError(f"The combined token count cannot exceed {MAX_METER_QUANTITY:,}.")
        return self

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.cached_input_tokens
            + self.output_tokens
            + self.reasoning_tokens
        )


class GenerateRequest(StrictModel):
    tokens: TokenUsage


class MeterEventRequest(StrictModel):
    usage_type: Literal["api_calls", "ai_tokens"]
    quantity: int = Field(ge=1, le=MAX_METER_QUANTITY)
    tokens: TokenUsage | None = None

    @model_validator(mode="after")
    def validate_usage_shape(self) -> "MeterEventRequest":
        if self.usage_type == "api_calls" and self.tokens is not None:
            raise ValueError("API-call events cannot include token details.")
        if self.usage_type == "ai_tokens":
            if self.tokens is None:
                raise ValueError("AI-token events require the disjoint token-category breakdown.")
            if self.quantity != self.tokens.total_tokens:
                raise ValueError("quantity must equal the sum of the token categories.")
        return self


class CheckoutRequest(StrictModel):
    plan_id: Literal["pro"] = "pro"


class ErrorEnvelope(BaseModel):
    code: str
    message: str
