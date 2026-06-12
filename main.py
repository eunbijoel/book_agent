#!/usr/bin/env python3
"""
agent_book_writer_v2 — Multi-Agent Book Writer using LangGraph + Ollama

Usage:
    python main.py --title "My Book" --description "A book about X" --chapters 10
    python main.py --toc toc.json --model llama3.1:8b
    python main.py --toc toc.json --model llama3.2 --output-dir ./outputs
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import urllib.request
from pathlib import Path

import yaml

logger = logging.getLogger("book-writer-v2")


def setup_logging(output_dir: str) -> None:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%H:%M:%S")
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    file_handler = logging.FileHandler(Path(output_dir) / "book-writer.log")
    file_handler.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(console)
    root.addHandler(file_handler)


def check_ollama(model: str, base_url: str = "http://localhost:11434") -> bool:
    try:
        req = urllib.request.Request(f"{base_url}/api/tags")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        available = [m["name"] for m in data.get("models", [])]
        if any(model in name or name.startswith(model) for name in available):
            logger.info("Ollama OK — model '%s' available", model)
            return True
        logger.error(
            "Model '%s' not found in Ollama. Available: %s",
            model,
            ", ".join(available) or "(none)",
        )
        logger.error("Pull with: ollama pull %s", model)
        return False
    except Exception as e:
        logger.error("Cannot reach Ollama at %s: %s", base_url, e)
        logger.error("Start Ollama with: ollama serve")
        return False


def load_toc(toc_path: str) -> dict:
    path = Path(toc_path)
    if not path.exists():
        raise FileNotFoundError(f"TOC file not found: {toc_path}")
    with open(path, encoding="utf-8") as f:
        if path.suffix in (".yaml", ".yml"):
            return yaml.safe_load(f)
        return json.load(f)


def load_config(config_path: str) -> dict:
    path = Path(config_path)
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def build_initial_state(args: argparse.Namespace, toc: dict | None) -> dict:
    if toc:
        return {
            "title": toc["title"],
            "description": toc.get("description", ""),
            "language": toc.get("language", "English"),
            "words_per_chapter": toc.get("words_per_chapter", args.words),
            "num_chapters": len(toc.get("chapters", [])),
            "writing_guidelines": toc.get("writing_guidelines", []),
            "toc_chapters": toc.get("chapters", []),
            "output_dir": args.output_dir,
            "completed_chapters": [],
            "errors": [],
        }
    return {
        "title": args.title,
        "description": args.description,
        "language": args.lang,
        "words_per_chapter": args.words,
        "num_chapters": args.chapters,
        "writing_guidelines": [],
        "toc_chapters": [],
        "output_dir": args.output_dir,
        "completed_chapters": [],
        "errors": [],
    }


def print_book_summary(final_state: dict) -> None:
    completed = final_state.get("completed_chapters", [])
    scores = [ch.get("evaluation_score", 0) for ch in completed if ch.get("evaluation_score")]
    avg = sum(scores) / len(scores) if scores else 0.0
    total_words = sum(ch.get("word_count", 0) for ch in completed)

    print("\n" + "=" * 60)
    print(f"BOOK COMPLETE: {final_state.get('title', '')}")
    print("=" * 60)
    print(f"Chapters completed : {len(completed)}")
    print(f"Total words        : {total_words:,}")
    print(f"Average quality    : {avg:.1f}/100")
    print()
    print("Chapter scores:")
    for ch in completed:
        bar = "█" * int(ch.get("evaluation_score", 0) / 10)
        print(f"  Ch{ch['number']:02d} {ch['title'][:40]:<40} {ch.get('evaluation_score', 0):5.1f} {bar}")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Multi-Agent Book Writer v2 (LangGraph + Ollama)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument("--toc", help="Path to TOC JSON/YAML file")
    input_group.add_argument("--title", help="Book title (when not using --toc)")
    parser.add_argument("--topic", help="Book topic (auto-generates title if --title not given)")
    parser.add_argument("--description", default="", help="Book description")
    parser.add_argument("--chapters", type=int, default=5, help="Number of chapters (when not using --toc)")
    parser.add_argument("--model", default="gemma4:31b", help="Ollama model name")
    parser.add_argument("--base-url", default="http://localhost:11434", help="Ollama base URL")
    parser.add_argument("--output-dir", default="./outputs", help="Output directory")
    parser.add_argument("--words", default="3000-5000", help="Target words per chapter")
    parser.add_argument("--lang", "--language", default="ko", help="Writing language (e.g. ko, English)")
    parser.add_argument("--config", default="agent/configs/models.yaml", help="Model config file")
    parser.add_argument("--no-check", action="store_true", help="Skip Ollama availability check")
    parser.add_argument("--test-mode", action="store_true", help="Test mode: shorter chapters (1500-2500 words)")
    parser.add_argument("--publish", action="store_true", help="Generate a browsable web site after book completion")
    args = parser.parse_args()

    if args.topic and not args.title:
        args.title = args.topic
    if not args.description and args.topic:
        args.description = f"A comprehensive book about {args.topic}"

    LANG_MAP = {"ko": "Korean", "en": "English", "ja": "Japanese", "zh": "Chinese"}
    args.lang = LANG_MAP.get(args.lang, args.lang)

    if args.test_mode:
        args.words = "1500-2500"
        logger.info("Test mode: reduced word count to %s per chapter", args.words)

    if not args.toc and not args.title:
        parser.error("Provide --toc <file>, --title <title>, or --topic <topic>")

    setup_logging(args.output_dir)
    logger.info("agent_book_writer_v2 starting")
    logger.info("Model: %s | Output: %s", args.model, args.output_dir)

    if not args.no_check and not check_ollama(args.model, args.base_url):
        sys.exit(1)

    toc = None
    if args.toc:
        toc = load_toc(args.toc)
        logger.info("Loaded TOC: '%s' (%d chapters)", toc["title"], len(toc.get("chapters", [])))

    from agent.workflows.book_workflow import build_book_workflow
    from agent.workflows.output_manager import OutputManager

    config = {
        "model": args.model,
        "base_url": args.base_url,
    }

    workflow = build_book_workflow(config)
    initial_state = build_initial_state(args, toc)

    title = initial_state["title"]
    output_manager = OutputManager(args.output_dir, title)
    progress = output_manager.load_progress()

    logger.info("Starting book generation: '%s'", title)
    start_time = time.time()

    try:
        final_state = workflow.invoke(initial_state)
    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        sys.exit(1)
    except Exception:
        logger.exception("Workflow failed")
        sys.exit(1)

    completed = final_state.get("completed_chapters", [])
    for ch in completed:
        if ch["number"] not in progress.get("completed", []):
            output_manager.save_chapter(ch)
            progress.setdefault("completed", []).append(ch["number"])
            output_manager.save_progress(progress)

    output_manager.save_book_report(final_state)
    consolidated = output_manager.save_consolidated_outputs(final_state)

    elapsed = time.time() - start_time
    logger.info("Total time: %.1f minutes", elapsed / 60)

    print_book_summary(final_state)

    print("\nGenerated files:")
    for name, path in consolidated.items():
        print(f"  {name}: {path}")

    if args.publish:
        from agent.workflows.web_publisher import WebPublisher

        site_dir = Path(args.output_dir) / output_manager.book_slug / "site"
        publisher = WebPublisher(site_dir)
        publisher.publish_from_state(final_state)
        mkdocs_yml = site_dir / "mkdocs.yml"
        print(f"\n  Web site: {site_dir}")
        print(f"  Preview:  mkdocs serve -f {mkdocs_yml}")
        print(f"  Deploy:   mkdocs gh-deploy -f {mkdocs_yml} --force")


if __name__ == "__main__":
    main()
