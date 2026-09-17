"""
=============================================================================
MATGAR LMS — EXPERIENTIALLABS AI CONNECTOR (gpt-6-astra)
=============================================================================
Connects the project to ExperientialLabs API (gpt-6-astra / openrouter-free)
to inspect, analyze, and power the LMS platform's AI capabilities.
=============================================================================
"""
import os
import sys
from pathlib import Path

# Safe Unicode output for Windows Console
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    from openai import OpenAI
except ImportError:
    print("[!] Error: The 'openai' python package is not installed.")
    print("Please install it via: pip install openai")
    sys.exit(1)


def get_api_key() -> str:
    """Retrieves the EXPLABS_API_KEY from environment, .env file, or prompts the user."""
    api_key = os.environ.get("EXPLABS_API_KEY")
    if not api_key:
        for env_path in [Path(__file__).resolve().parent / ".env", Path(__file__).resolve().parent / "apps" / "ai-service" / ".env"]:
            if env_path.exists():
                with open(env_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if line.strip().startswith("EXPLABS_API_KEY="):
                            val = line.strip().split("=", 1)[1].strip().strip('"\'')
                            if val:
                                return val
    if not api_key:
        api_key = input(">> Please enter your EXPLABS_API_KEY: ").strip()
    return api_key


def gather_project_context() -> str:
    """Collects architectural context and metadata about the project."""
    return """# PROJECT CONTEXT: MATGAR CHEMISTRY LMS PLATFORM
Domain: High School Chemistry LMS (منهج الكيمياء للثانوية العامة المصرية)
Tech Stack:
1. Core Backend: FastAPI on port 8000 (SQLite / PostgreSQL DB, SQLAlchemy, JWT Auth)
2. AI Microservice: FastAPI on port 8001 (RAG, Quiz Generation, Grading, Student Analytics)
3. Frontend: React 18 + Vite + Tailwind CSS on port 5173
4. Knowledge Center & RAG: Ingests Chemistry textbooks/PDFs, performs OCR, fixes visual reversed Arabic, extracts tables & Knowledge Units, and provides hybrid BM25 + Vector retrieval.

Key Services in Codebase:
- `apps/api/app/services/document_parsers.py`: PDF/OCR parser with reversed-Arabic fixer and table extraction.
- `apps/api/app/services/knowledge_center_service.py`: Knowledge Units and Assessment Questions ingestion.
- `apps/api/app/services/knowledge_retriever.py`: Hybrid BM25 retrieval with domain concept boosts (+2.0 concept, +2.5 phrase, +3.0 definition).
- `apps/api/app/services/quiz_engine.py`: Live quiz generation with academic distractor creation and duplicate detection.
- `apps/ai-service/app/services/`: LLM services for Tutor chat, Auto-grading, and Risk prediction.
- `apps/web/src/views/AIKnowledgeCenterView.tsx`: Knowledge Center management interface.
"""


def connect_ai(api_key: str):
    """Initializes client and establishes connection with gpt-6-astra or fallback."""
    print(">> Connecting to ExperientialLabs API...")
    
    client = OpenAI(
        base_url="https://api.experientiallabs.ai/v1",
        api_key=api_key,
    )
    
    project_context = gather_project_context()
    
    messages = [
        {
            "role": "system",
            "content": (
                "You are the central AI Brain for the Matgar Chemistry LMS platform. "
                "You have deep expertise in Chemistry (ثانوية عامة), educational curriculum, "
                "full-stack software architecture (FastAPI, React, RAG, BM25, SQLite/PostgreSQL), "
                "and question generation with rigorous pedagogical standards."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Hello! Here is the architecture and summary of my project:\n\n"
                f"{project_context}\n\n"
                f"Please confirm you can see and understand this project, and briefly explain "
                f"how you can assist with this codebase and its Chemistry teaching features."
            ),
        },
    ]

    active_model = None
    for model_name in ["gpt-6-astra", "openrouter-free"]:
        try:
            print(f">> Requesting model: [{model_name}]...")
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
            )
            content = response.choices[0].message.content
            print(f"\n[+] Connected successfully via [{model_name}]!\n")
            print("=" * 65)
            print(content)
            print("=" * 65)
            active_model = model_name
            messages.append({"role": "assistant", "content": content})
            return client, messages, active_model
        except Exception as e:
            if "card_required" in str(e) or "429" in str(e):
                print(f"[i] Model [{model_name}] requires card on file. Switching to free tier fallback...")
            else:
                print(f"[!] Error with [{model_name}]: {e}")

    return None, None, None


