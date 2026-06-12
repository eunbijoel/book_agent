#!/usr/bin/env python3
"""Generate static HTML library site from all completed books."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    parser = argparse.ArgumentParser(description="Generate book library site")
    parser.add_argument("--outputs", default="./outputs", help="Outputs directory")
    parser.add_argument("--out", default="./library_site", help="Library output directory")
    args = parser.parse_args()

    from web.services.library import generate_library

    templates_dir = Path(__file__).parent / "templates"
    result = generate_library(Path(args.outputs), Path(args.out), templates_dir)
    print(f"Library generated at: {result}")


if __name__ == "__main__":
    main()
