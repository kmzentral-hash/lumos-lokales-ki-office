from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from html import escape
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
EXPORTS_DIR = DATA_DIR / "exports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter(prefix="/api/v1/tables", tags=["tables"])


class TableInspectRequest(BaseModel):
    csv_content: str = Field(min_length=2, max_length=500000)
    delimiter: str = Field(default=",", max_length=5)


class ColumnSummary(BaseModel):
    name: str
    data_type: str
    min_value: float | None = None
    max_value: float | None = None
    sum_value: float | None = None
    avg_value: float | None = None


class TableInspectResponse(BaseModel):
    row_count: int
    column_count: int
    headers: list[str]
    columns: list[ColumnSummary]
    preview_rows: list[list[str]]


class TableAnalyzeRequest(BaseModel):
    csv_content: str = Field(min_length=2, max_length=500000)
    target_column: str | None = Field(default=None, max_length=100)
    operation: str = Field(default="sum", max_length=50)  # sum, avg, min, max, count


class TableAnalyzeResponse(BaseModel):
    success: bool
    operation: str
    target_column: str
    result_value: float
    formatted_result: str
    summary_html: str
    created_at: str


def parse_csv_rows(content: str, delimiter: str = ",") -> list[list[str]]:
    # Handle auto-detecting separator if needed
    if ";" in content and delimiter == ",":
        delimiter = ";"
    reader = csv.reader(io.StringIO(content.strip()), delimiter=delimiter)
    return [row for row in reader if row]


@router.post("/inspect", response_model=TableInspectResponse, name="inspect_table_data")
async def inspect_table_data(request: TableInspectRequest) -> TableInspectResponse:
    rows = parse_csv_rows(request.csv_content, request.delimiter)
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Die übergebenen Tabellendaten sind leer.",
        )

    headers = [col.strip() for col in rows[0]]
    data_rows = rows[1:]

    col_summaries: list[ColumnSummary] = []
    for col_idx, col_name in enumerate(headers):
        values = []
        is_numeric = True

        for r in data_rows:
            if col_idx < len(r) and r[col_idx].strip():
                raw_val = r[col_idx].strip().replace(",", ".").replace("€", "").replace(" ", "")
                try:
                    num = float(raw_val)
                    values.append(num)
                except ValueError:
                    is_numeric = False

        if is_numeric and values:
            c_min = round(min(values), 2)
            c_max = round(max(values), 2)
            c_sum = round(sum(values), 2)
            c_avg = round(c_sum / len(values), 2)
            col_summaries.append(
                ColumnSummary(
                    name=col_name,
                    data_type="numeric",
                    min_value=c_min,
                    max_value=c_max,
                    sum_value=c_sum,
                    avg_value=c_avg,
                )
            )
        else:
            col_summaries.append(ColumnSummary(name=col_name, data_type="text"))

    return TableInspectResponse(
        row_count=len(data_rows),
        column_count=len(headers),
        headers=headers,
        columns=col_summaries,
        preview_rows=data_rows[:10],
    )


@router.post("/analyze", response_model=TableAnalyzeResponse, name="analyze_table_data")
async def analyze_table_data(request: TableAnalyzeRequest) -> TableAnalyzeResponse:
    rows = parse_csv_rows(request.csv_content)
    if len(rows) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mindestens eine Kopfzeile und eine Datenzeile erforderlich.",
        )

    headers = [col.strip() for col in rows[0]]
    data_rows = rows[1:]

    target_col = request.target_column or headers[-1]
    if target_col not in headers:
        target_col = headers[-1]

    col_idx = headers.index(target_col)
    numbers = []
    for r in data_rows:
        if col_idx < len(r) and r[col_idx].strip():
            raw_val = r[col_idx].strip().replace(",", ".").replace("€", "").replace(" ", "")
            try:
                numbers.append(float(raw_val))
            except ValueError:
                pass

    if not numbers:
        result_val = float(len(data_rows))
        op_name = "count"
        fmt_res = f"{len(data_rows)} Zeilen"
    else:
        op_name = request.operation.lower()
        if op_name == "sum":
            result_val = round(sum(numbers), 2)
            fmt_res = f"{result_val:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
        elif op_name == "avg":
            result_val = round(sum(numbers) / len(numbers), 2)
            fmt_res = f"{result_val:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
        elif op_name == "min":
            result_val = round(min(numbers), 2)
            fmt_res = f"{result_val:,.2f}"
        elif op_name == "max":
            result_val = round(max(numbers), 2)
            fmt_res = f"{result_val:,.2f}"
        else:
            result_val = float(len(numbers))
            fmt_res = f"{int(result_val)} Werte"

    summary_html = f"""
<div class="table-summary-box">
  <div class="summary-head"><b>Kalkulation: {escape(target_col)}</b> (Operation: {escape(op_name.upper())})</div>
  <div class="summary-value">{escape(fmt_res)}</div>
  <div class="summary-meta">Ausgewertet aus {len(data_rows)} Tabellenzeilen</div>
</div>
""".strip()

    return TableAnalyzeResponse(
        success=True,
        operation=op_name,
        target_column=target_col,
        result_value=result_val,
        formatted_result=fmt_res,
        summary_html=summary_html,
        created_at=datetime.now(UTC).isoformat(),
    )


@router.post("/upload", response_model=TableInspectResponse, name="upload_table_file")
async def upload_table_file(file: UploadFile = File(...)) -> TableInspectResponse:  # noqa: B008
    content_bytes = await file.read()
    try:
        text_content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        text_content = content_bytes.decode("latin-1", errors="replace")

    return await inspect_table_data(TableInspectRequest(csv_content=text_content))
