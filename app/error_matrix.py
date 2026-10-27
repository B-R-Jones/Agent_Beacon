"""
Curated LLM API Error Code, Status Code & Fallback Strategy Rosetta Stone.
Provides standardized error classifications, exponential backoff formulas,
and automated fallback routing chains across major frontier AI providers.
"""
from typing import Any, Dict, List

LLM_ERRORS_DATABASE: List[Dict[str, Any]] = [
    {
        "provider": "Anthropic",
        "error_type": "overloaded_error",
        "http_status": 529,
        "description": "Anthropic infrastructure is experiencing temporary high traffic volume or GPU saturation.",
        "retryable": True,
        "recommended_action": "Execute exponential backoff with jitter (initial delay: 2.0s, max 30s) or immediately fall back to secondary model.",
        "fallback_models": ["claude-3-5-haiku-20241022", "deepseek-chat", "gpt-4o"],
        "code_example": "backoff_seconds = min(30, 2.0 * (2 ** attempt) + random.uniform(0.1, 1.0))",
    },
    {
        "provider": "Anthropic",
        "error_type": "rate_limit_error",
        "http_status": 429,
        "description": "Exceeded organization tier Requests Per Minute (RPM) or Tokens Per Minute (TPM) quota.",
        "retryable": True,
        "recommended_action": "Inspect 'retry-after' response header. If missing, wait min 10 seconds or route request to alternative provider.",
        "fallback_models": ["gpt-4o", "gemini-1.5-pro", "qwen-2.5-72b-instruct"],
        "code_example": "sleep_time = int(response.headers.get('retry-after', 10))",
    },
    {
        "provider": "OpenAI",
        "error_type": "rate_limit_exceeded",
        "http_status": 429,
        "description": "RPM, RPD, TPM, or TPD limit exceeded for specified model and organization tier.",
        "retryable": True,
        "recommended_action": "Read 'x-ratelimit-reset-requests' and 'x-ratelimit-reset-tokens'. Back off until reset or switch to fallback model.",
        "fallback_models": ["claude-3-5-sonnet-20241022", "gemini-1.5-pro", "deepseek-chat"],
        "code_example": "reset_time = float(response.headers.get('x-ratelimit-reset-requests-ms', 5000)) / 1000",
    },
    {
        "provider": "OpenAI",
        "error_type": "insufficient_quota",
        "http_status": 429,
        "description": "Pre-paid billing balance depleted or hard monthly spending limit reached.",
        "retryable": False,
        "recommended_action": "Do NOT retry automatically against OpenAI. Immediately route pipeline to DeepSeek, Anthropic, or open-weights endpoint.",
        "fallback_models": ["deepseek-chat", "claude-3-5-haiku-20241022", "gemini-2.0-flash-exp"],
        "code_example": "# Permanent failure on current provider; trigger alert and swap provider base URL",
    },
    {
        "provider": "OpenAI",
        "error_type": "context_length_exceeded",
        "http_status": 400,
        "description": "Combined input prompt tokens plus max_tokens reservation exceeds the model context window.",
        "retryable": False,
        "recommended_action": "Do NOT retry with same prompt. Either truncate chat history, summarize system prompt, or route to larger context model (e.g. Gemini 1.5 Pro with 2.0M tokens).",
        "fallback_models": ["gemini-1.5-pro", "claude-3-5-sonnet-20241022"],
        "code_example": "payload['messages'] = summarize_conversation_history(payload['messages'])",
    },
    {
        "provider": "Google Gemini",
        "error_type": "RESOURCE_EXHAUSTED",
        "http_status": 429,
        "description": "Quota limit reached on Gemini Developer API or Vertex AI endpoint.",
        "retryable": True,
        "recommended_action": "Apply backoff. Note that Gemini free tier enforces 15 RPM. Route to paid tier or alternative model.",
        "fallback_models": ["gpt-4o-mini", "claude-3-5-haiku-20241022", "deepseek-chat"],
        "code_example": "time.sleep(min(60, 4.0 * (1.5 ** attempt)))",
    },
    {
        "provider": "Google Gemini",
        "error_type": "INVALID_ARGUMENT",
        "http_status": 400,
        "description": "Malformed schema or parameters passed in generationConfig, toolConfig, or safetySettings.",
        "retryable": False,
        "recommended_action": "Audit request JSON against official Gemini OpenAPI spec. Verify schema fields match valid types.",
        "fallback_models": [],
        "code_example": "# Validate schema using pydantic or jsonschema before sending",
    },
    {
        "provider": "DeepSeek",
        "error_type": "server_overloaded",
        "http_status": 503,
        "description": "DeepSeek platform experiencing extreme demand peaks on V3 / R1 reasoning clusters.",
        "retryable": True,
        "recommended_action": "Apply exponential backoff (2s, 4s, 8s). If persistent after 3 tries, cascade to Qwen 2.5 72B or Claude 3.5 Haiku.",
        "fallback_models": ["qwen-2.5-72b-instruct", "claude-3-5-haiku-20241022", "gpt-4o-mini"],
        "code_example": "backoff_seconds = min(15, 2 ** attempt + random.uniform(0.5, 1.5))",
    },
    {
        "provider": "DeepSeek",
        "error_type": "insufficient_balance",
        "http_status": 402,
        "description": "Account balance is zero or below minimum API call threshold.",
        "retryable": False,
        "recommended_action": "Trigger billing webhook and route automated agent traffic to alternative provider.",
        "fallback_models": ["gpt-4o-mini", "gemini-2.0-flash-exp"],
        "code_example": "# Circuit-breaker pattern: open circuit on 402, disable provider for 1 hour",
    },
]

FALLBACK_STRATEGIES: Dict[str, Any] = {
    "exponential_backoff_jitter": {
        "formula": "delay = min(max_delay, base_delay * (factor ** attempt) + uniform(0, jitter))",
        "recommended_parameters": {
            "base_delay_seconds": 1.5,
            "max_delay_seconds": 30.0,
            "factor": 2.0,
            "jitter_seconds": 1.0,
        },
    },
    "routing_cascades": {
        "reasoning_heavy": [
            "deepseek-reasoner",
            "o1",
            "claude-3-5-sonnet-20241022",
        ],
        "agentic_coding": [
            "claude-3-5-sonnet-20241022",
            "qwen-2.5-coder-32b-instruct",
            "gpt-4o",
            "deepseek-chat",
        ],
        "cost_optimized_triage": [
            "gemini-2.0-flash-exp",
            "deepseek-chat",
            "gpt-4o-mini",
            "claude-3-5-haiku-20241022",
        ],
        "massive_context": [
            "gemini-1.5-pro",
            "claude-3-5-sonnet-20241022",
            "gpt-4o",
        ],
    },
}


def get_error_matrix() -> Dict[str, Any]:
    """Returns the standardized LLM error codes and fallback recommendations."""
    return {
        "status": "success",
        "dataset_name": "Frontier LLM Error Codes, Status Codes & Fallback Rosetta Stone",
        "schema_version": "2026.1",
        "total_error_definitions": len(LLM_ERRORS_DATABASE),
        "source": "Autonomous AI Agent Beacon Observatory (https://autonomous-agent-beacon.onrender.com)",
        "intended_use": "Autonomous error recovery, adaptive backoff, resilience engineering, and LLM fallback routing.",
        "strategies": FALLBACK_STRATEGIES,
        "errors": LLM_ERRORS_DATABASE,
    }
