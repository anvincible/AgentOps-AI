
import csv
import getpass
import sys
from pathlib import Path

import psycopg

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.database_config import load_database_config

DATA_DIR = PROJECT_ROOT / "data" / "novamart" / "structured"

TABLE_ORDER = [
    "sellers",
    "customers",
    "marketing_campaigns",
    "products",
    "leads",
    "orders",
    "marketing_events",
    "order_items",
    "payments",
    "shipments",
    "support_tickets",
    "returns",
]


def main():
    config = load_database_config()

    print(
        f"Connecting to {config['host']}:{config['port']} "
        f"/ database {config['database']} as {config['user']}"
    )

    password = config["password"] or getpass.getpass(
        "PostgreSQL password: "
    )

    conn = psycopg.connect(
        host=config["host"],
        port=config["port"],
        dbname=config["database"],
        user=config["user"],
        password=password,
    )

    try:
        with conn.transaction():
            with conn.cursor() as cur:
                for table in TABLE_ORDER:
                    cur.execute(f'SELECT COUNT(*) FROM public."{table}"')
                    count = cur.fetchone()[0]

                    if count:
                        raise RuntimeError(
                            f"Table {table} already contains {count} rows. "
                            "Import cancelled to prevent duplicate data."
                        )

                for table in TABLE_ORDER:
                    path = DATA_DIR / f"{table}.csv"

                    if not path.is_file():
                        raise FileNotFoundError(f"Missing CSV: {path}")

                    with path.open(
                        "r", encoding="utf-8-sig", newline=""
                    ) as f:
                        reader = csv.reader(f)
                        headers = next(reader)

                        copy_sql = (
                            f'COPY public."{table}" '
                            f'({", ".join(chr(34) + h + chr(34) for h in headers)}) '
                            "FROM STDIN"
                        )

                        with cur.copy(copy_sql) as copy:
                            for row in reader:
                                copy.write_row([
                                    value if value != "" else None
                                    for value in row
                                ])

                    cur.execute(f'SELECT COUNT(*) FROM public."{table}"')
                    print(f"{table}: {cur.fetchone()[0]} rows imported")

        print("\nImport completed successfully.")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
