"""Verify the loaded product search index without modifying Redis data."""

from app.redis_db import INDEX_NAME, get_connection


def main():
    connection = get_connection()
    try:
        response = connection.execute_command(
            "FT.SEARCH",
            INDEX_NAME,
            "@category:{electronics}",
            "LIMIT",
            0,
            5,
        )
        total_matches = int(response["total_results"])
        if total_matches == 0:
            raise AssertionError("The electronics search returned no products")
        print(f"Product search index is working ({total_matches:,} electronics products).")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
