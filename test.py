import redis
import json
import time

import redis

# Instantiate a Redis client, connecting to localhost on port 6379
r = redis.Redis(
    host='localhost',
    port=6379,
    db=0  # The default Redis database index
)

# 1. SET command: store a string under 'mykey'
r.set("mykey", "hello from Windows")

# 2. GET command: retrieve the value stored at 'mykey'
value = r.get("id")
print(value)   # Output is b'hello from Windows', since redis-py returns bytes.

# 3. Convert bytes to string
print(value.decode())  # prints "hello from Windows"

# 4. DEL command: remove 'mykey' from Redis
r.delete("mykey")