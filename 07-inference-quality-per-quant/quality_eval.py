#!/usr/bin/env python3
"""Quality eval harness for Ollama-served models.
Runs HumanEval-pass@1 and GSM8K (subset) on a given Ollama model tag.

Usage:
    python3 quality_eval.py --model qwen2.5:3b-instruct-q4_K_M --gsm8k-n 200
"""
import argparse
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

OLLAMA_URL = "http://localhost:11434"
DATASETS = Path(__file__).parent.parent / "datasets"
RESULTS = Path(__file__).parent.parent / "results"
RESULTS.mkdir(exist_ok=True)


def ollama_generate(model, prompt, max_tokens=512, system=None, temperature=0.0):
    body = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": max_tokens, "temperature": temperature, "top_p": 1.0, "seed": 42},
        "keep_alive": "30m",
    }
    if system:
        body["system"] = system
    data = json.dumps(body).encode()
    req = urllib.request.Request(f"{OLLAMA_URL}/api/generate", data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())


def extract_code(text):
    """Extract Python code from a model response."""
    # Look for fenced code block first
    m = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1)
    # Otherwise return text as-is (model may have just emitted code)
    return text


def run_humaneval_problem(problem, generated_code, timeout=10):
    """Run a HumanEval test for a single full-function generation. Returns (passed, error).
    `generated_code` should be a complete function (def ...) — we exec it then run check()."""
    test_code = (
        generated_code + "\n\n" +
        problem["test"] + "\n" +
        f"check({problem['entry_point']})\n"
    )
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(test_code)
            path = f.name
        try:
            res = subprocess.run(["python3", path], capture_output=True, text=True, timeout=timeout)
            return (res.returncode == 0, res.stderr[:500] if res.returncode != 0 else "")
        finally:
            os.unlink(path)
    except subprocess.TimeoutExpired:
        return (False, "TIMEOUT")
    except Exception as e:
        return (False, f"EXCEPTION: {e}")


def humaneval_completion_prompt(problem):
    """Build instruct-style prompt for HumanEval. Asks for the full function so we can exec it directly."""
    sys_msg = ("You are an expert Python programmer. When given a function specification, "
               "write the complete Python function in a ```python code block. "
               "Include any necessary imports inside the code block. No explanations.")
    user = (f"Write the complete implementation for this function:\n\n"
            f"```python\n{problem['prompt']}```\n\n"
            f"Output the entire function (signature + body) in a ```python code block.")
    return sys_msg, user


def parse_humaneval_completion(response_text, problem):
    """Extract the model's generated code (full function) from response."""
    code = extract_code(response_text).strip("\n")
    return code


GSM8K_SYS = ("You are a math tutor. Solve the problem step by step. "
             "On the last line, write 'The answer is N' where N is the final numeric answer (no units, no commas).")


def parse_gsm8k_answer(text):
    """Extract numeric answer from model response."""
    # Last "answer is X" pattern
    m = re.findall(r"answer\s+is\s*:?\s*\$?\s*(-?[\d,]+(?:\.\d+)?)", text, re.IGNORECASE)
    if m:
        return m[-1].replace(",", "")
    # Try "#### X" (gold format)
    m = re.findall(r"####\s*(-?[\d,]+(?:\.\d+)?)", text)
    if m:
        return m[-1].replace(",", "")
    # Last number in text
    nums = re.findall(r"-?\$?\d[\d,]*(?:\.\d+)?", text)
    if nums:
        return nums[-1].replace("$", "").replace(",", "")
    return None


def gsm8k_gold(answer_field):
    m = re.search(r"####\s*(-?[\d,]+(?:\.\d+)?)", answer_field)
    if not m:
        return None
    return m.group(1).replace(",", "")


