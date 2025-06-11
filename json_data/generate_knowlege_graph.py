import json
import argparse
from pathlib import Path
import openai
import re
from typing import Dict, List

class KnowledgeGraphBuilder:
    def __init__(self, input_file: str, api_provider: str = "deepseek"):
        self.input_path = Path(input_file)
        self.data_dir = self.input_path.parent
        self.output_dir = self.data_dir / "kg_output"
        self.output_dir.mkdir(exist_ok=True)
        self.api_provider = api_provider
        self.api_config = {
            "openai": {"model": "gpt-4o", "base_url": "https://api.openai.com/v1"},
            "deepseek": {"model": "deepseek-reasoner", "base_url": "https://api.deepseek.com/v1"}
        }
        self._load_input_data()
        self._init_api_client()

    def _load_input_data(self):
        """Load the input JSON file"""
        with open(self.input_path) as f:
            self.input_data = json.load(f)

    def _init_api_client(self):
        """Initialize the API client based on provider"""
        cfg = self.api_config[self.api_provider]
        openai.api_base = cfg["base_url"]
        openai.api_key = os.getenv("API_KEY")  # Set appropriate env var
        self.model_name = cfg["model"]

    @staticmethod
    def sanitize_id(name: str) -> str:
        """Convert names to valid knowledge graph IDs"""
        return re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')

    def _load_schema_and_template(self, node_type: str) -> tuple:
        """Load schema and prompt template for a node type"""
        try:
            with open(self.data_dir / f"schema_{node_type}.json") as f:
                schema = json.load(f)
            with open(self.data_dir / f"prompt_{node_type}.txt") as f:
                template = f.read()
            return schema, template
        except FileNotFoundError as e:
            raise RuntimeError(f"Missing required file: {e}")

    def _generate_pose_prompt(self, chunk: List[Dict], schema: Dict, template: str) -> str:
        """Generate API prompt for pose conversion"""
        return template.format(
            schema=json.dumps(schema, indent=2),
            poses=json.dumps(chunk, indent=2)
        )

    def _process_chunk(self, prompt: str) -> List[Dict]:
        """Process a chunk of data through API"""
        try:
            response = openai.ChatCompletion.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"API Error: {e}")
            return []

    def _process_poses(self, chunk_size=3):
        """Process pose data in chunks and save results"""
        all_poses = self.input_data.get("pose", {})
        schema, template = self._load_schema_and_template("pose")
        
        pose_items = list(all_poses.items())
        chunk_size = 3  # Optimal for context window
        processed = []
        
        for i in range(0, len(pose_items), chunk_size):
            chunk = pose_items[i:i+chunk_size]
            chunk_data = [{"name": name, **data} for name, data in chunk]
            prompt = self._generate_pose_prompt(chunk_data, schema, template)
            result = self._process_chunk(prompt)
            
            # Post-process results
            for pose in result:
                pose["id"] = f"pose:{self.sanitize_id(pose['name'])}"
                if "relationships" in pose:
                    for rel_type in ["prerequisites", "counter_poses", "progressions"]:
                        pose["relationships"][rel_type] = [
                            f"pose:{self.sanitize_id(name)}"
                            for name in pose["relationships"].get(rel_type, [])
                        ]
            processed.extend(result)
        
        # Save results
        output_file = self.output_dir / "node_pose.json"
        with open(output_file, "w") as f:
            json.dump(processed, f, indent=2)
        print(f"Processed {len(processed)} poses to {output_file}")

    def process_nodes(self, node_types: List[str]):
        """Process requested node types"""
        for node_type in node_types:
            if node_type == "pose":
                self._process_poses(chunk_size=3)
            else:
                print(f"Processing for {node_type} not implemented yet")


if __name__ == "__main__":
    
        """Entry point for command line execution"""
        parser = argparse.ArgumentParser(description="Knowledge Graph Builder")
        parser.add_argument("input_file", type=str, help="Path to input JSON file")
        parser.add_argument("--node", nargs="+", default=["pose"], 
                          choices=["pose", "category", "attribute", "health_issue", "anatomical"],
                          help="Node types to process")
        parser.add_argument("--api", choices=["openai", "deepseek"], default="deepseek",
                          help="API provider to use")
        args = parser.parse_args()

        builder = KnowledgeGraphBuilder(args.input_file, args.api)
        builder.process_nodes(args.node)
