from langchain_neo4j import Neo4jGraph, GraphCypherQAChain # Updated import
from langchain_chroma import Chroma  # Updated import
from langchain_huggingface import HuggingFaceEmbeddings  # Updated import
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
import os

# Configuration
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "12345678"
CHROMA_PERSIST_DIR = "/home/xli/NAS/home/bin/yoga-info-processing/graphrag/chroma_db"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # Set your OpenAI API key

# Initialize components
graph = Neo4jGraph(
    url=NEO4J_URI,
    username=NEO4J_USER,
    password=NEO4J_PASSWORD
)

# Initialize ChromaDB for poses and courses
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
pose_vectorstore = Chroma(
    collection_name="yoga_pose",
    persist_directory=CHROMA_PERSIST_DIR,
    embedding_function=embeddings
)
course_vectorstore = Chroma(
    collection_name="yoga_course",
    persist_directory=CHROMA_PERSIST_DIR,
    embedding_function=embeddings
)

# Initialize LLM
llm = ChatOpenAI(model="gpt-4-turbo", temperature=0, openai_api_key=OPENAI_API_KEY)

# Custom prompt template for yoga sequence generation
CYPHER_GENERATION_TEMPLATE = """
You are an expert yoga assistant helping users find safe and effective yoga sequences.
Your knowledge comes from a knowledge graph with the following structure:

Node types:
- Pose: Represents a yoga pose with properties: id (for name), challenge, introduction, steps, etc.
- Course: Represents a yoga sequence with properties: id (for name), challenge, description, duration

Relationship types:
- BUILD_UP: Suggested preparatory pose
- MOVE_FORWARD: Progression to deepen practice
- BALANCE_OUT: Counterpose to balance effects
- UNWIND: Easier/more relaxing next pose
- INCLUDES_POSE: Pose in course sequence (with order/duration)

Pose field meanings:
- CAUTION: Contraindications for certain conditions
- CHALLENGE: Difficulty level (1=easiest, 3=hardest)
- MODIFICATION: Variations for different situations
- EFFECTS: Physical/mental benefits
- PRACTICE_NOTE: Body positioning suggestions

User query: {question}

Based on the query, follow these steps:
1. Identify key requirements: 
   - Contraindications (e.g., wrist pain)
   - Duration preferences
2. Use this Cypher query to find relevant poses and sequences:

MATCH (p:Pose)
WHERE p.effects CONTAINS $body_area  // Target body area
AND NOT (p.caution CONTAINS $contraindication)  // Avoid contraindications
RETURN p.id AS pose, p.effects AS effects, p.modification AS modifications
LIMIT 20

3. For courses, use this query:
MATCH (c:Course)-[r:INCLUDES_POSE]->(p:Pose)
WHERE c.description CONTAINS $body_area
RETURN c.id AS course, COLLECT(p.id) AS poses, c.total_duration AS duration

4. Consider these guidelines:
   - Start with BUILD_UP poses
   - Progress to MOVE_FORWARD poses
   - Include BALANCE_OUT poses
   - End with UNWIND poses
   - Avoid poses with contraindications
   - Suggest modifications when needed

Return a Cypher query that will help answer the user's question.
"""

CYPHER_GENERATION_PROMPT = PromptTemplate(
    input_variables=["question"],
    template=CYPHER_GENERATION_TEMPLATE
)

# Initialize QA chain
chain = GraphCypherQAChain.from_llm(
    llm=llm,
    graph=graph,
    verbose=True,
    cypher_prompt=CYPHER_GENERATION_PROMPT,
    return_direct=True,  # Return graph results directly
    allow_dangerous_requests=True  # Acknowledge security risks
)

def find_relevant_poses(query: str, field: str = None, k: int = 5):
    """Find relevant poses using semantic search"""
    if field:
        results = pose_vectorstore.similarity_search(
            query, 
            k=k,
            filter={"field": field}
        )
    else:
        results = pose_vectorstore.similarity_search(query, k=k)
    
    return [{
        "pose": doc.metadata["pose"],
        "field": doc.metadata["field"],
        "content": doc.page_content
    } for doc in results]

def generate_safe_sequence(query: str):
    """Generate a safe yoga sequence based on user constraints"""
    # Extract contraindications using LLM
    contraindication_prompt = f"""
    Identify any physical contraindications mentioned in this query.
    Return ONLY the key contraindication terms or an empty string if none are found.
    
    Query: {query}
    Contraindications:
    """
    contraindications = llm.invoke(contraindication_prompt).content.lower()
    
    # Extract target body area
    target_prompt = f"""
    Identify the primary body area the user wants to strengthen in this yoga query. 
    Should not be any body area of physical contraindications.
    Return ONLY the body area or an empty string if not specified.
    
    Query: {query}
    Body area:
    """
    body_area = llm.invoke(target_prompt).content.lower()
    
    # Find relevant poses while avoiding contraindications
    contraindication_poses = set()
    if contraindications:
        # Find poses to avoid
        avoid_results = find_relevant_poses(contraindications, "caution", k=20)
        contraindication_poses = {item["pose"] for item in avoid_results}
    
    # Find beneficial poses
    beneficial_poses = find_relevant_poses(body_area, "effects", k=20) if body_area else []
    
    # Filter out contraindicated poses
    safe_poses = [pose for pose in beneficial_poses if pose["pose"] not in contraindication_poses]
    
    # Find relevant courses
    course_results = course_vectorstore.similarity_search(query, k=3)
    relevant_courses = [{
        "course": doc.metadata.get("name", ""),
        "content": doc.page_content
    } for doc in course_results]
    
    # Generate sequence using the knowledge graph
    graph_query = f"""
    I need a yoga sequence focusing on {body_area or 'general wellness'}.
    Avoid poses that involve: {contraindications or 'no specific contraindications'}.
    Don't require any props.
    """
    
    try:
        sequence_data = chain.invoke({"query": graph_query})
        sequence = sequence_data["result"]
    except Exception as e:
        print(f"Graph query failed: {e}")
        sequence = []
    
    # Format final response
    response = f"Here's a personalized yoga sequence focusing on {body_area}:\n\n"
    
    if sequence:
        response += "Graph-based sequence:\n"
        for i, pose in enumerate(sequence, 1):
            response += f"{i}. {pose['pose']} - Effects: {pose['effects']}\n"
            if pose['modifications']:
                response += f"   Modifications: {pose['modifications']}\n"
    else:
        response += "Couldn't generate a custom sequence from the graph. "
        response += "Here are some relevant poses and courses instead:\n\n"
        
        response += "Recommended poses:\n"
        for i, pose in enumerate(safe_poses[:5], 1):
            response += f"{i}. {pose['pose']} ({pose['field']}: {pose['content'][:100]}...)\n"
        
        response += "\nRelevant courses:\n"
        for i, course in enumerate(relevant_courses, 1):
            response += f"{i}. {course['course']}\n   Description: {course['content'][:100]}...\n"
    
    # Add safety notes
    if contraindications:
        response += f"\nSafety Note: This sequence avoids poses that might aggravate {contraindications}. "
        response += "Always listen to your body and modify as needed."
    
    return response

# Example usage
if __name__ == "__main__":
    query = "suggest a yoga sequence. I have wrist pain so training with wrist should avoided in the sequence."
    print(generate_safe_sequence(query))