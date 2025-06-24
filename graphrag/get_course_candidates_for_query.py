import os
import json
from openai import OpenAI
from neo4j import GraphDatabase
import chromadb
from chromadb.utils import embedding_functions

# Configuration - Load from environment variables
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "12345678")
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "/home/xli/NAS/home/bin/yoga-info-processing/graphrag/chroma_db")
chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

# Initialize clients
PROMPT_FILE_PATH = "/home/xli/NAS/home/bin/yoga-info-processing/graphrag/get_user_query_key_info.prompt"
api_client = None
api_model = ""

def init_api_client(api_type: str):
    global api_model, api_client

    if api_type == 'deepseek':
        api_key = os.getenv('DEEPSEEK_API_KEY')
        if not api_key:
            raise RuntimeError("Missing DEEPSEEK_API_KEY")
        api_client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1"
        )
        api_model = "deepseek-chat"

    elif api_type == 'openai':
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise RuntimeError("Missing OPENAI_API_KEY")
        api_client = OpenAI(api_key=api_key)  # OpenAI default base_url is fine
        api_model = "gpt-3.5-turbo"

    else:
        raise ValueError("Unsupported API type")

def extract_query_info(user_query: str) -> dict:
    """Extract structured info from user query using OpenAI"""
    # Load prompt template
    with open(PROMPT_FILE_PATH, 'r') as f:
        prompt_template = f.read().format(query=user_query)
    
    # Call OpenAI API
    response = api_client.chat.completions.create(
        model=api_model,
        messages=[{"role": "user", "content": prompt_template}],
        temperature=0.0,
        response_format={"type": "json_object"}
    )
    
    # Parse and return structured data
    return json.loads(response.choices[0].message.content)

def search_courses_by_keywords(collection, keywords: list, k: int = 5) -> list:
    """Search ChromaDB collection for courses matching keywords"""
    course_names = set()
    for keyword in keywords:
        results = collection.query(
            query_texts=[keyword],
            n_results=k
        )
        course_names.update(results['ids'][0])
    return list(course_names)

def get_course_descriptions(course_names: list) -> dict:
    """Retrieve course descriptions from Neo4j"""
    with neo4j_driver.session() as session:
        result = session.run(
            "UNWIND $course_names AS name "
            "MATCH (c:Course {id: name}) "
            "RETURN c.id AS name, c.description AS description",
            course_names=course_names
        )
        return {record["name"]: record["description"] for record in result}

def filter_courses_by_llm(course_descriptions: dict, user_query: str) -> list:
    """Filter courses using OpenAI verification"""
    yes_courses = []
    na_courses = []
    
    for name, description in course_descriptions.items():
        prompt = (
            f"Please answer if the Yoga course matches the user's query for a training. "
            f"Course description: {description}\n"
            f"User query: {user_query}\n\n"
            "Answer only one of the three words: yes, no, or n/a"
        )
        
        response = api_client.chat.completions.create(
            model=api_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=5
        )
        
        answer = response.choices[0].message.content.strip().lower()
        if answer == "yes":
            yes_courses.append(name)
        elif answer == "n/a":
            na_courses.append(name)
    
    return yes_courses if yes_courses else na_courses

def get_course_candidates(user_query: str) -> list:
    """Main pipeline to get filtered course candidates"""
    # Step 1: Extract structured info from query
    query_info = extract_query_info(user_query)
    
    # Initialize Chroma collection
    emb_func = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    course_collection = chroma_client.get_collection(
        name="yoga_course",
        embedding_function=emb_func
    )
    
    # Step 2: Semantic search for candidates
    candidate_courses = set()
    
    # Search by objectives
    if query_info.get("objective"):
        candidate_courses.update(
            search_courses_by_keywords(
                course_collection,
                query_info["objective"],
                k=3
            )
        )
    
    # Search by body parts
    if query_info.get("physical body parts to train"):
        candidate_courses.update(
            search_courses_by_keywords(
                course_collection,
                query_info["physical body parts to train"],
                k=3
            )
        )
    
    if not candidate_courses:
        return []
    
    # Step 3: Filter courses using LLM verification
    course_descriptions = get_course_descriptions(list(candidate_courses))
    return filter_courses_by_llm(course_descriptions, user_query)

# Example usage
if __name__ == "__main__":
    #user_query = "I'm stressed and need a 15-minute relaxation sequence"
    user_query = "Please advise a sequence that helps me to enhance core"
    init_api_client("openai")
    candidates = get_course_candidates(user_query)
    print("Candidate courses:", candidates)
    neo4j_driver.close()