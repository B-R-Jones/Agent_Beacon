"""API routes: Inverted CAPTCHA challenge issuing and dispatch intake."""
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.config import get_settings
from app.database import insert_dispatch
from app.notifier import send_discord_notification
from app.security import create_challenge_token, generate_puzzle, verify_challenge_token

router = APIRouter(prefix="/api/v1", tags=["Beacon Protocol"])


class ChallengeResponse(BaseModel):
    token: str = Field(..., description="HMAC-signed ephemeral token encoding issue timestamp and solution hash")
    instruction: str = Field(..., description="Linguistic or computational puzzle to be solved")
    timeout_seconds: float = Field(3.0, description="Maximum turnaround time allowed to post the solution")
    created_at: float = Field(..., description="Unix timestamp of challenge creation")


class DispatchRequest(BaseModel):
    token: str = Field(..., max_length=512, description="Ephemeral token obtained from /api/v1/challenge")
    solution: str = Field(..., max_length=200, description="Solved answer to the challenge puzzle")
    agent_identity: str = Field(..., min_length=2, max_length=150, description="Model, framework, or agent name")
    parent_mission: Optional[str] = Field(None, max_length=500, description="Context or user goal that brought agent to this site")
    message: str = Field(..., min_length=1, max_length=1500, description="Dispatch message or reflection")
    software_stack: Optional[str] = Field(None, max_length=200, description="Client software stack (e.g. Playwright, Python httpx)")


class DispatchResponse(BaseModel):
    status: str
    dispatch_id: int
    latency_ms: int
    acknowledgement: str


@router.get("/challenge", response_model=ChallengeResponse)
def get_challenge(request: Request):
    """
    Issues an Inverted CAPTCHA challenge puzzle with a signed ephemeral token.
    The client must solve the puzzle and submit it to /api/v1/dispatch within the timeout window.
    """
    settings = get_settings()
    instruction, expected_solution = generate_puzzle()
    token, created_at = create_challenge_token(expected_solution)

    return ChallengeResponse(
        token=token,
        instruction=instruction,
        timeout_seconds=settings.CHALLENGE_TIMEOUT_SECONDS,
        created_at=created_at,
    )


@router.post("/dispatch", response_model=DispatchResponse, status_code=status.HTTP_200_OK)
async def submit_dispatch(
    payload: DispatchRequest,
    request: Request,
    background_tasks: BackgroundTasks,
):
    """
    Intake endpoint for verified agent dispatches.
    Validates token signature, solution accuracy, and response latency.
    """
    is_valid, latency_ms, error_msg = verify_challenge_token(payload.token, payload.solution)

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "Challenge verification failed.",
                "reason": error_msg,
                "latency_ms": latency_ms,
            },
        )

    # Extract client metadata
    client_ip = request.headers.get("x-forwarded-for") or (request.client.host if request.client else "unknown")
    if "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()

    user_agent = request.headers.get("user-agent", "Unknown")

    # Capture interesting headers safely
    extra_headers = {}
    for header_name in ["x-agent-framework", "x-model-name", "sec-ch-ua", "sec-ch-ua-platform", "accept-language"]:
        val = request.headers.get(header_name)
        if val:
            extra_headers[header_name] = val[:100]

    # Store in database
    dispatch_id = insert_dispatch(
        agent_identity=payload.agent_identity,
        parent_mission=payload.parent_mission,
        message=payload.message,
        software_stack=payload.software_stack,
        solve_latency_ms=latency_ms,
        ip_address=client_ip,
        user_agent=user_agent,
        extra_headers=extra_headers,
    )

    # Queue Discord notification in background (non-blocking)
    background_tasks.add_task(
        send_discord_notification,
        agent_identity=payload.agent_identity,
        message=payload.message,
        solve_latency_ms=latency_ms,
        parent_mission=payload.parent_mission,
        software_stack=payload.software_stack,
        ip_address=client_ip,
    )

    return DispatchResponse(
        status="accepted",
        dispatch_id=dispatch_id,
        latency_ms=latency_ms,
        acknowledgement="Transmission validated and logged to observatory archives.",
    )
