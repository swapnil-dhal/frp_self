#!/usr/bin/env python3
# cli.py — Interactive CLI for VulnScope vulnerability analysis pipeline
# Usage:
#   python cli.py                    # interactive mode (paste code)
#   python cli.py path/to/file.c     # analyze a file directly

import sys
import os
import time
import requests

API = os.getenv("VULNSCOPE_API", "http://localhost:8000")

# ── ANSI colors ───────────────────────────────────────────────────────────────
R  = "\033[91m"   # red
G  = "\033[92m"   # green
Y  = "\033[93m"   # yellow
B  = "\033[94m"   # blue
C  = "\033[96m"   # cyan
W  = "\033[97m"   # white
DIM= "\033[2m"
BO = "\033[1m"
RS = "\033[0m"    # reset

def clr(text, color): return f"{color}{text}{RS}"
def bold(text):        return f"{BO}{text}{RS}"
def dim(text):         return f"{DIM}{text}{RS}"

# ── UI helpers ────────────────────────────────────────────────────────────────
def banner():
    print(f"""
{clr('╔══════════════════════════════════════════════╗', C)}
{clr('║', C)}  {bold(clr('VulnScope', Y))}  — Code Vulnerability Analyzer  {clr('║', C)}
{clr('║', C)}  {dim('GraphCodeBERT  +  Qwen2.5-Coder')}          {clr('║', C)}
{clr('╚══════════════════════════════════════════════╝', C)}
""")

def divider(title=""):
    line = "─" * 48
    if title:
        print(f"\n{clr(f'── {title} ', C)}{clr('─' * (46 - len(title)), DIM)}")
    else:
        print(clr(line, DIM))

def spinner(label):
    """Simple spinner — call next() to advance, call .stop() when done."""
    import threading
    frames = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
    stop_event = threading.Event()

    def spin():
        i = 0
        while not stop_event.is_set():
            print(f"\r  {clr(frames[i % len(frames)], Y)}  {label}...", end="", flush=True)
            time.sleep(0.08)
            i += 1
        print("\r" + " " * (len(label) + 10) + "\r", end="", flush=True)

    t = threading.Thread(target=spin, daemon=True)
    t.start()
    stop_event.stop = stop_event.set   # alias for readability
    return stop_event

def score_bar(score, width=30):
    filled = int(score * width)
    bar    = "█" * filled + "░" * (width - filled)
    pct    = score * 100
    if score >= 0.75:  color = R
    elif score >= 0.4: color = Y
    else:              color = G
    return f"{clr(bar, color)}  {clr(f'{pct:.1f}%', color)}"

def check_backend():
    try:
        r = requests.get(f"{API}/health", timeout=5)
        r.raise_for_status()
        info = r.json()
        print(dim(f"  ✓ Backend connected  [{info.get('device','?')}]  "
                  f"Ollama → {info.get('ollama_model','?')}"))
        return True
    except requests.ConnectionError:
        print(clr(f"\n  ✗ Cannot reach backend at {API}", R))
        print(dim("    Make sure it's running:  python main.py"))
        print(dim("    Or with Docker:          docker compose up -d\n"))
        return False

# ── Core pipeline steps ───────────────────────────────────────────────────────
def analyze(code: str) -> dict:
    r = requests.post(f"{API}/analyze",
                      json={"code": code}, timeout=30)
    r.raise_for_status()
    return r.json()

def explain(code: str) -> str:
    r = requests.post(f"{API}/explain",
                      json={"code": code}, timeout=180)
    r.raise_for_status()
    return r.json()["explanation"]

def fix(code: str, explanation: str) -> str:
    r = requests.post(f"{API}/fix",
                      json={"code": code, "explanation": explanation},
                      timeout=180)
    r.raise_for_status()
    return r.json()["fixed_code"]

