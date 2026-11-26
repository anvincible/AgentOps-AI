"""
Read-only Data Explorer endpoints for AgentOps AI.

Security:
- Strict explicit table allowlist.
- Parameterized SQL queries for all filtering, searching, and pagination.
- Column name validation against table schema for ORDER BY to prevent SQL injection.
- Read-only execution preserving all existing database records and SQL Agent behaviour.
"""

from typing import Any
import logging
from decimal import Decimal
from datetime import date, datetime
from fastapi import APIRouter, HTTPException, Query
import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from backend.app.database_config import load_database_config
from backend.app.safe_logging import log_sanitized_exception

logger = logging.getLogger(__name__)

router = APIRouter(tags=["data"])

ALLOWED_TABLES: set[str] = {
    "customers",
    "leads",
    "marketing_campaigns",
    "marketing_events",
    "order_items",
    "orders",
    "payments",
    "products",
    "returns",
    "sellers",
    "shipments",
    "support_tickets",
}


def _get_connection():
    config = load_database_config()
    db_params = dict(config)
    if "database" in db_params:
        db_params["dbname"] = db_params.pop("database")
    return psycopg.connect(**db_params, row_factory=dict_row)


def _serialize_value(val: Any) -> Any:
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, (date, datetime)):
        return val.isoformat()
    return val


def _get_table_columns(cur, table_name: str) -> list[dict[str, Any]]:
    cur.execute("""
        SELECT 
            column_name, 
            data_type, 
            is_nullable
        FROM information_schema.columns 
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position;
    """, (table_name,))
    return cur.fetchall()


@router.get("/data/schema")
@router.get("/api/data/schema")
def get_database_schema() -> dict[str, Any]:
    """Return catalogue of all 12 allowlisted tables with columns and record counts."""
    tables_info = []
    try:
        with _get_connection() as conn:
            with conn.cursor() as cur:
                for table_name in sorted(ALLOWED_TABLES):
                    columns = _get_table_columns(cur, table_name)
                    # Safe parameterized query on verified table identifier
                    cur.execute(
                        sql.SQL("SELECT COUNT(*) AS row_count FROM {}").format(
                            sql.Identifier(table_name)
                        )
                    )
                    count_row = cur.fetchone()
                    row_count = count_row["row_count"] if count_row else 0
                    tables_info.append({
                        "table_name": table_name,
                        "row_count": row_count,
                        "column_count": len(columns),
                        "columns": columns,
                    })
        return {"tables": tables_info}
    except Exception as exc:
        log_sanitized_exception(logger, "Failed to retrieve schema", exc)
        raise HTTPException(status_code=500, detail="Failed to retrieve database schema.") from None


@router.get("/data/tables/{table_name}")
@router.get("/api/data/tables/{table_name}")
def get_table_records(
    table_name: str,
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=20, ge=1, le=100, description="Records per page (max 100)"),
    search: str | None = Query(default=None, description="Search term across text fields"),
    sort_by: str | None = Query(default=None, description="Column name to sort by"),
    sort_order: str = Query(default="asc", pattern="^(asc|desc)$", description="Sort order"),
) -> dict[str, Any]:
    """Return paginated records for an allowlisted table with safe parameterized search & sorting."""
    t_name = table_name.lower().strip()
    if t_name not in ALLOWED_TABLES:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' is not in the allowed catalogue.")

    try:
        with _get_connection() as conn:
            with conn.cursor() as cur:
                columns = _get_table_columns(cur, t_name)
                valid_columns = {c["column_name"]: c["data_type"] for c in columns}

                # Build safe WHERE clause for search
                where_clauses = []
                params: list[Any] = []

                if search and search.strip():
                    search_term = f"%{search.strip()}%"
                    text_cols = [
                        col for col, dtype in valid_columns.items()
                        if any(t in dtype.lower() for t in ("char", "text", "varchar", "uuid"))
                    ]
                    if text_cols:
                        search_predicates = [
                            sql.SQL("{}::text ILIKE %s").format(sql.Identifier(col))
                            for col in text_cols
                        ]
                        where_clauses.append(sql.SQL("({})").format(sql.SQL(" OR ").join(search_predicates)))
                        params.extend([search_term] * len(text_cols))

                where_sql = sql.SQL("")
                if where_clauses:
                    where_sql = sql.SQL("WHERE ") + sql.SQL(" AND ").join(where_clauses)

                # Count matching rows
                count_query = sql.SQL("SELECT COUNT(*) AS total FROM {} {}").format(
                    sql.Identifier(t_name),
                    where_sql,
                )
                cur.execute(count_query, params)
                total_rows = cur.fetchone()["total"]

                # Build safe ORDER BY clause
                order_sql = sql.SQL("")
                if sort_by and sort_by in valid_columns:
                    direction = sql.SQL("DESC") if sort_order.lower() == "desc" else sql.SQL("ASC")
                    order_sql = sql.SQL("ORDER BY {} {}").format(sql.Identifier(sort_by), direction)
                else:
                    first_col = columns[0]["column_name"] if columns else "ctid"
                    order_sql = sql.SQL("ORDER BY {} ASC").format(sql.Identifier(first_col))

                # Pagination
                offset = (page - 1) * page_size
                query = sql.SQL("SELECT * FROM {} {} {} LIMIT %s OFFSET %s").format(
                    sql.Identifier(t_name),
                    where_sql,
                    order_sql,
                )
                query_params = list(params) + [page_size, offset]
                cur.execute(query, query_params)
                raw_rows = cur.fetchall()

                # Clean and serialize
                serialized_rows = [
                    {k: _serialize_value(v) for k, v in row.items()}
                    for row in raw_rows
                ]

                total_pages = (total_rows + page_size - 1) // page_size if total_rows > 0 else 1

                return {
                    "table_name": t_name,
                    "page": page,
                    "page_size": page_size,
                    "total_rows": total_rows,
                    "total_pages": total_pages,
                    "columns": [c["column_name"] for c in columns],
                    "column_details": columns,
                    "rows": serialized_rows,
                }
    except HTTPException:
        raise
    except Exception as exc:
        log_sanitized_exception(logger, f"Failed to retrieve records for table {t_name}", exc)
        raise HTTPException(status_code=500, detail="Failed to retrieve table records.") from None


