import asyncio
from app.infrastructure.graph import graph_db

async def add_index():
    print("Connecting to Neo4j...")
    await graph_db.connect()
    
    print("Creating constraint/index on Entity(id)...")
    # Using raw driver session to run schema operations if execute_query constructs transactions that prevent schema ops? 
    # Usually allowed.
    try:
        # Create constraint (which creates index)
        # Verify syntax for Neo4j version. Assuming 4.x/5.x
        query = "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE"
        await graph_db.execute_query(query)
        print("Constraint created.")
    except Exception as e:
        print(f"Error: {e}")
        
    await graph_db.close()

if __name__ == "__main__":
    asyncio.run(add_index())
