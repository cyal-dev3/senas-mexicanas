import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from miratek.dataset import DatasetStore  # noqa: E402
from miratek.synthetic import fill_store  # noqa: E402,F401  (lo usan las pruebas)


@pytest.fixture
def store(tmp_path):
    return DatasetStore(tmp_path / "datos")
