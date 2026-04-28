"""
seed_protocols.py — Seed Vertex AI Matching Engine with crisis protocol embeddings
Run once after creating your Vertex AI index.

Usage:
    python seed_protocols.py --project project-e82fa8f3-3868-42a9-a35 --region us-central1
"""
import argparse
import json
import os

# Protocol descriptions for embedding
PROTOCOL_DESCRIPTIONS = {
    "trauma": "mass trauma injury surgical emergency trauma bay activation bleeding hemorrhage",
    "cardiac_arrest": "code blue cardiac arrest CPR defibrillation heart failure resuscitation",
    "fire": "fire emergency RACE evacuation hazard flames smoke alarm",
    "respiratory": "respiratory distress breathing difficulty oxygen SpO2 intubation ventilator",
    "mass_casualty": "mass casualty incident MCI triage multiple patients disaster",
    "chemical_spill": "hazmat chemical spill toxic exposure decontamination PPE poison",
    "unknown": "general emergency medical urgent situation hospital staff",
}


def seed_protocols(project: str, region: str, index_id: str, endpoint_id: str):
    """Embed protocol descriptions and upsert to Vertex AI Matching Engine."""
    try:
        import vertexai
        from vertexai.language_models import TextEmbeddingModel
        from google.cloud import aiplatform

        vertexai.init(project=project, location=region)
        aiplatform.init(project=project, location=region)

        print(f"Generating embeddings for {len(PROTOCOL_DESCRIPTIONS)} protocols...")
        embed_model = TextEmbeddingModel.from_pretrained("textembedding-gecko@003")

        datapoints = []
        for protocol_key, description in PROTOCOL_DESCRIPTIONS.items():
            embeddings = embed_model.get_embeddings([description])
            vector = embeddings[0].values
            datapoints.append({
                "id": protocol_key,
                "feature_vector": vector,
            })
            print(f"  ✓ {protocol_key}: {len(vector)}-dim vector")

        # Upsert to Matching Engine
        index = aiplatform.MatchingEngineIndex(index_name=index_id)
        index.upsert_datapoints(datapoints=datapoints)

        print(f"\n✅ Seeded {len(datapoints)} protocol embeddings to index {index_id}")
        print("   Protocols: " + ", ".join(PROTOCOL_DESCRIPTIONS.keys()))

    except ImportError:
        print("⚠️  vertexai SDK not installed. Run: pip install google-cloud-aiplatform")
        _dump_mock_embeddings()
    except Exception as e:
        print(f"❌ Seeding failed: {e}")
        _dump_mock_embeddings()


def _dump_mock_embeddings():
    """Dump protocol descriptions as JSON for manual seeding."""
    output = "protocol_descriptions.json"
    with open(output, "w") as f:
        json.dump(PROTOCOL_DESCRIPTIONS, f, indent=2)
    print(f"\n📄 Protocol descriptions saved to {output}")
    print("   Upload these manually to your Vertex AI index.")


def create_matching_engine_index(project: str, region: str) -> str:
    """Create a Vertex AI Matching Engine index for protocols."""
    try:
        from google.cloud import aiplatform
        aiplatform.init(project=project, location=region)

        print("Creating Vertex AI Matching Engine index...")
        index = aiplatform.MatchingEngineIndex.create_tree_ah_index(
            display_name="crisis-protocols-index",
            contents_delta_uri="",
            dimensions=768,  # gecko@003 embedding size
            approximate_neighbors_count=5,
            distance_measure_type="DOT_PRODUCT_DISTANCE",
        )
        print(f"✅ Index created: {index.resource_name}")
        return index.resource_name
    except Exception as e:
        print(f"❌ Index creation failed: {e}")
        return ""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed crisis protocols into Vertex AI")
    parser.add_argument("--project", default="project-e82fa8f3-3868-42a9-a35")
    parser.add_argument("--region", default="us-central1")
    parser.add_argument("--index-id", default="", help="Vertex AI Matching Engine index resource name")
    parser.add_argument("--endpoint-id", default="", help="Deployed index endpoint resource name")
    parser.add_argument("--create-index", action="store_true", help="Create a new index first")

    args = parser.parse_args()

    if args.create_index:
        args.index_id = create_matching_engine_index(args.project, args.region)

    if args.index_id:
        seed_protocols(args.project, args.region, args.index_id, args.endpoint_id)
    else:
        print("ℹ️  No index ID provided. Dumping protocol descriptions as JSON.")
        _dump_mock_embeddings()
