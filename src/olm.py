from __future__ import annotations

import argparse
import json
import math
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

__version__ = "0.1.0"
TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]*|[0-9]+|[ぁ-んァ-ヶ一-龯]{2,}")


def state_path() -> Path:
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "olm-lite" / "history.jsonl"


def history() -> list[dict]:
    path = state_path()
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def save(mode: str, query: str, output: str, success: bool) -> None:
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"time": datetime.now(timezone.utc).isoformat(), "mode": mode, "query": query,
           "output": output[-12000:], "success": success, "cwd": str(Path.cwd()),
           "command": query if mode == "command" else ""}
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def tokens(text: str) -> set[str]:
    return {word.lower() for word in TOKEN_RE.findall(text)}


def similar(query: str, rows: list[dict], limit: int = 5) -> list[tuple[float, dict]]:
    query_words = tokens(query)
    scored = []
    for row in rows:
        document_words = tokens(str(row.get("query", "")) + " " + str(row.get("output", "")))
        overlap = len(query_words & document_words)
        if overlap:
            score = overlap / math.sqrt(len(query_words) * len(document_words))
            scored.append((score, row))
    return sorted(scored, key=lambda item: item[0], reverse=True)[:limit]


def record_line(row: dict) -> str:
    status = "ok" if row.get("success") else "failed"
    return f"{row.get('time', '')} [{status}] {row.get('mode', '')}: {row.get('query', '')}"


def dangerous(command: str) -> bool:
    pattern = r"(?:^|\s)(?:rm|rmdir|dd|mkfs|shutdown|reboot|kill|chmod|chown)\b|(?:>|>>|\|\s*sh\b)"
    return bool(re.search(pattern, command))


def propose_command(command: str) -> tuple[str, bool]:
    try:
        shlex.split(command)
    except ValueError as error:
        return f"command parse error: {error}", False
    print(f"proposal: {command}")
    if dangerous(command):
        print("危険な操作の可能性があります。実行しません。")
        return "not executed: dangerous command", False
    if not sys.stdin.isatty():
        print("非対話環境のため実行しません。確認後に再実行してください。")
        return "not executed: confirmation required", False
    if input("execute? [y/N] ").strip().lower() != "y":
        return "not executed: declined", False
    result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=60)
    return (result.stdout + result.stderr).strip() or "(no output)", result.returncode == 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    rows = history()
    if argv and argv[0] == "history":
        parser = argparse.ArgumentParser(prog="olm history")
        parser.add_argument("--last", type=int, default=20)
        parser.add_argument("--failed", action="store_true")
        parser.add_argument("--grep", default="")
        args = parser.parse_args(argv[1:])
        selected = [row for row in rows if not (args.failed and row.get("success"))]
        if args.grep:
            selected = [row for row in selected if args.grep.lower() in str(row).lower()]
        for row in selected[-args.last:][::-1]:
            print(record_line(row))
        return 0

    parser = argparse.ArgumentParser(prog="olm", description="local-first command and error history helper")
    parser.add_argument("input", nargs="*")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--ai", action="store_true")
    args = parser.parse_args(argv)

    if not sys.stdin.isatty():
        mode, query, output, success = "stdin", "", sys.stdin.read(), True
    elif not args.input:
        mode, query = "now", "now " + str(Path.cwd())
        output, success = f"directory: {Path.cwd()}\nentries: {len(list(Path.cwd().iterdir()))}", True
    elif len(args.input) == 1 and Path(args.input[0]).exists():
        path = Path(args.input[0]).resolve()
        mode, query = "file", f"file {path}"
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").count("\n") + 1
            output = f"file: {path}\ntype: {path.suffix or '[none]'}\nsize: {path.stat().st_size} bytes\nlines: {lines}"
            success = True
        except OSError as error:
            output, success = f"file error: {error}", False
    else:
        mode, query = "command", " ".join(args.input)
        output, success = propose_command(query)

    print(f"mode: {mode}\n{output}")
    save(mode, query, output, success)
    matches = similar_tfidf(output, history())
    if matches:
        print("\n似た過去事例:")
        for score, row in matches:
            print(f"  {score:.2f} {record_line(row)}")
    if args.ai and not (os.environ.get("OLLAMA_HOST") or os.environ.get("OLLAMA_MODEL")):
        print("AI: 未設定のためRAGモードを使用")
    return 0 if success else 1


def similar_tfidf(query: str, rows: list[dict], limit: int = 5):
    documents = [str(row.get("query", "")) + " " + str(row.get("output", "")) for row in rows]
    term_docs = [TOKEN_RE.findall(document.lower()) for document in documents]
    document_frequency = {}
    for terms in term_docs:
        for term in set(terms): document_frequency[term] = document_frequency.get(term, 0) + 1
    def vector(terms):
        counts = {term: terms.count(term) for term in set(terms)}
        return {term: (1 + math.log(count)) * math.log((1 + len(term_docs)) / (1 + document_frequency[term])) for term, count in counts.items()}
    query_vector = vector(TOKEN_RE.findall(query.lower()))
    query_norm = math.sqrt(sum(value * value for value in query_vector.values()))
    scored = []
    for row, terms in zip(rows, term_docs):
        doc_vector = vector(terms)
        doc_norm = math.sqrt(sum(value * value for value in doc_vector.values()))
        denominator = query_norm * doc_norm
        score = sum(query_vector.get(term, 0.0) * value for term, value in doc_vector.items()) / denominator if denominator else 0.0
        if score > 0: scored.append((score, row))
    return sorted(scored, key=lambda item: item[0], reverse=True)[:limit]
if __name__ == "__main__":
    raise SystemExit(main())