def run_humaneval(model, n_problems=None):
    problems = [json.loads(l) for l in open(DATASETS / "HumanEval.jsonl")]
    if n_problems:
        problems = problems[:n_problems]
    print(f"  HumanEval: {len(problems)} problems")
    results = []
    passed = 0
    t0 = time.time()
    for i, p in enumerate(problems):
        sys_msg, user = humaneval_completion_prompt(p)
        try:
            r = ollama_generate(model, user, max_tokens=512, system=sys_msg, temperature=0.0)
        except Exception as e:
            results.append({"task": p["task_id"], "passed": False, "err": f"API: {e}"})
            continue
        completion = parse_humaneval_completion(r.get("response", ""), p)
        ok, err = run_humaneval_problem(p, completion)
        if ok:
            passed += 1
        results.append({"task": p["task_id"], "passed": ok, "err": err[:200] if err else "",
                        "tokens": r.get("eval_count", 0),
                        "tok_s": (r.get("eval_count", 0) / (r.get("eval_duration", 1) / 1e9)) if r.get("eval_duration") else 0})
        if (i + 1) % 20 == 0:
            print(f"    [{i+1}/{len(problems)}] pass@1={passed/(i+1):.3f}  elapsed={time.time()-t0:.0f}s")
    return {"n": len(problems), "passed": passed, "pass_rate": passed / len(problems),
            "elapsed_s": time.time() - t0, "results": results}


def run_gsm8k(model, n_problems=200, seed=42):
    import random
    rng = random.Random(seed)
    problems = [json.loads(l) for l in open(DATASETS / "gsm8k_test.jsonl")]
    rng.shuffle(problems)
    problems = problems[:n_problems]
    print(f"  GSM8K: {len(problems)} problems")
    results = []
    passed = 0
    t0 = time.time()
    for i, p in enumerate(problems):
        gold = gsm8k_gold(p["answer"])
        try:
            r = ollama_generate(model, p["question"], max_tokens=512, system=GSM8K_SYS, temperature=0.0)
        except Exception as e:
            results.append({"i": i, "passed": False, "err": f"API: {e}"})
            continue
        pred = parse_gsm8k_answer(r.get("response", ""))
        ok = (pred is not None and gold is not None and float(pred) == float(gold))
        if ok:
            passed += 1
        results.append({"i": i, "passed": ok, "pred": pred, "gold": gold,
                        "tokens": r.get("eval_count", 0),
                        "tok_s": (r.get("eval_count", 0) / (r.get("eval_duration", 1) / 1e9)) if r.get("eval_duration") else 0})
        if (i + 1) % 20 == 0:
            print(f"    [{i+1}/{len(problems)}] acc={passed/(i+1):.3f}  elapsed={time.time()-t0:.0f}s")
    return {"n": len(problems), "passed": passed, "pass_rate": passed / len(problems),
            "elapsed_s": time.time() - t0, "results": results}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--humaneval-n", type=int, default=164)
    ap.add_argument("--gsm8k-n", type=int, default=200)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    safe_name = args.model.replace(":", "_").replace("/", "_")
    out = args.out or str(RESULTS / f"{safe_name}.json")

    print(f"=== Eval {args.model} ===")
    # Warmup
    print("  warmup")
    ollama_generate(args.model, "hi", max_tokens=4)

    he = run_humaneval(args.model, args.humaneval_n) if args.humaneval_n > 0 else None
    if he:
        print(f"  HumanEval: pass@1 = {he['pass_rate']:.3f} ({he['passed']}/{he['n']}) in {he['elapsed_s']:.0f}s")

    gsm = run_gsm8k(args.model, args.gsm8k_n) if args.gsm8k_n > 0 else None
    if gsm:
        print(f"  GSM8K-{gsm['n']}: acc = {gsm['pass_rate']:.3f} ({gsm['passed']}/{gsm['n']}) in {gsm['elapsed_s']:.0f}s")

    summary = {"model": args.model}
    if he:
        summary["humaneval"] = {"n": he["n"], "passed": he["passed"], "pass_rate": he["pass_rate"], "elapsed_s": he["elapsed_s"]}
    if gsm:
        summary["gsm8k"] = {"n": gsm["n"], "passed": gsm["passed"], "pass_rate": gsm["pass_rate"], "elapsed_s": gsm["elapsed_s"]}
    full = dict(summary)
    if he:
        full["humaneval_runs"] = he["results"]
    if gsm:
        full["gsm8k_runs"] = gsm["results"]
    with open(out, "w") as f:
        json.dump(full, f, indent=2)
    print(f"  saved -> {out}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
