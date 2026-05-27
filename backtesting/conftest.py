import sys
from pathlib import Path

# Allow `import backtester`, `import data_loader`, etc. from tests/
sys.path.insert(0, str(Path(__file__).parent))