@router.get("/data/tables/{table_name}/stats")
@router.get("/api/data/tables/{table_name}/stats")
def get_table_stats(table_name: str) -> dict[str, Any]:
    """Compute summary statistics for numeric and categorical columns of an allowlisted table."""
    t_name = table_name.lower().strip()
    if t_name not in ALLOWED_TABLES:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' is not in the allowed catalogue.")

    try:
        with _get_connection() as conn:
            with conn.cursor() as cur:
                columns = _get_table_columns(cur, t_name)

                # Total rows
                cur.execute(
                    sql.SQL("SELECT COUNT(*) AS total FROM {}").format(sql.Identifier(t_name))
                )
                total_rows = cur.fetchone()["total"]

                numeric_stats = []
                categorical_stats = []

                for col in columns:
                    c_name = col["column_name"]
                    c_type = col["data_type"].lower()

                    if any(t in c_type for t in ("numeric", "integer", "decimal", "real", "double", "bigint")):
                        cur.execute(
                            sql.SQL("""
                                SELECT 
                                    MIN({}) AS min_val, 
                                    MAX({}) AS max_val, 
                                    ROUND(AVG({})::numeric, 2) AS avg_val
                                FROM {} 
                                WHERE {} IS NOT NULL
                            """).format(
                                sql.Identifier(c_name),
                                sql.Identifier(c_name),
                                sql.Identifier(c_name),
                                sql.Identifier(t_name),
                                sql.Identifier(c_name),
                            )
                        )
                        stat = cur.fetchone()
                        if stat and stat["min_val"] is not None:
                            numeric_stats.append({
                                "column": c_name,
                                "type": c_type,
                                "min": _serialize_value(stat["min_val"]),
                                "max": _serialize_value(stat["max_val"]),
                                "avg": _serialize_value(stat["avg_val"]),
                            })

                    elif any(t in c_type for t in ("char", "text", "varchar")) and "id" not in c_name and "description" not in c_name:
                        cur.execute(
                            sql.SQL("""
                                SELECT {}, COUNT(*) AS count
                                FROM {}
                                WHERE {} IS NOT NULL
                                GROUP BY {}
                                ORDER BY count DESC
                                LIMIT 5
                            """).format(
                                sql.Identifier(c_name),
                                sql.Identifier(t_name),
                                sql.Identifier(c_name),
                                sql.Identifier(c_name),
                            )
                        )
                        top_vals = cur.fetchall()
                        if top_vals and len(top_vals) > 1:
                            categorical_stats.append({
                                "column": c_name,
                                "type": c_type,
                                "top_values": [
                                    {"value": str(row[c_name]), "count": row["count"]}
                                    for row in top_vals
                                ],
                            })

                return {
                    "table_name": t_name,
                    "total_rows": total_rows,
                    "column_count": len(columns),
                    "numeric_metrics": numeric_stats[:5],
                    "categorical_breakdowns": categorical_stats[:4],
                }
    except HTTPException:
        raise
    except Exception as exc:
        log_sanitized_exception(logger, f"Failed to compute stats for table {t_name}", exc)
        raise HTTPException(status_code=500, detail="Failed to compute table statistics.") from None
