import sys
from pathlib import Path
import uvicorn

# Ensure repository root is on sys.path so mock_target package imports resolve
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if __name__ == "__main__":
    uvicorn.run("mock_target.main:app", host="0.0.0.0", port=8001, reload=False)