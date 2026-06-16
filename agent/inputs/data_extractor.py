from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from agent.inputs.base import BaseExtractor

logger = logging.getLogger(__name__)

_SUPPORTED = {".csv", ".xlsx", ".xls"}
_ROWS_PER_CHUNK = 50


class DataExtractor(BaseExtractor):
    """Extract and analyse structured data from CSV/Excel files."""

    def extract(self, source: str) -> dict[str, Any]:
        import pandas as pd

        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {source}")

        suffix = path.suffix.lower()
        if suffix not in _SUPPORTED:
            raise ValueError(f"Unsupported format: {suffix}. Supported: {', '.join(sorted(_SUPPORTED))}")

        if suffix == ".csv":
            df = pd.read_csv(path)
        else:
            df = pd.read_excel(path)

        if df.empty:
            raise ValueError(f"Empty dataset: {source}")

        summary = self._analyse(df)
        content = self._format_summary(summary)
        chunks = self._create_data_chunks(df)

        return {
            "source_type": suffix.lstrip("."),
            "source_path": str(path),
            "title": path.stem,
            "content": content,
            "content_length": len(content),
            "chunks": chunks,
            "data_summary": summary,
            "metadata": {
                "file_name": path.name,
                "rows": len(df),
                "columns": list(df.columns),
                "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            },
        }

    def _analyse(self, df) -> dict[str, Any]:
        import pandas as pd

        columns_info = []
        for col in df.columns:
            info: dict[str, Any] = {
                "name": col,
                "dtype": str(df[col].dtype),
                "null_count": int(df[col].isnull().sum()),
                "unique_count": int(df[col].nunique()),
                "sample_values": [
                    v if not isinstance(v, float) or not pd.isna(v) else None
                    for v in df[col].dropna().head(5).tolist()
                ],
            }

            if df[col].dtype.kind in "iufb":
                stats = df[col].describe()
                info["stats"] = {k: round(float(v), 4) for k, v in stats.items()}

            columns_info.append(info)

        numeric_cols = df.select_dtypes(include="number")
        correlations = {}
        if len(numeric_cols.columns) >= 2:
            corr = numeric_cols.corr()
            for i, c1 in enumerate(corr.columns):
                for c2 in corr.columns[i + 1:]:
                    val = corr.loc[c1, c2]
                    if abs(val) > 0.3:
                        correlations[f"{c1} <-> {c2}"] = round(float(val), 4)

        return {
            "shape": {"rows": len(df), "columns": len(df.columns)},
            "columns": columns_info,
            "correlations": correlations,
        }

    def _format_summary(self, summary: dict) -> str:
        lines = [
            f"Dataset: {summary['shape']['rows']} rows x {summary['shape']['columns']} columns",
            "",
            "Columns:",
        ]
        for col in summary["columns"]:
            line = f"  - {col['name']} ({col['dtype']}): {col['unique_count']} unique, {col['null_count']} nulls"
            if col.get("stats"):
                s = col["stats"]
                line += f", mean={s.get('mean', 'N/A')}, std={s.get('std', 'N/A')}"
            lines.append(line)

        if summary.get("correlations"):
            lines.append("")
            lines.append("Notable correlations:")
            for pair, val in summary["correlations"].items():
                lines.append(f"  - {pair}: {val}")

        return "\n".join(lines)

    def _create_data_chunks(self, df) -> list[dict]:
        chunks = []
        for start in range(0, len(df), _ROWS_PER_CHUNK):
            end = min(start + _ROWS_PER_CHUNK, len(df))
            subset = df.iloc[start:end]
            text = subset.to_string(index=False)
            chunks.append({
                "index": len(chunks),
                "text": text,
                "token_estimate": len(text.split()) * 2 // 3,
                "rows": f"{start}-{end}",
            })
        return chunks
