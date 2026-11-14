from backend.app.sql.schema_inspector import DatabaseSchemaLoader


def main():
    print("=" * 70)
    print("TESTING DATABASE SCHEMA INSPECTOR")
    print("=" * 70)

    loader = DatabaseSchemaLoader(
        host="localhost",
        port=5432,
        database="novamart",
        user="postgres",
        password="agentops",
    )

    print("\nConnecting to NovaMart PostgreSQL database...")
    print("Loading database schema...\n")

    schema = loader.load_schema()

    print(f"Database: {schema['database']}")
    print(f"Tables found: {len(schema['tables'])}")

    print("\n" + "-" * 70)

    for table_name, table_info in schema["tables"].items():

        print(f"\nTABLE: {table_name}")

        print("Primary keys:")
        print(f"   {table_info['primary_keys']}")

        print("Columns:")

        for column in table_info["columns"]:
            print(
                f"   - {column['column_name']}"
                f" | {column['data_type']}"
                f" | nullable={column['is_nullable']}"
            )

    print("\n" + "-" * 70)

    print("\nFOREIGN KEY RELATIONSHIPS:")

    if schema["foreign_keys"]:
        for relationship in schema["foreign_keys"]:
            print(
                f"   {relationship['source_table']}."
                f"{relationship['source_column']}"
                f" -> "
                f"{relationship['target_table']}."
                f"{relationship['target_column']}"
            )
    else:
        print("   No foreign-key relationships found.")

    print("\n" + "=" * 70)
    print("SCHEMA INSPECTOR TEST COMPLETED SUCCESSFULLY")
    print("=" * 70)


if __name__ == "__main__":
    main()