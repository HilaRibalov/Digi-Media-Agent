import os
from typing import Any, AsyncIterator, Dict, Iterator, Optional, Sequence, Tuple
from google.cloud import firestore
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    ChannelVersions
)
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

# Initialize Firestore client with explicit database name
db = firestore.Client(database="digi-media-db")

class FirestoreSaver(BaseCheckpointSaver):
    def __init__(self):
        super().__init__()
        self.serde = JsonPlusSerializer()

    def get_tuple(self, config: dict) -> Optional[CheckpointTuple]:
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = config["configurable"].get("checkpoint_id")
        
        doc_ref = db.collection("checkpoints").document(f"{thread_id}_{checkpoint_ns}")
        doc = doc_ref.get()
        if not doc.exists:
            return None
        
        data = doc.to_dict()
        if checkpoint_id and data.get("checkpoint_id") != checkpoint_id:
            # Simple implementation: only fetching the latest checkpoint for the given thread_id + ns
            return None
            
        if "checkpoint_bytes" not in data:
            return None
            
        return CheckpointTuple(
            config={"configurable": {"thread_id": thread_id, "checkpoint_ns": checkpoint_ns, "checkpoint_id": data.get("checkpoint_id")}},
            checkpoint=self.serde.loads_typed((data["checkpoint_type"], data["checkpoint_bytes"])),
            metadata=self.serde.loads_typed((data["metadata_type"], data["metadata_bytes"])) if "metadata_type" in data else {},
            parent_config=data.get("parent_config"),
            pending_writes=[],
        )

    def list(self, config: Optional[dict], *, filter: Optional[Dict[str, Any]] = None, before: Optional[dict] = None, limit: Optional[int] = None) -> Iterator[CheckpointTuple]:
        # Minimal implementation for simple usage
        if config and "thread_id" in config["configurable"]:
            thread_id = config["configurable"]["thread_id"]
            docs = db.collection("checkpoints").where("thread_id", "==", thread_id).stream()
            for doc in docs:
                data = doc.to_dict()
                yield CheckpointTuple(
                    config={"configurable": {"thread_id": thread_id, "checkpoint_ns": data.get("checkpoint_ns", ""), "checkpoint_id": data.get("checkpoint_id")}},
                    checkpoint=self.serde.loads_typed((data["checkpoint_type"], data["checkpoint_bytes"])),
                    metadata=self.serde.loads_typed((data["metadata_type"], data["metadata_bytes"])) if "metadata_type" in data else {},
                    parent_config=data.get("parent_config"),
                    pending_writes=[],
                )

    def put(self, config: dict, checkpoint: Checkpoint, metadata: CheckpointMetadata, new_versions: ChannelVersions) -> dict:
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = checkpoint["id"]
        
        cp_type, cp_bytes = self.serde.dumps_typed(checkpoint)
        meta_type, meta_bytes = self.serde.dumps_typed(metadata)
        
        db.collection("checkpoints").document(f"{thread_id}_{checkpoint_ns}").set({
            "thread_id": thread_id,
            "checkpoint_ns": checkpoint_ns,
            "checkpoint_id": checkpoint_id,
            "checkpoint_type": cp_type,
            "checkpoint_bytes": cp_bytes,
            "metadata_type": meta_type,
            "metadata_bytes": meta_bytes,
            "parent_config": config.get("configurable", {}).get("checkpoint_id")
        })
        
        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        }

    def put_writes(self, config: dict, writes: Sequence[Tuple[str, Any]], task_id: str, task_path: str = "") -> None:
        pass
        
