"""Table hints (structural information about a table).

The goal is not to reproduce the table's appearance from the ODT, but to
give the SSG enough information to decide how to adapt it to the web:

- a "simple" table (rectangular grid, no merged cells) can safely be
  restyled, e.g. stacked into cards on narrow screens;
- a "complex" table (merged cells or ragged rows) usually has to keep its
  grid and scroll horizontally instead;
- the relative column shares tell which columns the author meant to be
  narrow or wide, independently of the printed page width.
"""
from __future__ import annotations

from dataclasses import dataclass

from .model import Table


@dataclass
class TableHints:
    cols: int
    rows: int
    header_rows: int
    # True when the grid is rectangular and has no merged cells.
    simple: bool
    # Relative width of each column as an integer percentage (sums to
    # about 100), or None when the widths are unknown for any column.
    col_shares: list[int] | None


def analyze_table(table: Table) -> TableHints:
    # covered cells are kept in the rows as placeholders, so len(cells)
    # is the logical column count of that row.
    cols = max((len(row.cells) for row in table.rows), default=0)
    has_merged = any(
        cell.colspan > 1 or cell.rowspan > 1
        for row in table.rows
        for cell in row.cells
        if not cell.covered
    )
    is_rectangular = all(len(row.cells) == cols for row in table.rows)

    col_shares = None
    widths = table.column_widths
    if widths and len(widths) == cols and all(widths) and sum(widths) > 0:
        total = sum(widths)
        col_shares = [round(100 * width / total) for width in widths]

    return TableHints(
        cols=cols,
        rows=len(table.rows),
        header_rows=sum(1 for row in table.rows if row.is_header),
        simple=is_rectangular and not has_merged,
        col_shares=col_shares,
    )