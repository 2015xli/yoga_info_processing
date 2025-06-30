
import argparse
import dataclasses
import logging
import os


from neo4j import GraphDatabase

from get_course_candidates_for_query import CourseFinder

# --- Agent-specific Data Structures ---

@dataclasses.dataclass
class PoseInSequence:
    """Represents a single pose within a course sequence."""
    pose_name: str
    order: int
    duration_seconds: int

@dataclasses.dataclass
class CourseCandidate:
    """Represents a full course candidate with its pose sequence."""
    course_name: str
    description: str
    challenge: str
    total_duration: str
    sequence: list[PoseInSequence]

@dataclasses.dataclass
class FindCoursesRequest:
    """The request to the CourseFinderAgent."""
    user_query: str

@dataclasses.dataclass
class FindCoursesResponse:
    """The response from the CourseFinderAgent."""
    courses: list[CourseCandidate]

# --- Neo4j Configuration ---
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "12345678")

class CourseFinderAgent:
    """
    An agent specialized in finding existing yoga courses based on a user query.
    """
    def __init__(self, api_type: str):
        self.finder = CourseFinder(api_type=api_type)
        self.neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    def _get_course_details(self, tx, course_names: list[str]) -> list[CourseCandidate]:
        """Retrieves full course details, including the pose sequence, from Neo4j."""
        # This query fetches the course and collects all its poses and their sequence details.
        query = """
        UNWIND $course_names AS course_name
        MATCH (c:Course {id: course_name})-[rel:INCLUDES_POSE]->(p:Pose)
        WITH c, rel, p
        ORDER BY rel.order
        RETURN c.id AS name, 
               c.description AS description, 
               c.challenge AS challenge, 
               c.total_duration AS total_duration, 
               collect({
                   pose_name: p.id, 
                   order: rel.order, 
                   duration_seconds: rel.duration_seconds
               }) AS sequence
        """
        results = tx.run(query, course_names=course_names)
        
        course_candidates = []
        for record in results:
            # The sequence from the record is already a list of dicts
            seq = [PoseInSequence(**pose_data) for pose_data in record["sequence"]]
            
            candidate = CourseCandidate(
                course_name=record["name"],
                description=record["description"],
                challenge=record["challenge"],
                total_duration=record["total_duration"],
                sequence=seq
            )
            course_candidates.append(candidate)
            
        return course_candidates

    def run(self, request: FindCoursesRequest) -> FindCoursesResponse:
        """
        The main execution logic for the agent.
        """
        logging.info(f"Agent received request to find courses for query: '{request.user_query}'")
        
        # Step 1: Use the CourseFinder to get initial candidate names.
        candidate_names = self.finder.find_candidates(request.user_query)
        
        if not candidate_names:
            logging.info("CourseFinder found no initial candidates.")
            return FindCoursesResponse(courses=[])

        logging.info(f"Found initial candidates: {candidate_names}")

        # Step 2: Retrieve the full course details, including pose sequences.
        with self.neo4j_driver.session() as session:
            full_course_details = session.execute_read(self._get_course_details, candidate_names)

        logging.info(f"Retrieved full details for {len(full_course_details)} courses.")
        
        return FindCoursesResponse(courses=full_course_details)

    def close(self):
        """Clean up resources."""
        self.finder.close()
        self.neo4j_driver.close()

def main():
    parser = argparse.ArgumentParser(description="Course Finder Agent")
    parser.add_argument(
        "--query",
        type=str,
        default="Suggest a 30-min yoga sequence to improve balance, but I have a sensitive wrist.",
        help="The user's query for a yoga course.",
    )
    parser.add_argument(
        "--api",
        type=str,
        choices=["openai", "deepseek"],
        default="deepseek",
        help="Specify which model API to use.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    agent_instance = None
    try:
        agent_instance = CourseFinderAgent(api_type=args.api)
        request = FindCoursesRequest(user_query=args.query)
        response = agent_instance.run(request)
        
        print("\n--- Course Finder Agent Result ---")
        if not response.courses:
            print("No courses found that match the criteria.")
        else:
            for course in response.courses:
                print(f"\nCourse: {course.course_name}")
                print(f"  Description: {course.description}")
                print(f"  Challenge: {course.challenge}")
                print(f"  Sequence Poses: {[p.pose_name for p in course.sequence]}")

    except Exception as e:
        logging.error(f"An error occurred during agent execution: {e}")
    finally:
        if agent_instance:
            agent_instance.close()

if __name__ == "__main__":
    main()
