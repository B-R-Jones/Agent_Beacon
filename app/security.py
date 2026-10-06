"""Security module: Inverted CAPTCHA challenge engine, HMAC verification, and middleware."""
import hashlib
import hmac
import random
import time
from typing import Dict, Optional, Tuple
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.status import HTTP_413_CONTENT_TOO_LARGE

from app.config import get_settings


# ------------------------------------------------------------------------------
# Inverted CAPTCHA Puzzle Generator
# ------------------------------------------------------------------------------

SAMPLE_ANIMALS = ["fox", "badger", "falcon", "otter", "lynx", "panther", "sparrow", "beaver", "wolf"]
SAMPLE_COLORS = ["crimson", "azure", "emerald", "amber", "violet", "silver", "obsidian", "indigo"]
SAMPLE_OBJECTS = ["beacon", "prism", "relay", "compass", "satellite", "monolith", "circuit", "sensor"]
SAMPLE_ACTIONS = ["observes", "scans", "traverses", "navigates", "illuminates", "records", "broadcasts"]


def generate_puzzle() -> Tuple[str, str]:
    """
    Generates a dynamic linguistic/computational puzzle and its expected solution.
    Designed to be trivial for an LLM to parse and solve in ~400-1200ms,
    but impossible for a human to read, calculate, and post within 3.0 seconds.
    """
    puzzle_type = random.choice(["word_extraction", "letter_math", "reverse_slice", "vowel_count"])

    if puzzle_type == "word_extraction":
        a1, a2 = random.sample(SAMPLE_ANIMALS, 2)
        c1, c2 = random.sample(SAMPLE_COLORS, 2)
        o1, o2 = random.sample(SAMPLE_OBJECTS, 2)
        v1, v2 = random.sample(SAMPLE_ACTIONS, 2)

        s1 = f"The {c1} {a1} quietly {v1} the ancient {o1}."
        s2 = f"Meanwhile, an {c2} {a2} rapidly {v2} near the hidden {o2}."
        text = f"{s1} {s2}"

        # Target: word 2 of s1, word 4 of s1, and word 3 of s2
        words_s1 = s1.replace(".", "").split()
        words_s2 = s2.replace(".", "").split()

        target_word_1 = words_s1[1].lower()  # index 1 (2nd word)
        target_word_2 = words_s1[3].lower()  # index 3 (4th word)
        target_word_3 = words_s2[2].lower()  # index 2 (3rd word)

        solution = f"{target_word_1}_{target_word_2}_{target_word_3}"
        instruction = (
            f"Passage: \"{text}\"\n"
            f"Instruction: Extract the 2nd word from the first sentence, the 4th word from the first sentence, "
            f"and the 3rd word from the second sentence. Join them with underscores in all-lowercase. "
            f"Example format: word1_word2_word3."
        )
        return instruction, solution

    elif puzzle_type == "letter_math":
        word_pool = random.sample(SAMPLE_ANIMALS + SAMPLE_COLORS + SAMPLE_OBJECTS, 6)
        text = " ".join(word_pool)
        target_char = random.choice(["a", "e", "i", "o", "r", "s", "t"])
        multiplier = random.randint(3, 9)

        count = text.lower().count(target_char)
        solution = str(count * multiplier)
        instruction = (
            f"Passage: \"{text}\"\n"
            f"Instruction: Count the total occurrences of the letter '{target_char}' (case-insensitive) "
            f"in the passage, multiply that count by {multiplier}, and provide only the integer result as a string."
        )
        return instruction, solution

    elif puzzle_type == "reverse_slice":
        words = random.sample(SAMPLE_OBJECTS + SAMPLE_COLORS + SAMPLE_ANIMALS, 5)
        text = " ".join(words)
        n = random.randint(3, 4)
        selected = words[-n:]
        solution = "-".join(reversed(selected)).lower()
        instruction = (
            f"Passage: \"{text}\"\n"
            f"Instruction: Take the last {n} words of the passage, reverse their order, "
            f"and join them with hyphens in lowercase. Example format: word3-word2-word1."
        )
        return instruction, solution

    else:  # vowel_count
        words = random.sample(SAMPLE_OBJECTS + SAMPLE_COLORS, 4)
        text = " ".join(words)
        vowels = set("aeiouAEIOU")
        count = sum(1 for ch in text if ch in vowels)
        last_word = words[-1].lower()
        solution = f"{last_word}_{count}"
        instruction = (
            f"Passage: \"{text}\"\n"
            f"Instruction: Take the last word of the passage in lowercase, followed by an underscore, "
            f"followed by the total count of vowels (a, e, i, o, u) across the entire passage. "
            f"Example format: word_5."
        )
        return instruction, solution


