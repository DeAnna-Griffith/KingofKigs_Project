import redis
from redis.commands.search.aggregation import AggregateRequest 
from redis.commands.search import reducers
from redis.commands.search.field import TagField
from redis.commands.search.index_definition import IndexDefinition, IndexType


try:
    # Initialize the client (Adjust host, port, and password to match your setup)
    # decode_responses=True automatically converts bytes to Python strings
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
    
    # Force a network round-trip to verify connection
    if r.ping():
        print("Successfully connected to Redis!")
        
except redis.exceptions.ConnectionError as e:
    print(f"Failed to connect to Redis: {e}")



# Fashion

r.hset(
    name='ItemID:0001',
    mapping={
        'name': 'Coat',
        'price': 29.99,
        'category': 'Fashion',
        'inInventory': 40
    }
)


r.hset(
    name='ItemID:0002',
    mapping={
        'name': 'Dress',
        'price': 42.59,
        'category': 'Fashion',
        'inInventory': 20
    }
)


r.hset(
    name='ItemID:0003',
    mapping={
        'name': 'Jeans',
        'price': 19.38,
        'category': 'Fashion',
        'inInventory': 25
    }
)


r.hset(
    name='ItemID:0004',
    mapping={
        'name': 'Shoes',
        'price': 25.00,
        'category': 'Fashion',
        'inInventory': 50
    }
)



# Furniture

r.hset(
    name='ItemID:0005',
    mapping={
        'name': 'Couch',
        'price': 211.00,
        'category': 'Furniture',
        'inInventory': 8
    }
)


r.hset(
    name='ItemID:0006',
    mapping={
        'name': 'Table',
        'price': 79.97,
        'category': 'Furniture',
        'inInventory': 10
    }
)


r.hset(
    name='ItemID:0007',
    mapping={
        'name': 'Chair',
        'price': 59.99,
        'category': 'Furniture',
        'inInventory': 19
    }
)


r.hset(
    name='ItemID:0008',
    mapping={
        'name': 'Dresser',
        'price': 148.00,
        'category': 'Furniture',
        'inInventory': 12
    }
)



# Tech

r.hset(
    name='ItemID:0009',
    mapping={
        'name': 'Speaker',
        'price': 179.00,
        'category': 'Tech',
        'inInventory': 17
    }
)


r.hset(
    name='ItemID:0010',
    mapping={
        'name': 'Laptop',
        'price': 197.00,
        'category': 'Tech',
        'inInventory': 22
    }
)


r.hset(
    name='ItemID:0011',
    mapping={
        'name': 'Headphones',
        'price': 39.59,
        'category': 'Tech',
        'inInventory': 19
    }
)


r.hset(
    name='ItemID:0012',
    mapping={
        'name': 'TV',
        'price': 378.00,
        'category': 'Tech',
        'inInventory': 6
    }
)


r.hset(
    name='ItemID:0013',
    mapping={
        'name': 'Smart Phone',
        'price': 450.00,
        'category': 'Tech',
        'inInventory': 14
    }
)

# Creates index for search to use to know what data it is looking for
if "idx:ItemID" not in r.execute_command("FT._LIST"):
    search = r.ft("idx:ItemID").create_index(
        [
            TagField("category"),
        ],
        definition=IndexDefinition(
            prefix=["ItemID:"],
            index_type=IndexType.HASH
        )
    )
    print("Index created successfully!")
else:
    search = r.ft("idx:ItemID")
    print("Index already exists. Using existing index.")


req = (
    AggregateRequest('*') # means that it will search all of the items in database
    .load('name','category') #similar to select clause, must include attribute that your trying to use
    .filter("@category == 'Furniture'")
)

results = search.aggregate(req)

results = search.aggregate(req)
print("\n")
for row in results.rows:
    print(row)
print("\n")
# 3. Verify it worked by fetching the entire hash
user_data = r.hgetall('ItemID:0001')
print("Complete Hash:", user_data)

# 4. Fetch a single field from the hash
item_name = r.hget('ItemID:0001', 'name')
print("Item Name:", item_name)