import os, json
from neo4j import GraphDatabase
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

# Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "12345678")
INPUT_DATA_DIR = "/home/xli/NAS/home/bin/yoga-info-processing/graphrag"
CHROMA_PERSIST_DIR = f"{INPUT_DATA_DIR}/chroma_db"
POSE_JSON = f"{INPUT_DATA_DIR}/array_pose.json"
ATTRIBUTE_JSON = f"{INPUT_DATA_DIR}/array_attribute.json"
CATEGORY_JSON = f"{INPUT_DATA_DIR}/array_category.json"
CHALLENGE_JSON = f"{INPUT_DATA_DIR}/array_challenge.json"
COURSE_JSON = f"{INPUT_DATA_DIR}/array_course.json"
CHROMA_COLLECTION_POSE = "yoga_pose"
CHROMA_COLLECTION_COURSE = "yoga_course"
CHROMA_COLLECTION_CATEGORY = "yoga_category"

def delete_chroma_collection(chroma_client, collection_name: str):
    existing = [col.name for col in chroma_client.list_collections()]
    if collection_name in existing:
        chroma_client.delete_collection(collection_name)
        print(f"✅ Deleted collection: {collection_name}")
    else:
        print(f"⚠️ Collection not found: {collection_name} - skipping deletion")

def delete_neo4j_database(driver):
    """Clear existing data in Neo4j and ChromaDB"""
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")

def load_json_data(file_path):
    """Load JSON data from file"""
    with open(file_path) as f:
        return json.load(f)

def create_neo4j_nodes(tx, node_type, items, id_field):
    """Create nodes in Neo4j"""
    query = f"""
    UNWIND $items AS item
    MERGE (n:{node_type} {{id: item.{id_field}}})
    SET n += apoc.map.removeKeys(item, ['{id_field}'])
    """
    tx.run(query, items=items)

def link_pose_to_references(tx):
    """Create relationships between poses and reference nodes"""
    link_query = """
    MATCH (p:Pose), (ref:{reference_type} {{id: p.{reference_field}}})
    MERGE (p)-[:{relationship}]->(ref)
    """
    references = [
        ("Attribute", "attribute", "HAS_ATTRIBUTE"),
        ("Category", "category", "IN_CATEGORY"),
        ("Challenge", "challenge", "HAS_CHALLENGE")
    ]
    
    for ref_type, field, rel in references:
        tx.run(link_query.format(
            reference_type=ref_type,
            reference_field=field,
            relationship=rel
        ))

def create_pose_relationships(tx, pose):
    """Create relationships between poses"""
    relationships = {
        "BUILD_UP": pose.get("build_up", []),
        "MOVE_FORWARD": pose.get("move_forward", []),
        "BALANCE_OUT": pose.get("balance_out", []),
        "UNWIND": pose.get("unwind", [])
    }
    
    for rel_type, targets in relationships.items():
        for target in targets:
            tx.run("""
            MATCH (source:Pose {id: $source_name})
            MATCH (target:Pose {id: $target_name})
            MERGE (source)-[:%s]->(target)
            """ % rel_type,
            source_name=pose["name"],
            target_name=target)

# Update the create_course_nodes function
def create_course_nodes(tx, courses):
    """Create course nodes and relationships with support for repeated poses"""
    for course in courses:
        # Create course node
        tx.run("""
        MERGE (c:Course {id: $name})
        SET c += {
            challenge: $challenge,
            description: $description,
            total_duration: $total_duration
        }
        """, 
        name=course["name"],
        challenge=course["challenge"],
        description=course["description"],
        total_duration=course["total_duration"])
        
        # Create sequence relationships with unique identifiers
        for i, step in enumerate(course["sequence"]):
            # Generate unique relationship ID
            rel_id = f"{course['name']}_{step['pose']}_{i}"
            
            tx.run("""
            MATCH (c:Course {id: $course_name})
            MATCH (p:Pose {id: $pose_name})
            MERGE (c)-[rel:INCLUDES_POSE {
                id: $rel_id,
                order: $order
            }]->(p)
            SET rel += {
                duration_seconds: $duration_seconds,
                repeat_times: $repeat_times,
                transition_note: $transition_notes,
                action_note: $action_note
            }
            """,
            course_name=course["name"],
            pose_name=step["pose"],
            rel_id=rel_id,
            order=i+1,
            duration_seconds=step["duration_seconds"],
            repeat_times=step["repeat_times"],
            transition_notes=step["transition_notes"],
            action_note=step["action_note"])
        
        # Link course to challenge
        tx.run("""
        MATCH (c:Course {id: $name})
        MATCH (ch:Challenge {level: $challenge})
        MERGE (c)-[:HAS_CHALLENGE]->(ch)
        """,
        name=course["name"],
        challenge=course["challenge"])

def build_knowledge_graph(driver):
    """Main function to build the knowledge graph"""   
    # Load data
    pose_data = load_json_data(POSE_JSON)["pose"]
    attributes = load_json_data(ATTRIBUTE_JSON)["attribute"]
    categories = load_json_data(CATEGORY_JSON)["category"]
    challenges = load_json_data(CHALLENGE_JSON)["challenge"]
    courses = load_json_data(COURSE_JSON)["course"]
    
    with driver.session() as session:
        # Create reference nodes
        session.execute_write(create_neo4j_nodes, "Attribute", attributes, "name")
        session.execute_write(create_neo4j_nodes, "Category", categories, "name")
        session.execute_write(create_neo4j_nodes, "Challenge", challenges, "level")
        
        # Create pose nodes
        session.execute_write(create_neo4j_nodes, "Pose", pose_data, "name")

        # update the challenge property to long type to match Challenge.id
        session.execute_write(
            lambda tx: tx.run("""
                MATCH (p:Pose)
                SET p.challenge = toInteger(p.challenge)
                """))
        
        # update Attribute id to capital letter to match Pose.attribute
        session.execute_write(
            lambda tx: tx.run("""
                MATCH (a:Attribute)
                SET a.id = apoc.text.capitalize(a.id)
            """))
        
        # Link poses to references
        session.execute_write(link_pose_to_references)
        
        # Create inter-pose relationships
        for pose in pose_data:
            session.execute_write(create_pose_relationships, pose)

        # create courses
        session.execute_write(create_course_nodes, courses)

    driver.close()
    print("Knowledge graph built successfully!")
    print(f"Created {len(pose_data)} pose nodes")

