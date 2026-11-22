"""CSV downloads for spreadsheets, from flat pydantic models: the fields are the columns.

Text a spreadsheet would read as a formula (``=``, ``+``, ``-``, ``@``, tab or carriage return
first) gets a leading apostrophe, so a login or team name can't run anything when the file is
opened (CSV injection). Numbers are written as they are, so negative values stay numbers;
exact amounts (``Decimal``) without trailing zeros.
"""

import csv
import io
from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import Response
from pydantic import BaseModel

CSV: dict[int | str, dict[str, Any]] = {200: {"content": {"text/csv": {}}}}  # OpenAPI ``responses``

_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def csv_cell(value: object) -> str | int | float:
    match value:
        case None:
            return ""
        case bool():
            return "true" if value else "false"
        case int() | float():
            return value
        case Decimal():
            return f"{value.normalize():f}"  # 12.5, not 12.5000 or 1.25E+1
        case datetime() | date():
            return value.isoformat()
        case _:
            text = str(value)
            return f"'{text}" if text.startswith(_FORMULA_START) else text


def to_csv[M: BaseModel](model: type[M], rows: Iterable[M]) -> str:
    """The header comes from ``model``, so an empty export still names its columns."""
    columns = list(model.model_fields)
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(columns)
    writer.writerows([csv_cell(getattr(row, c)) for c in columns] for row in rows)
    return out.getvalue()


def csv_response[M: BaseModel](filename: str, model: type[M], rows: Iterable[M]) -> Response:
    return Response(
        content=to_csv(model, rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},
    )
