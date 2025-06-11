from neo4j import GraphDatabase

uri = "neo4j://localhost:7687"
auth = ("neo4j", "12345678")

try:
    driver = GraphDatabase.driver(uri, auth=auth)
    driver.verify_connectivity()
    print("✅ Connection established!")
    # Optionally perform a quick test query:
    with driver.session() as session:
        result = session.run("RETURN 1 AS result").single()
        print("Test query result:", result["result"])
except Exception as e:
    print("❌ Connection failed:", e)
finally:
    driver.close()
    print("Checked!")