def add_to_chroma(collection, pose):

    """Add pose fields to ChromaDB collection"""
    fields = {
        "name": pose["name"],
        "introduction": pose.get("introduction", ""),
        "steps": "\n".join(pose.get("steps", [])),
        "modification": pose.get("modification", ""),
        "caution": pose.get("caution", ""),
        "effects": pose.get("effects", ""),
        "practice_note": pose.get("practice_note", ""),
        "how_to_come_out": pose.get("how_to_come_out", "")
    }
    
    for field_name, text in fields.items():
        if text:
            collection.add(
                documents=[text],
                metadatas=[{"pose": pose["name"], "field": field_name}],
                ids=[f"{pose['name']}_{field_name}"]
            )

def build_pose_chroma_db(chroma_client):
    sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    collection = chroma_client.get_or_create_collection(
        name=CHROMA_COLLECTION_POSE,
        embedding_function=sentence_transformer_ef,
        metadata={"hnsw:space": "cosine"}
    )
    # Load data
    pose_data = load_json_data(POSE_JSON)["pose"]
    # Add to ChromaDB
    for pose in pose_data:
        add_to_chroma(collection, pose)

    print(f"Yoga pose ChromaDB collection contains {collection.count()} documents")

def build_category_chroma_db(chroma_client):
    """Build ChromaDB collection for yoga categories"""
    sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    collection = chroma_client.get_or_create_collection(
        name=CHROMA_COLLECTION_CATEGORY,
        embedding_function=sentence_transformer_ef,
        metadata={"hnsw:space": "cosine"}
    )
    
    # Load course data
    try:
        category_data = load_json_data(CATEGORY_JSON)["category"]
    except Exception as e:
        print(f"⚠️ Failed to load category data: {str(e)}")
        return
    
    # Add courses to collection
    for category in category_data:
        # Create a comprehensive document for semantic search
        guidelines = "\n".join(category.get("guidelines", []))
        
        document = (
            f"Category: {category['name']}\n"
            f"Introduction: {category['introduction']}\n"
            f"Guidelines:{guidelines}"
        )
        
        collection.add(
            documents=[document],
            ids=[category['name']],
            metadatas=[{
                "category": category['name']
            }]
        )
    
    print(f"Yoga category ChromaDB collection contains {collection.count()} documents")


def build_course_chroma_db(chroma_client):
    """Build ChromaDB collection for yoga courses"""
    sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    collection = chroma_client.get_or_create_collection(
        name=CHROMA_COLLECTION_COURSE,
        embedding_function=sentence_transformer_ef,
        metadata={"hnsw:space": "cosine"}
    )
    
    # Load course data
    try:
        course_data = load_json_data(COURSE_JSON)["course"]
    except Exception as e:
        print(f"⚠️ Failed to load course data: {str(e)}")
        return
    
    # Add courses to collection
    for course in course_data:
        # Create a comprehensive document for semantic search
        sequence_str = "\n".join(
            [f"{i+1}. {step['pose']} ({step['duration_seconds']}s)" 
             for i, step in enumerate(course['sequence'])]
        )
        
        document = (
            f"Course: {course['name']}\n"
            f"Challenge Level: {course['challenge']}\n"
            f"Total Duration: {course['total_duration']}\n"
            f"Description: {course['description']}\n"
            #f"Sequence:\n{sequence_str}"
        )
        
        collection.add(
            documents=[document],
            ids=[course['name']],
            metadatas=[{
                "course": course['name'],
                "challenge": course['challenge'],
                "duration": course['total_duration']
                }]
        )
    
    print(f"Yoga course ChromaDB collection contains {collection.count()} documents")


def check_neo4j_dbms_connection(driver):
    try:
        driver.verify_connectivity()
        print("✅ Connection established!")
        # Optionally perform a quick test query:
        with driver.session() as session:
            result = session.run("RETURN 1 AS result").single()
            print("Test query result:", result["result"])
    except Exception as e:
        print("❌ Connection failed:", e)
    finally:
        #driver.close()
        print("Checked!")

def check_chroma_dir_permission():
    import os, fcntl
    test_file = os.path.join(CHROMA_PERSIST_DIR, "locktest.txt")
    with open(test_file, "w") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            print("✅ Locking supported!")
            fcntl.flock(f, fcntl.LOCK_UN)
        except IOError:
            print("❌ Locking NOT supported on this filesystem!")

if __name__ == "__main__":

    # Initialize Neo4j driver and ChromaDB client
    check_chroma_dir_permission()
    chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    delete_chroma_collection(chroma_client, CHROMA_COLLECTION_POSE)
    build_pose_chroma_db(chroma_client)
    delete_chroma_collection(chroma_client, CHROMA_COLLECTION_COURSE) 
    build_course_chroma_db(chroma_client)
    delete_chroma_collection(chroma_client, CHROMA_COLLECTION_CATEGORY)     
    build_category_chroma_db(chroma_client)

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    check_neo4j_dbms_connection(driver)
    delete_neo4j_database(driver)
    build_knowledge_graph(driver)
    
