"""OpenCode Zen / Go contract — verified against upstream API documentation.

This module records every detail of the OpenCode API contract so tests and provider
code can reference a shared source of truth rather than repeating literals.

Verified against the public OpenCode Zen and Go documentation on 2026-07-31:

- https://opencode.ai/docs/zen/
- https://opencode.ai/docs/go/

OpenCode exposes two independent OpenAI-compatible endpoints:

- Zen (``https://opencode.ai/zen/v1/``) — the hosted credit-tier aggregator.
- Go  (``https://opencode.ai/zen/go/v1/``) — the flat-rate subscription tier.

PR #110 treats them as two independent providers (``opencode_zen`` / ``opencode_go``):
each stores its own api_key on its own ``provider:<name>`` SecretStore profile, routes
through its own endpoint, and only *shares* the ``OPENCODE_API_KEY`` environment-var
fallback. There is deliberately NO canonical ``provider:opencode`` shared profile and
no shared configured state.

Known model caveats (conservative by design):

- Capabilities: tools, parallel tool calls and streaming are verified on the shared
  OpenAI-compatible endpoint; vision and PDF input are NOT verified; reasoning is
  supported via DeepSeek-style ``reasoning_content``.
- Zen Free models are time-limited (availability checked 2026-07-31), free of charge,
  and Zen-ONLY (no Go equivalent). Every free label carries the explicit caveat
  "(Free, data may be retained)" — upstream docs for big-pickle, north-mini-code-free
  and nemotron-3-ultra-free note prompt retention for training, and we apply the
  notice conservatively to all of them.
- This first PR exposes only the documented OpenAI-compatible ``/chat/completions``
  compatibility slice. ``/responses``, Anthropic-compatible ``/messages``, and
  Gemini-specific endpoints are intentionally not implemented or selectable here.
- The first PR also omits paid models that are not in the strict Zen/Go
  ``/chat/completions`` intersection. Those are follow-up catalog work, not an implicit
  claim that this provider supports them.
"""

# -- base URLs ------------------------------------------------------------------
# Note the trailing slashes: these MUST match the registry's prefilled `base_url`
# field defaults exactly (registry.py `_compat` entries for opencode_zen/opencode_go).
OPCODE_GO_ENDPOINT = "https://opencode.ai/zen/go/v1/"
OPCODE_ZEN_ENDPOINT = "https://opencode.ai/zen/v1/"

# -- auth -----------------------------------------------------------------------
# Header: Authorization: Bearer <key>
# Key source: https://opencode.ai/auth
# Env var: OPENCODE_API_KEY — shared fallback for BOTH independent providers
# (each provider's own stored profile key still wins over this env var).
SHARED_ENV_KEY = "OPENCODE_API_KEY"

# -- verification ---------------------------------------------------------------
# GET <endpoint>/models with Bearer auth returns 200 on success, 401/403 on bad key.
VERIFY_PATH = "/models"

from dataclasses import dataclass

# -- model-to-transport mapping -------------------------------------------------
# This is deliberately a small, explicit first-PR catalog. Do not broaden it without
# rechecking the public docs above.

TRANSPORT_OPENAI = "openai"  # OpenAI SDK chat.completions
TRANSPORT_ANTHROPIC = "anthropic"  # Anthropic SDK messages (reserved for future use)

@dataclass(frozen=True)
class OpenCodeModel:
    model_id: str
    label: str
    tier: str
    free: bool = False
    transport: str = TRANSPORT_OPENAI
    profile: str = "chat.completions"
    data_retention_notice: str | None = None
    recommendation_priority: int | None = None

OPEN_CODE_CATALOG = (
    *(OpenCodeModel(m, m.replace("-", " ").title(), "zen", recommendation_priority=0 if m == "grok-4.5" else None) for m in (
        "grok-4.5", "grok-build-0.1", "glm-5.2", "glm-5.1", "glm-5", "kimi-k3",
        "kimi-k2.7-code", "kimi-k2.6", "kimi-k2.5", "deepseek-v4-pro", "deepseek-v4-flash",
        "minimax-m3", "minimax-m2.7", "minimax-m2.5")),
    *(OpenCodeModel(m, m.replace("-", " ").title(), "zen", True, data_retention_notice="Free, data may be retained") for m in (
        "big-pickle", "deepseek-v4-flash-free", "mimo-v2.5-free", "laguna-s-2.1-free",
        "ling-3.0-flash-free", "north-mini-code-free", "nemotron-3-ultra-free")),
    *(OpenCodeModel(
        m,
        m.replace("-", " ").title(),
        "go",
        data_retention_notice="Data may be retained" if m == "deepseek-v4-flash" else None,
        recommendation_priority=0 if m == "kimi-k3" else None,
    ) for m in (
        "grok-4.5", "glm-5.2", "glm-5.1", "kimi-k3", "kimi-k2.7-code", "kimi-k2.6",
        "deepseek-v4-pro", "deepseek-v4-flash", "mimo-v2.5", "mimo-v2.5-pro", "hy3")),
)
OPEN_CODE_RECOMMENDED = {
    f"opencode_{tier}": next(x.model_id for x in OPEN_CODE_CATALOG if x.tier == tier and x.recommendation_priority == 0)
    for tier in ("zen", "go")
}
OPEN_CODE_MODELS = {tier: frozenset(x.model_id for x in OPEN_CODE_CATALOG if x.tier == tier) for tier in ("zen", "go")}
COMMON_CHAT_COMPLETIONS_MODELS = frozenset(
    x.model_id for x in OPEN_CODE_CATALOG
    if not x.free and x.tier == "zen"
    and any(y.model_id == x.model_id and y.tier == "go" for y in OPEN_CODE_CATALOG)
)
ZEN_MODELS = frozenset(x.model_id for x in OPEN_CODE_CATALOG if x.tier == "zen" and not x.free)
GO_CHAT_COMPLETIONS_MODELS = frozenset(x.model_id for x in OPEN_CODE_CATALOG if x.tier == "go")
GO_MODEL_TRANSPORT = {x.model_id: x.transport for x in OPEN_CODE_CATALOG if x.tier == "go"}
ZEN_FREE_MODELS = {x.model_id: x.transport for x in OPEN_CODE_CATALOG if x.tier == "zen" and x.free}
ZEN_CHAT_COMPLETIONS_MODELS = OPEN_CODE_MODELS["zen"]

UNSUPPORTED_TRANSPORTS = {
    "responses": "Deferred: OpenCode Zen/Go /responses models are not part of this first PR.",
    "messages": "Deferred: Anthropic-compatible /messages models are not part of this first PR.",
    "gemini": "Deferred: Gemini model-specific endpoints are not part of this first PR.",
}

# Paid ids documented on only one tier (for example Zen Qwen or Go Qwen) are intentionally
# omitted until their transport is supported.
# Go MiniMax/Qwen are documented under /messages;
# Go GPT-family models and Zen GPT-family models are documented under /responses.

# -- capabilities (conservative) ------------------------------------------------
# Tools: verified
# Parallel tool calls: verified
# Streaming: verified
# Vision: not verified on shared endpoint
# PDF: not verified on shared endpoint
# Reasoning: supported (DeepSeek-style reasoning_content)

# -- streaming event format -----------------------------------------------------
# OpenAI-compat: SSE with standard delta choices (all exposed first-PR models use this transport).
# Anthropic-compat SSE is reserved for future use.