def interactive_chat(client, history, model):
    """Run an interactive chat using the already-established client session."""
    print("\n[i] Interactive chat started. Type 'exit' or 'quit' to end.\n")
    while True:
        try:
            user_input = input(">> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[i] Chat ended.")
            return
        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            print("[i] Chat ended.")
            return
        history.append({"role": "user", "content": user_input})
        try:
            response = client.chat.completions.create(model=model, messages=history)
            answer = response.choices[0].message.content
        except Exception as exc:
            print(f"[!] Error: {exc}")
            history.pop()
            continue
        history.append({"role": "assistant", "content": answer})
        print(f"\n{'=' * 65}\n{answer}\n{'=' * 65}\n")


def send_task_and_save_response(client, model, output_file: str = r"D:\AI_REVIEW.md"):
    """Reads D:\AI_AND_INDEXING_SYSTEM.zip and D:\AI_TASK_PROMPT.md, sends to AI, and saves response."""
    import zipfile
    
    print("\n" + "=" * 65)
    print(">> [1/4] Reading source code from D:\\AI_AND_INDEXING_SYSTEM.zip...")
    zip_path = r"D:\AI_AND_INDEXING_SYSTEM.zip"
    code_snippets = []
    if os.path.exists(zip_path):
        with zipfile.ZipFile(zip_path) as zf:
            for n in zf.namelist():
                if not n.endswith(".md") and not n.endswith("/"):
                    content = zf.read(n).decode("utf-8", "ignore")
                    code_snippets.append(f"# ===== FILE: {n} =====\n{content}")
    code = "\n\n".join(code_snippets)
    print(f"    Loaded {len(code_snippets)} files from ZIP ({len(code)} characters).")

    print(">> [2/4] Reading prompt and objectives from D:\\AI_TASK_PROMPT.md...")
    prompt_path = r"D:\AI_TASK_PROMPT.md"
    if os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8", errors="ignore") as f:
            prompt = f.read()
    else:
        prompt = "Review and implement multimodal chemistry indexing and zero-hallucination grounded answering."
    print(f"    Loaded task prompt ({len(prompt)} characters).")

    payload_text = f"{prompt}\n\n=== REPOSITORY SOURCE CODE ===\n{code[:25000]}"
    print(f">> [3/4] Sending request to ExperientialLabs AI using [{model}]...")
    print("    (Please wait, generating comprehensive architectural review and plan...)")
    
    try:
        res = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": payload_text}],
        )
        ans = res.choices[0].message.content
        print(">> [4/4] Saving AI response...")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(ans)
        print(f"\n[+] SUCCESS! Full AI response saved to: {output_file}")
        print(f"    File size: {len(ans)} characters / {len(ans.splitlines())} lines.")
        print("=" * 65 + "\n")
        return ans
    except Exception as e:
        print(f"\n[!] Error sending task to AI: {e}")
        return None


if __name__ == "__main__":
    key = get_api_key()
    client, history, model = connect_ai(key)
    if client and history and len(sys.argv) > 1:
        if sys.argv[1] in ("--chat", "-c"):
            interactive_chat(client, history, model)
        elif sys.argv[1] in ("--task", "--review", "-t"):
            send_task_and_save_response(client, model)

