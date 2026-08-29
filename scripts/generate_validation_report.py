import sys
from pathlib import Path

# Add paths
root = Path(__file__).resolve().parent.parent
sys.path.extend([str(root / "core"), str(root / "apps" / "api"), str(root / "integrations" / "razorpay"), str(root / "simulator")])

from merchantos_core.config import Settings
from merchantos_core.validation.runner import ValidationRunner

runner = ValidationRunner()
settings = Settings(_env_file=None, razorpay_use_mock=True, llm_use_mock=True)
report = runner.run(scope="all", settings=settings)
print(f"Generated validation report: status={report.overall_status}, checks={len(report.results)}")
