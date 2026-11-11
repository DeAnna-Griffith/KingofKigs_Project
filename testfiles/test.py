"""Small Redis connection and string round-trip smoke check."""

from app.redis_db import get_connection


def main():
    connection = get_connection()
    key = "test:connection-smoke"
    expected = "hello from King of Kings"
    try:
        connection.set(key, expected)
        actual = connection.get(key)
        if actual != expected:
            raise AssertionError(f"Expected {expected!r}, got {actual!r}")
        print("Redis connection and string round-trip succeeded.")
    finally:
        connection.delete(key)
        connection.close()


if __name__ == "__main__":
    main()