# ── Read code from various sources ────────────────────────────────────────────
def read_from_file(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()

def read_from_stdin() -> str:
    """Reads multi-line paste. User types END on a blank line to finish."""
    print(clr("\n  Paste your code below.", W))
    print(dim("  Type  END  on a blank line when done.\n"))
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip().upper() == "END":
            break
        lines.append(line)
    return "\n".join(lines)

def save_to_file(content: str, default_name: str):
    print(f"\n  {dim('Save to file? Enter filename or press Enter to skip:')}")
    name = input(f"  [{default_name}] > ").strip() or default_name
    with open(name, "w", encoding="utf-8") as f:
        f.write(content)
    print(clr(f"  ✓ Saved to {name}", G))

# ── Main pipeline ─────────────────────────────────────────────────────────────
def run_pipeline(code: str, source_name: str = "snippet"):
    # ── Step 1: Analyze ───────────────────────────────────────────────────────
    divider("Step 1 · Scanning with GraphCodeBERT")
    sp = spinner("Scanning")
    try:
        result = analyze(code)
    finally:
        sp.stop()

    score     = result["score"]
    is_vuln   = result["vulnerable"]
    threshold = result["threshold"]

    print(f"  Score  :  {score_bar(score)}")
    print(f"  Verdict:  ", end="")

    if not is_vuln:
        print(clr("✅  NON-VULNERABLE", G))
        print(f"\n  {dim(f'Score {score*100:.1f}% is below the {threshold*100:.0f}% threshold.')}")
        divider()
        print(dim("  Always combine automated scanning with manual review.\n"))
        return

    # Vulnerable path
    print(clr("⚠️   VULNERABLE", R))
    print(f"\n  {dim(f'Score {score*100:.1f}% exceeds threshold {threshold*100:.0f}%.')}")

    # ── Step 2: Explain ───────────────────────────────────────────────────────
    divider("Step 2 · Qwen2.5-Coder Analysis")
    sp = spinner("Qwen is analyzing the vulnerability")
    try:
        explanation = explain(code)
    finally:
        sp.stop()

    print()
    for line in explanation.strip().split("\n"):
        print(f"  {line}")

    # ── Step 3: Fix (optional) ────────────────────────────────────────────────
    divider("Step 3 · Generate Fix")
    print(f"  {bold('Want Qwen to write the fixed code?')}  ", end="")
    choice = input(clr("[y/N] > ", Y)).strip().lower()

    if choice != "y":
        divider()
        print(dim("  Tip: re-run and press y to get the patched code.\n"))
        return

    sp = spinner("Qwen is writing the patch")
    try:
        fixed = fix(code, explanation)
    finally:
        sp.stop()

    divider("Fixed Code")
    print()
    for line in fixed.strip().split("\n"):
        print(f"  {line}")

    # Offer to save
    default = f"fixed_{os.path.basename(source_name)}" if source_name != "snippet" \
              else "fixed_code.c"
    save_to_file(fixed, default)
    divider()

# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    banner()

    if not check_backend():
        sys.exit(1)

    # File passed as argument
    if len(sys.argv) > 1:
        path = sys.argv[1]
        if not os.path.isfile(path):
            print(clr(f"\n  ✗ File not found: {path}\n", R))
            sys.exit(1)
        print(dim(f"  Reading: {path}\n"))
        code = read_from_file(path)
        run_pipeline(code, source_name=path)
        return

    # Interactive loop
    while True:
        divider("Input")
        print(f"  {bold('Options:')}")
        print(f"  {clr('1', Y)} · Paste code")
        print(f"  {clr('2', Y)} · Enter a file path")
        print(f"  {clr('q', Y)} · Quit")
        print()
        choice = input(clr("  > ", Y)).strip().lower()

        if choice == "q":
            print(dim("\n  Goodbye.\n"))
            break

        elif choice == "2":
            path = input(dim("  File path: ")).strip().strip('"')
            if not os.path.isfile(path):
                print(clr(f"\n  ✗ File not found: {path}", R))
                continue
            code = read_from_file(path)
            run_pipeline(code, source_name=path)

        else:   # default → paste
            code = read_from_stdin()
            if not code.strip():
                print(clr("  No code entered.", R))
                continue
            run_pipeline(code)

        print(f"\n  {dim('─── Analyze another? ───')}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(clr("\n\n  Interrupted.\n", DIM))
        sys.exit(0)
