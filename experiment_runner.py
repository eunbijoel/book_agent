#!/usr/bin/env python3
"""
Model Comparison Experiment Runner

Runs the same book generation across multiple LLM providers and compares results.

Usage:
    python experiment_runner.py \
        --input-file "agent/inputs/ai assistant.html" \
        --topic "반도체 AI 어시스턴트 개발 가이드" \
        --providers "ollama:gemma4:31b,gemini:gemini-2.5-flash,claude:claude-sonnet-4-6" \
        --chapters 3 --test-mode
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


class ExperimentRunner:

    def __init__(self, args: argparse.Namespace):
        self.input_file = args.input_file
        self.topic = args.topic
        self.chapters = args.chapters
        self.test_mode = args.test_mode
        self.words = args.words
        self.lang = args.lang
        self.experiment_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.experiment_dir = Path(args.output_dir) / self.experiment_id
        self.experiment_dir.mkdir(parents=True, exist_ok=True)
        self.results: list[dict] = []

    def parse_providers(self, providers_str: str) -> list[tuple[str, str]]:
        pairs = []
        for item in providers_str.split(","):
            item = item.strip()
            if ":" in item:
                provider, model = item.split(":", 1)
            else:
                defaults = {
                    "ollama": "gemma4:31b",
                    "gemini": "gemini-2.5-flash",
                    "claude": "claude-sonnet-4-6",
                    "openai": "gpt-4.1-mini",
                }
                provider = item
                model = defaults.get(provider, item)
            pairs.append((provider.strip(), model.strip()))
        return pairs

    def run_single(self, provider: str, model: str) -> dict:
        run_dir = self.experiment_dir / f"{provider}_{model.replace(':', '_').replace('/', '_')}"

        cmd = [
            sys.executable, "main.py",
            "--title", self.topic,
            "--topic", self.topic,
            "--input-file", self.input_file,
            "--provider", provider,
            "--model", model,
            "--chapters", str(self.chapters),
            "--words", self.words,
            "--lang", self.lang,
            "--output-dir", str(run_dir),
            "--no-check",
        ]
        if self.test_mode:
            cmd.append("--test-mode")

        print(f"\n{'='*60}")
        print(f"Running: {provider}:{model}")
        print(f"Output:  {run_dir}")
        print(f"{'='*60}\n")

        start = time.time()
        try:
            result = subprocess.run(
                cmd,
                capture_output=False,
                text=True,
                timeout=3600,
            )
            elapsed = time.time() - start
            success = result.returncode == 0
        except subprocess.TimeoutExpired:
            elapsed = time.time() - start
            success = False
            print(f"\nTIMEOUT after {elapsed/60:.1f} minutes")

        if success:
            return self.collect_results(provider, model, str(run_dir), elapsed)

        return {
            "provider": provider,
            "model": model,
            "generation_time_seconds": round(elapsed, 1),
            "success": False,
            "error": f"Process exited with code {result.returncode}" if 'result' in dir() else "Timeout",
        }

    def collect_results(self, provider: str, model: str, output_dir: str, elapsed: float) -> dict:
        run_path = Path(output_dir)
        book_dirs = [d for d in run_path.iterdir() if d.is_dir() and not d.name.startswith(".")]

        if not book_dirs:
            return {
                "provider": provider, "model": model,
                "generation_time_seconds": round(elapsed, 1),
                "success": False, "error": "No book output directory found",
            }

        book_dir = book_dirs[0]

        report_path = book_dir / "book_report.json"
        if not report_path.exists():
            return {
                "provider": provider, "model": model,
                "generation_time_seconds": round(elapsed, 1),
                "success": False, "error": "No book_report.json found",
            }

        report = json.loads(report_path.read_text(encoding="utf-8"))

        per_chapter = []
        for ch_score in report.get("chapter_scores", []):
            num = ch_score["number"]
            entry = {
                "number": num,
                "title": ch_score.get("title", ""),
                "quality_score": ch_score.get("score", 0),
                "word_count": ch_score.get("word_count", 0),
                "rewrites": ch_score.get("rewrites", 0),
                "faithfulness_score": ch_score.get("faithfulness_score"),
                "faithfulness_verdict": ch_score.get("faithfulness_verdict"),
            }

            quant_path = book_dir / f"chapter-{num:02d}-quantitative.json"
            if quant_path.exists():
                entry["quantitative_metrics"] = json.loads(quant_path.read_text(encoding="utf-8"))

            src_eval_path = book_dir / f"chapter-{num:02d}-source-evaluation.json"
            if src_eval_path.exists():
                entry["source_evaluation"] = json.loads(src_eval_path.read_text(encoding="utf-8"))

            per_chapter.append(entry)

        quality_scores = [ch["quality_score"] for ch in per_chapter if ch["quality_score"]]
        faith_scores = [ch["faithfulness_score"] for ch in per_chapter if ch.get("faithfulness_score")]
        word_counts = [ch["word_count"] for ch in per_chapter]
        wtr_values = [
            ch.get("quantitative_metrics", {}).get("word_target_ratio", 0)
            for ch in per_chapter
            if ch.get("quantitative_metrics")
        ]

        return {
            "provider": provider,
            "model": model,
            "success": True,
            "generation_time_seconds": round(elapsed, 1),
            "overall_quality_score": round(sum(quality_scores) / len(quality_scores), 1) if quality_scores else 0,
            "overall_source_faithfulness": round(sum(faith_scores) / len(faith_scores), 1) if faith_scores else None,
            "total_words": sum(word_counts),
            "total_chapters": len(per_chapter),
            "word_count_accuracy": round(sum(wtr_values) / len(wtr_values), 3) if wtr_values else None,
            "total_rewrites": sum(ch.get("rewrites", 0) for ch in per_chapter),
            "per_chapter": per_chapter,
        }

    def run_all(self, provider_model_pairs: list[tuple[str, str]]) -> None:
        total = len(provider_model_pairs)
        for i, (provider, model) in enumerate(provider_model_pairs, 1):
            print(f"\n[Experiment {i}/{total}]")
            result = self.run_single(provider, model)
            self.results.append(result)

            if result.get("success"):
                print(f"\nCompleted: {provider}:{model}")
                print(f"  Quality: {result.get('overall_quality_score', 'N/A')}")
                print(f"  Faithfulness: {result.get('overall_source_faithfulness', 'N/A')}")
                print(f"  Time: {result['generation_time_seconds']/60:.1f} min")
                print(f"  Words: {result.get('total_words', 0):,}")
            else:
                print(f"\nFailed: {provider}:{model} — {result.get('error', 'unknown')}")

    def generate_report(self) -> None:
        comparison_json = {
            "experiment_id": self.experiment_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "input_file": self.input_file,
            "topic": self.topic,
            "chapters": self.chapters,
            "test_mode": self.test_mode,
            "results": self.results,
            "rankings": self._compute_rankings(),
        }

        json_path = self.experiment_dir / "comparison.json"
        json_path.write_text(json.dumps(comparison_json, indent=2, ensure_ascii=False), encoding="utf-8")

        md_path = self.experiment_dir / "comparison.md"
        md_path.write_text(self._build_markdown_report(comparison_json), encoding="utf-8")

        print(f"\nComparison report: {md_path}")
        print(f"Comparison data:   {json_path}")

    def _compute_rankings(self) -> dict:
        successful = [r for r in self.results if r.get("success")]
        if not successful:
            return {"by_quality": [], "by_faithfulness": [], "by_speed": [], "overall_winner": None}

        by_quality = sorted(successful, key=lambda r: r.get("overall_quality_score", 0), reverse=True)
        by_speed = sorted(successful, key=lambda r: r.get("generation_time_seconds", float("inf")))

        has_faith = [r for r in successful if r.get("overall_source_faithfulness") is not None]
        by_faithfulness = sorted(has_faith, key=lambda r: r.get("overall_source_faithfulness", 0), reverse=True)

        fastest_time = by_speed[0]["generation_time_seconds"] if by_speed else 1

        def composite(r: dict) -> float:
            q = r.get("overall_quality_score", 0) / 100
            f = (r.get("overall_source_faithfulness") or 70) / 100
            speed_ratio = fastest_time / max(r.get("generation_time_seconds", 1), 1)
            return q * 0.4 + f * 0.4 + speed_ratio * 0.2

        overall = sorted(successful, key=composite, reverse=True)

        def _rank_entry(r: dict, score_key: str) -> dict:
            return {"provider": r["provider"], "model": r["model"], "score": r.get(score_key, 0)}

        return {
            "by_quality": [_rank_entry(r, "overall_quality_score") for r in by_quality],
            "by_faithfulness": [_rank_entry(r, "overall_source_faithfulness") for r in by_faithfulness],
            "by_speed": [{"provider": r["provider"], "model": r["model"], "seconds": r["generation_time_seconds"]} for r in by_speed],
            "overall_winner": {
                "provider": overall[0]["provider"],
                "model": overall[0]["model"],
                "composite_score": round(composite(overall[0]) * 100, 1),
            } if overall else None,
        }

    def _build_markdown_report(self, data: dict) -> str:
        lines = [
            f"# Model Comparison Report",
            f"*Experiment: {data['experiment_id']} | {data['timestamp'][:19]}*\n",
            "## Configuration\n",
            f"- **Input:** {data['input_file']}",
            f"- **Topic:** {data['topic']}",
            f"- **Chapters:** {data['chapters']}",
            f"- **Test mode:** {'Yes' if data['test_mode'] else 'No'}",
            "",
        ]

        successful = [r for r in data["results"] if r.get("success")]
        failed = [r for r in data["results"] if not r.get("success")]

        if successful:
            lines.append("## Summary Table\n")
            headers = ["Metric"] + [f"{r['provider']}:{r['model']}" for r in successful]
            lines.append("| " + " | ".join(headers) + " |")
            lines.append("|" + "|".join(["---"] * len(headers)) + "|")

            metrics = [
                ("Quality Score", lambda r: f"{r.get('overall_quality_score', 0):.1f}"),
                ("Source Faithfulness", lambda r: f"{r.get('overall_source_faithfulness', 'N/A')}"),
                ("Generation Time", lambda r: f"{r['generation_time_seconds']/60:.1f} min"),
                ("Total Words", lambda r: f"{r.get('total_words', 0):,}"),
                ("Word Target Accuracy", lambda r: f"{r.get('word_count_accuracy', 'N/A')}"),
                ("Total Rewrites", lambda r: str(r.get("total_rewrites", 0))),
            ]

            for name, fn in metrics:
                row = [name] + [fn(r) for r in successful]
                lines.append("| " + " | ".join(row) + " |")
            lines.append("")

            max_chapters = max(len(r.get("per_chapter", [])) for r in successful)
            for ch_idx in range(max_chapters):
                ch_num = ch_idx + 1
                titles = set()
                for r in successful:
                    chs = r.get("per_chapter", [])
                    if ch_idx < len(chs):
                        titles.add(chs[ch_idx].get("title", ""))
                ch_title = next(iter(titles), f"Chapter {ch_num}")

                lines.append(f"\n### Chapter {ch_num}: {ch_title[:40]}\n")
                ch_headers = ["Metric"] + [f"{r['provider']}" for r in successful]
                lines.append("| " + " | ".join(ch_headers) + " |")
                lines.append("|" + "|".join(["---"] * len(ch_headers)) + "|")

                ch_metrics = [
                    ("Quality", lambda r, i=ch_idx: f"{r.get('per_chapter', [{}])[i].get('quality_score', 0):.1f}" if i < len(r.get("per_chapter", [])) else "N/A"),
                    ("Faithfulness", lambda r, i=ch_idx: f"{r.get('per_chapter', [{}])[i].get('faithfulness_score', 'N/A')}" if i < len(r.get("per_chapter", [])) else "N/A"),
                    ("Words", lambda r, i=ch_idx: f"{r.get('per_chapter', [{}])[i].get('word_count', 0):,}" if i < len(r.get("per_chapter", [])) else "N/A"),
                    ("Rewrites", lambda r, i=ch_idx: str(r.get("per_chapter", [{}])[i].get("rewrites", 0)) if i < len(r.get("per_chapter", [])) else "N/A"),
                ]
                for name, fn in ch_metrics:
                    row = [name] + [fn(r) for r in successful]
                    lines.append("| " + " | ".join(row) + " |")
                lines.append("")

        rankings = data.get("rankings", {})
        if rankings:
            lines.append("## Rankings\n")
            by_q = rankings.get("by_quality", [])
            if by_q:
                lines.append(f"1. **Quality:** {by_q[0]['provider']}:{by_q[0]['model']} ({by_q[0]['score']:.1f})")
            by_f = rankings.get("by_faithfulness", [])
            if by_f:
                lines.append(f"2. **Faithfulness:** {by_f[0]['provider']}:{by_f[0]['model']} ({by_f[0]['score']})")
            by_s = rankings.get("by_speed", [])
            if by_s:
                lines.append(f"3. **Speed:** {by_s[0]['provider']}:{by_s[0]['model']} ({by_s[0]['seconds']/60:.1f} min)")
            lines.append("")

            winner = rankings.get("overall_winner")
            if winner:
                lines.append(f"## Overall Winner: {winner['provider']}:{winner['model']}")
                lines.append(f"Composite score: {winner['composite_score']}/100")
                lines.append("*(Quality 40% + Faithfulness 40% + Speed 20%)*")
            lines.append("")

        if failed:
            lines.append("## Failed Runs\n")
            for r in failed:
                lines.append(f"- **{r['provider']}:{r['model']}** — {r.get('error', 'unknown error')}")
            lines.append("")

        return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Model Comparison Experiment Runner")
    parser.add_argument("--input-file", required=True, help="Source file for book generation")
    parser.add_argument("--topic", required=True, help="Book topic")
    parser.add_argument("--providers", required=True, help="Comma-separated provider:model pairs")
    parser.add_argument("--chapters", type=int, default=3, help="Chapters per book")
    parser.add_argument("--test-mode", action="store_true", help="Use shorter chapters")
    parser.add_argument("--output-dir", default="./outputs/experiments", help="Experiment output directory")
    parser.add_argument("--words", default="3000-5000", help="Target words per chapter")
    parser.add_argument("--lang", default="ko", help="Writing language")
    args = parser.parse_args()

    runner = ExperimentRunner(args)
    pairs = runner.parse_providers(args.providers)

    print(f"Experiment ID: {runner.experiment_id}")
    print(f"Models to compare: {len(pairs)}")
    for p, m in pairs:
        print(f"  - {p}:{m}")
    print()

    start = time.time()
    runner.run_all(pairs)
    total_elapsed = time.time() - start

    runner.generate_report()

    print(f"\nTotal experiment time: {total_elapsed/60:.1f} minutes")
    print(f"Results: {runner.experiment_dir}")


if __name__ == "__main__":
    main()
