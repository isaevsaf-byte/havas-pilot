"""Test type hints for key modules.

This test verifies that type hints are present and correctly defined
in priority modules: database, reid, detector, main, and pipeline.
"""

import sys
import inspect
from pathlib import Path

import pytest

# Project root on path
sys.path.insert(0, str(Path(__file__).parent.parent))


def check_function_signature_has_hints(func, param_names, has_return=True):
    """Check if function has type hints for specified parameters."""
    sig = inspect.signature(func)

    for param_name in param_names:
        param = sig.parameters.get(param_name)
        assert param is not None, f"Parameter '{param_name}' not found"
        assert param.annotation != inspect.Parameter.empty, \
            f"Parameter '{param_name}' missing type hint"

    if has_return:
        assert sig.return_annotation != inspect.Signature.empty, \
            f"Function {func.__name__} missing return type hint"


class TestDatabaseTypeHints:
    """Verify type hints in database.py"""

    def test_cosine_similarity_has_hints(self):
        """_cosine_similarity should have parameter and return type hints."""
        import ast
        import inspect

        # Read source to verify type hints are present
        source = inspect.getsource(inspect.getmodule(
            __import__("database")
        )._cosine_similarity)

        # Check that type hints are in the source
        assert "np.ndarray" in source, "Missing type hint for numpy array parameter"
        assert "-> float" in source, "Missing return type float"

    def test_localdb_find_similar_signature(self):
        """LocalDB.find_similar should have type hints."""
        import inspect
        # Just verify the signature has annotations by checking source
        source_file = Path(__file__).parent.parent / "database.py"
        source = source_file.read_text()

        assert "def find_similar(self, embedding: np.ndarray, threshold: float)" in source
        assert "-> Tuple[Optional[str], float]" in source

    def test_localdb_save_embedding_signature(self):
        """LocalDB.save_embedding should have type hints."""
        source_file = Path(__file__).parent.parent / "database.py"
        source = source_file.read_text()

        assert "def save_embedding(self, visitor_id: str, embedding: np.ndarray) -> None" in source

    def test_clouddb_log_visit_signature(self):
        """CloudDB.log_visit should have type hints."""
        source_file = Path(__file__).parent.parent / "database.py"
        source = source_file.read_text()

        assert "def log_visit(self, timestamp: str, direction: str, is_repeat: bool, visitor_id: str) -> None" in source

    def test_clouddb_log_heartbeat_signature(self):
        """CloudDB.log_heartbeat should have return type hint."""
        source_file = Path(__file__).parent.parent / "database.py"
        source = source_file.read_text()

        assert "def log_heartbeat(self) -> None" in source


class TestReIDTypeHints:
    """Verify type hints in reid.py"""

    def test_reid_check_signature(self):
        """ReIDChecker.check should have type hints."""
        source_file = Path(__file__).parent.parent / "reid.py"
        source = source_file.read_text()

        assert "def check(self, crop: np.ndarray, track_id: int) -> Optional[Dict[str, Any]]" in source

    def test_reid_get_embedding_signature(self):
        """ReIDChecker.get_embedding should have type hints."""
        source_file = Path(__file__).parent.parent / "reid.py"
        source = source_file.read_text()

        assert "def get_embedding(self, crop: np.ndarray) -> Optional[np.ndarray]" in source

    def test_reid_normalize_crop_signature(self):
        """ReIDChecker.normalize_crop should have type hints."""
        source_file = Path(__file__).parent.parent / "reid.py"
        source = source_file.read_text()

        assert "def normalize_crop(self, crop: np.ndarray) -> np.ndarray" in source


class TestDetectorTypeHints:
    """Verify type hints in detector.py"""

    def test_detector_detect_signature(self):
        """PersonDetector.detect should have type hints."""
        source_file = Path(__file__).parent.parent / "detector.py"
        source = source_file.read_text()

        assert "def detect(self, frame: Any) -> List[Dict[str, Any]]" in source

    def test_detector_is_good_crop_signature(self):
        """PersonDetector.is_good_crop should have type hints."""
        source_file = Path(__file__).parent.parent / "detector.py"
        source = source_file.read_text()

        assert "def is_good_crop(self, bbox: List[int]) -> bool" in source


class TestPipelineTypeHints:
    """Verify type hints in pipeline.py"""

    def test_process_frame_signature(self):
        """process_frame should have type hints."""
        source_file = Path(__file__).parent.parent / "pipeline.py"
        source = source_file.read_text()

        assert "def process_frame(frame: np.ndarray, detector: Any, tracker: Any) -> List[Dict[str, Any]]" in source

    def test_check_visitors_signature(self):
        """check_visitors should have type hints."""
        source_file = Path(__file__).parent.parent / "pipeline.py"
        source = source_file.read_text()

        # Check key type hints in the signature
        assert "tracks: List[Dict[str, Any]]" in source
        assert "frame: np.ndarray" in source
        assert "line_y: float" in source
        assert "event_queue: queue.Queue" in source
        assert "-> List[Dict[str, Any]]" in source

    def test_render_overlay_signature(self):
        """render_overlay should have type hints."""
        source_file = Path(__file__).parent.parent / "pipeline.py"
        source = source_file.read_text()

        assert "def render_overlay(frame: np.ndarray, tracks_with_results: List[Dict[str, Any]], line_y: float) -> None" in source

    def test_handle_heartbeat_signature(self):
        """handle_heartbeat should have type hints."""
        source_file = Path(__file__).parent.parent / "pipeline.py"
        source = source_file.read_text()

        assert "def handle_heartbeat(frame_count: int, event_queue: queue.Queue) -> int" in source


class TestMainTypeHints:
    """Verify type hints in main.py"""

    def test_connect_camera_signature(self):
        """connect_camera should have return type hint."""
        source_file = Path(__file__).parent.parent / "main.py"
        source = source_file.read_text()

        assert "def connect_camera() -> cv2.VideoCapture" in source

    def test_cloud_sender_signature(self):
        """cloud_sender should have type hints."""
        source_file = Path(__file__).parent.parent / "main.py"
        source = source_file.read_text()

        assert "def cloud_sender(cloud_db: CloudDB) -> None" in source

    def test_main_function_signature(self):
        """main function should have return type hint."""
        source_file = Path(__file__).parent.parent / "main.py"
        source = source_file.read_text()

        assert "def main() -> None" in source


class TestTypeImports:
    """Verify that necessary typing imports are present."""

    def test_database_has_type_imports(self):
        """database.py should import typing modules."""
        source_file = Path(__file__).parent.parent / "database.py"
        source = source_file.read_text()

        assert "from typing import Optional, Tuple" in source

    def test_reid_has_type_imports(self):
        """reid.py should import typing modules."""
        source_file = Path(__file__).parent.parent / "reid.py"
        source = source_file.read_text()

        assert "from typing import" in source
        assert "Optional" in source
        assert "Dict" in source

    def test_detector_has_type_imports(self):
        """detector.py should import typing modules."""
        source_file = Path(__file__).parent.parent / "detector.py"
        source = source_file.read_text()

        assert "from typing import List, Dict, Any" in source

    def test_pipeline_has_type_imports(self):
        """pipeline.py should import typing modules."""
        source_file = Path(__file__).parent.parent / "pipeline.py"
        source = source_file.read_text()

        assert "from typing import List, Dict, Any" in source
        assert "import queue" in source

    def test_main_has_type_imports(self):
        """main.py should import typing modules."""
        source_file = Path(__file__).parent.parent / "main.py"
        source = source_file.read_text()

        assert "from typing import" in source


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
