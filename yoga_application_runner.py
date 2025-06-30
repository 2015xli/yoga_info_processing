import argparse
import logging
import subprocess
import time
import requests
import re

from agents.course_finder.agent import CourseFinderAgent, FindCoursesRequest
from agents.category_recommender.agent import CategoryRecommenderAgent, ComposeCourseRequest

class YogaApplicationRunner:
    """
    Orchestrates the yoga recommendation process by coordinating with a FastAPI service and specialized agents.
    """
    def __init__(self, api_type: str, api_base_url: str):
        self.api_type = api_type
        self.api_base_url = api_base_url
        self.course_finder_agent = CourseFinderAgent(api_type=self.api_type)
        self.category_recommender_agent = CategoryRecommenderAgent(api_type=self.api_type)

    def _validate_sequence(self, sequence: list[str], user_query: str) -> list[str] | None:
        """
        Validates a sequence of poses by calling the pose checker API.

        Returns:
            A validated list of pose names, or None if the sequence is unacceptable.
        """
        validated_sequence = []
        removed_poses_count = 0
        max_removals_allowed = 2
        check_url = f"{self.api_base_url}/check-pose"

        for pose_name in sequence:
            try:
                payload = {"pose_name": pose_name, "user_query": user_query}
                logging.info(f"Attempting to check pose '{pose_name}' via API: {check_url} with payload {payload}")
                response = requests.post(check_url, json=payload, timeout=45)
                response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

                result = response.json()
                final_pose_name = result.get("final_pose_name")

                if final_pose_name:
                    validated_sequence.append(final_pose_name)
                    if result.get("was_replaced"):
                        logging.info(f"Pose '{pose_name}' was replaced with '{final_pose_name}'.")
                else:
                    removed_poses_count += 1
                    logging.warning(f"Pose '{pose_name}' was unsuitable and removed (no replacement found).")

            except requests.exceptions.ConnectionError as e:
                logging.error(f"Connection error checking pose '{pose_name}'. Is the server running at {check_url}? Error: {e}")
                removed_poses_count += 1
            except requests.exceptions.Timeout as e:
                logging.error(f"Timeout checking pose '{pose_name}'. Server took too long to respond. Error: {e}")
                removed_poses_count += 1
            except requests.exceptions.HTTPError as e:
                logging.error(f"HTTP error checking pose '{pose_name}': {e}. Response: {e.response.text}")
                removed_poses_count += 1
            except requests.exceptions.RequestException as e:
                logging.error(f"General request error checking pose '{pose_name}': {e}. It will be removed.")
                removed_poses_count += 1
            except Exception as e:
                logging.error(f"An unexpected error occurred while processing pose '{pose_name}': {e}. It will be removed.")
                removed_poses_count += 1

        if removed_poses_count > max_removals_allowed:
            logging.error(f"Course rejected: {removed_poses_count} poses were removed, which is more than the allowed {max_removals_allowed}.")
            return None
        
        return validated_sequence

    def run(self, user_query: str, max_retries: int = 2):
        """
        Executes the full recommendation and validation pipeline.
        """
        # --- Phase 1: Try to find an existing course ---
        logging.info("--- Phase 1: Searching for existing courses ---")
        find_req = FindCoursesRequest(user_query=user_query)
        find_res = self.course_finder_agent.run(find_req)

        for course in find_res.courses:
            logging.info(f"\nValidating candidate course: '{course.course_name}'")
            original_sequence = [p.pose_name for p in course.sequence]
            
            validated_sequence = self._validate_sequence(original_sequence, user_query)
            
            if validated_sequence:
                print("\n🎉 Found an acceptable existing course!")
                print(f"Course Name: {course.course_name}")
                print("Validated Pose Sequence:")
                for i, pose in enumerate(validated_sequence, 1):
                    print(f"  {i}. {pose}")
                return

        # --- Phase 2: Fallback to composing a new course ---
        logging.info("\n--- Phase 2: No suitable existing course found. Composing a new one. ---")
        for i in range(max_retries):
            logging.info(f"Attempt {i + 1} of {max_retries}...")
            compose_req = ComposeCourseRequest(user_query=user_query)
            compose_res = self.category_recommender_agent.run(compose_req)

            if not compose_res.composed_sequence:
                logging.warning("Category recommender failed to create a sequence. Retrying...")
                continue

            validated_sequence = self._validate_sequence(compose_res.composed_sequence, user_query)

            if validated_sequence:
                print("\n🎉 Successfully composed and validated a new course!")
                print("Composed Pose Sequence:")
                for i, pose in enumerate(validated_sequence, 1):
                    print(f"  {i}. {pose}")
                return

        # --- Phase 3: Failure ---
        print("\n😞 Sorry, after multiple attempts, we could not create a suitable yoga course for your query.")

    def close(self):
        self.course_finder_agent.close()
        self.category_recommender_agent.close()

def main():
    parser = argparse.ArgumentParser(description="Yoga Application Runner")
    parser.add_argument(
        "--query",
        type=str,
        default="I need a 30-minute session for strength, but I have a weak neck and can't do headstands.",
        help="The user's natural language query.",
    )
    parser.add_argument(
        "--api",
        type=str,
        choices=["openai", "deepseek"],
        default="deepseek",
        help="Specify which model API to use.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    api_server_process = None
    runner = None
    try:
        # Start the API server as a background process
        cmd = ["python", "-m", "services.pose_checker.server", "--api", args.api, "--port", "0", "--host", "127.0.0.1"]
        api_server_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        
        # Wait for the server to start and extract its address
        server_address = None
        for line in iter(api_server_process.stdout.readline, ''):
            logging.info(f"[API Server]: {line.strip()}")
            # Look for the line like: "Uvicorn running on http://127.0.0.1:54389"
            match = re.search(r"Uvicorn running on (http://[0-9\.:]+)", line)
            if match:
                server_address = match.group(1)
                logging.info(f"Detected API server running at: {server_address}")
                break
            if api_server_process.poll() is not None:
                logging.error("API server process terminated unexpectedly.")
                break
        
        if server_address is None:
            raise RuntimeError("Could not determine API server address after waiting.")

        # Initialize and run the application
        runner = YogaApplicationRunner(api_type=args.api, api_base_url=server_address)
        runner.run(user_query=args.query)

    except Exception as e:
        logging.error(f"An error occurred in the main runner: {e}")
    finally:
        if runner:
            runner.close()
        if api_server_process:
            api_server_process.terminate()
            api_server_process.wait()
            logging.info("API server has been shut down.")

if __name__ == "__main__":
    main()