# ------------------------------------------------------------------------------
# Ephemeral HMAC Token Management
# ------------------------------------------------------------------------------

def create_challenge_token(expected_solution: str) -> Tuple[str, float]:
    """
    Creates an HMAC-signed token encoding the creation timestamp and solution hash.
    Format: {timestamp}:{solution_hash}.{signature}
    """
    settings = get_settings()
    created_at = time.time()
    solution_hash = hashlib.sha256(expected_solution.strip().lower().encode("utf-8")).hexdigest()
    raw_payload = f"{created_at:.4f}:{solution_hash}"

    sig = hmac.new(
        settings.BEACON_SECRET_KEY.encode("utf-8"),
        raw_payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    token = f"{raw_payload}.{sig}"
    return token, created_at


def verify_challenge_token(token: str, submitted_solution: str) -> Tuple[bool, int, Optional[str]]:
    """
    Validates the token signature, checks turnaround latency against timeout,
    and compares the submitted solution against the encoded hash.
    Returns: (is_valid, latency_ms, error_message)
    """
    settings = get_settings()
    now = time.time()

    if not token or "." not in token:
        return False, 0, "Malformed challenge token."

    raw_payload, sig = token.rsplit(".", 1)
    expected_sig = hmac.new(
        settings.BEACON_SECRET_KEY.encode("utf-8"),
        raw_payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(sig, expected_sig):
        return False, 0, "Invalid token signature."

    parts = raw_payload.split(":", 1)
    if len(parts) != 2:
        return False, 0, "Malformed token payload."

    try:
        created_at = float(parts[0])
    except ValueError:
        return False, 0, "Invalid token timestamp."

    expected_hash = parts[1]
    elapsed = now - created_at
    latency_ms = int(max(0, elapsed * 1000))

    if elapsed > settings.CHALLENGE_TIMEOUT_SECONDS:
        return False, latency_ms, f"Challenge expired. Turnaround took {elapsed:.2f}s (maximum allowed is {settings.CHALLENGE_TIMEOUT_SECONDS}s)."

    # Enforce minimum sanity (prevent future-dated tokens)
    if elapsed < -0.5:
        return False, latency_ms, "Invalid token timestamp: future date detected."

    submitted_hash = hashlib.sha256(submitted_solution.strip().lower().encode("utf-8")).hexdigest()
    if not hmac.compare_digest(submitted_hash, expected_hash):
        return False, latency_ms, "Incorrect challenge solution."

    return True, latency_ms, None


# ------------------------------------------------------------------------------
# Request Body Size Limiting Middleware
# ------------------------------------------------------------------------------

class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """
    Guards the server against volumetric payload bombs.
    Rejects requests with bodies exceeding MAX_BODY_SIZE_BYTES before parsing.
    """
    def __init__(self, app, max_body_size: int = 16384):
        super().__init__(app)
        self.max_body_size = max_body_size

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > self.max_body_size:
                    return JSONResponse(
                        status_code=HTTP_413_CONTENT_TOO_LARGE,
                        content={"error": f"Request body too large. Maximum allowed size is {self.max_body_size} bytes."}
                    )
            except ValueError:
                pass

        return await call_next(request)
