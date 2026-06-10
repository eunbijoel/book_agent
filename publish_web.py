#!/usr/bin/env python3
"""
Publish a generated book as a browsable website.

Usage:
    python publish_web.py outputs/kz-travel-guide-ver1/
    python publish_web.py outputs/kz-travel-guide-ver1/ --serve
    python publish_web.py outputs/kz-travel-guide-ver1/ --deploy
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish a book as a website")
    parser.add_argument("book_dir", help="Path to the book output directory")
    parser.add_argument(
        "--output",
        default=None,
        help="Site output directory (default: <book_dir>/site)",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start a local preview server after building",
    )
    parser.add_argument(
        "--deploy",
        action="store_true",
        help="Deploy to GitHub Pages via mkdocs gh-deploy",
    )
    args = parser.parse_args()

    book_dir = Path(args.book_dir)
    if not book_dir.exists():
        print(f"Error: directory not found: {book_dir}")
        sys.exit(1)

    site_dir = Path(args.output) if args.output else book_dir / "site"

    from workflows.web_publisher import WebPublisher

    publisher = WebPublisher(site_dir)
    publisher.publish_from_files(book_dir)

    mkdocs_yml = site_dir / "mkdocs.yml"
    print(f"\nSite generated at: {site_dir}")
    print(f"MkDocs config:     {mkdocs_yml}")

    if args.serve:
        print("\nStarting local preview server...")
        print("Open http://127.0.0.1:8000 in your browser\n")
        subprocess.run(
            ["mkdocs", "serve", "-f", str(mkdocs_yml)],
            check=True,
        )
    elif args.deploy:
        print("\nDeploying to GitHub Pages...")
        subprocess.run(
            ["mkdocs", "gh-deploy", "-f", str(mkdocs_yml), "--force"],
            check=True,
        )
        print("Deployed successfully!")
    else:
        print(f"\nTo preview locally:  mkdocs serve -f {mkdocs_yml}")
        print(f"To deploy:           mkdocs gh-deploy -f {mkdocs_yml} --force")


if __name__ == "__main__":
    main()
