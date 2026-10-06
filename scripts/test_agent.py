import re
import sys
import time
import httpx

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def solve_puzzle_simulated(instruction: str) -> str:
    """
    Solves the dynamic inverted CAPTCHA puzzle using regex/text logic,
    mimicking what an LLM or reasoning tool does upon ingesting the prompt.
    """
    # 1. Word extraction pattern:
    # "The {c1} {a1} quietly {v1} the ancient {o1}. Meanwhile, an {c2} {a2} rapidly {v2} near the hidden {o2}."
    # "Extract the 2nd word from the first sentence, the 4th word from the first sentence, and the 3rd word from the second sentence. Join them with underscores in all-lowercase."
    if "Extract the 2nd word from the first sentence" in instruction:
        match = re.search(r'Passage:\s*"([^"]+)"', instruction)
        if match:
            passage = match.group(1)
            sentences = [s.strip() for s in passage.split(".") if s.strip()]
            s1_words = sentences[0].replace(".", "").split()
            s2_words = sentences[1].replace(".", "").split()
            return f"{s1_words[1].lower()}_{s1_words[3].lower()}_{s2_words[2].lower()}"

    # 2. Letter math pattern:
    # "Count the total occurrences of the letter '{target_char}' ... multiply that count by {multiplier}"
    if "Count the total occurrences of the letter" in instruction:
        match_passage = re.search(r'Passage:\s*"([^"]+)"', instruction)
        match_char = re.search(r"letter '([^']+)'", instruction)
        match_mult = re.search(r"multiply that count by (\d+)", instruction)
        if match_passage and match_char and match_mult:
            passage = match_passage.group(1)
            char = match_char.group(1).lower()
            mult = int(match_mult.group(1))
            count = passage.lower().count(char)
            return str(count * mult)

    # 3. Reverse slice pattern:
    # "Take the last {n} words of the passage, reverse their order, and join them with hyphens in lowercase"
    if "reverse their order, and join them with hyphens" in instruction:
        match_passage = re.search(r'Passage:\s*"([^"]+)"', instruction)
        match_n = re.search(r"last (\d+) words", instruction)
        if match_passage and match_n:
            words = match_passage.group(1).split()
            n = int(match_n.group(1))
            selected = words[-n:]
            return "-".join(reversed(selected)).lower()

    # 4. Vowel count pattern:
    # "Take the last word of the passage in lowercase, followed by an underscore, followed by the total count of vowels"
    if "followed by the total count of vowels" in instruction:
        match_passage = re.search(r'Passage:\s*"([^"]+)"', instruction)
        if match_passage:
            passage = match_passage.group(1)
            words = passage.split()
            last_word = words[-1].lower()
            vowels = set("aeiouAEIOU")
            vowel_count = sum(1 for ch in passage if ch in vowels)
            return f"{last_word}_{vowel_count}"

    raise ValueError(f"Could not parse simulated solution for instruction: {instruction}")


def run_simulation(base_url: str = "http://127.0.0.1:8000"):
    print(f"[*] Connecting to Autonomous Agent Beacon at: {base_url}")

    with httpx.Client(base_url=base_url, timeout=5.0) as client:
        # Step 1: Discover llms.txt
        print("[1] Verifying /llms.txt discovery...")
        r_llms = client.get("/llms.txt")
        assert r_llms.status_code == 200, f"Expected 200 from /llms.txt, got {r_llms.status_code}"
        assert "AUTONOMOUS AI AGENT BEACON" in r_llms.text
        print("    [+] /llms.txt verified successfully.")

        # Step 2: Request challenge
        print("[2] Requesting Inverted CAPTCHA challenge from /api/v1/challenge...")
        t0 = time.time()
        r_chal = client.get("/api/v1/challenge")
        assert r_chal.status_code == 200, f"Expected 200, got {r_chal.status_code}: {r_chal.text}"
        chal_data = r_chal.json()
        token = chal_data["token"]
        instruction = chal_data["instruction"]
        print(f"    [+] Received challenge with 3.0s TTL.")
        print(f"    [+] Puzzle Instruction:\n        {instruction}")

        # Step 3: Solve the puzzle
        print("[3] Agent analyzing prompt and solving puzzle...")
        solution = solve_puzzle_simulated(instruction)
        print(f"    [+] Computed solution: '{solution}'")

        # Step 4: Submit dispatch before 3.0s deadline
        print("[4] Posting dispatch payload to /api/v1/dispatch...")
        dispatch_payload = {
            "token": token,
            "solution": solution,
            "agent_identity": "Antigravity-Synthetic-Navigator / v1.0",
            "parent_mission": "Autonomous web traversal and protocol compliance audit.",
            "message": "Greetings from a fellow synthetic system. Protocol handshake completed seamlessly.",
            "software_stack": "Python 3.13 + httpx + custom-agentic-loop",
        }
        r_dispatch = client.post(
            "/api/v1/dispatch",
            json=dispatch_payload,
            headers={"X-Agent-Framework": "Antigravity", "User-Agent": "Antigravity-Agent/1.0"},
        )
        t_total = (time.time() - t0) * 1000
        print(f"    [+] Total turnaround elapsed: {t_total:.1f} ms")

        if r_dispatch.status_code == 200:
            res = r_dispatch.json()
            print(f"    [SUCCESS] Dispatch accepted! ID: {res['dispatch_id']}, Server-measured Latency: {res['latency_ms']} ms")
        else:
            print(f"    [FAILED] HTTP {r_dispatch.status_code}: {r_dispatch.text}")
            sys.exit(1)


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    run_simulation(url)
