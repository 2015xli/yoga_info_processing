

import argparse
import dataclasses
import logging



from recommend_course_from_category import CategoryCourseRecommender

# --- Agent-specific Data Structures ---

@dataclasses.dataclass
class ComposeCourseRequest:
    """The request to the CategoryRecommenderAgent."""
    user_query: str

@dataclasses.dataclass
class ComposeCourseResponse:
    """The response from the CategoryRecommenderAgent."""
    composed_sequence: list[str]

# --- Agent Implementation ---

class CategoryRecommenderAgent:
    """
    An agent specialized in composing a new yoga sequence from categories based on a user query.
    """
    def __init__(self, api_type: str):
        self.recommender = CategoryCourseRecommender(api_type=api_type)

    def run(self, request: ComposeCourseRequest) -> ComposeCourseResponse:
        """
        The main execution logic for the agent.
        """
        logging.info(f"Agent received request to compose a course for query: '{request.user_query}'")
        
        # Use the recommender to generate a pose sequence.
        pose_sequence = self.recommender.recommend_course(request.user_query)
        
        if not pose_sequence:
            logging.warning("CategoryRecommender could not generate a sequence.")
            return ComposeCourseResponse(composed_sequence=[])

        logging.info(f"Successfully composed a sequence with {len(pose_sequence)} poses.")
        
        return ComposeCourseResponse(composed_sequence=pose_sequence)

    def close(self):
        """Clean up resources."""
        self.recommender.close()

def main():
    parser = argparse.ArgumentParser(description="Category Recommender Agent")
    parser.add_argument(
        "--query",
        type=str,
        default="I want to find my bodily balance and calm a scattered mind.",
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
        agent_instance = CategoryRecommenderAgent(api_type=args.api)
        request = ComposeCourseRequest(user_query=args.query)
        response = agent_instance.run(request)
        
        print("\n--- Category Recommender Agent Result ---")
        if not response.composed_sequence:
            print("Could not compose a course for the given query.")
        else:
            print("Composed Yoga Sequence:")
            for i, pose in enumerate(response.composed_sequence, 1):
                print(f"  {i}. {pose}")

    except Exception as e:
        logging.error(f"An error occurred during agent execution: {e}")
    finally:
        if agent_instance:
            agent_instance.close()

if __name__ == "__main__":
    main()

