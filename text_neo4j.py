from database.neo4j_client import Neo4jClient

neo4j = Neo4jClient()
print("Connected:", neo4j.verify_connection())
neo4j.close()
