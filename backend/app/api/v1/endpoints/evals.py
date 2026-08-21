from app.models.domain import EnterpriseProfile
from fastapi import APIRouter, Depends
from app.core.security import get_current_user, get_current_organization
from app.evals.golden_eval import run_golden_evaluation_benchmark

router = APIRouter()

@router.get("/golden-benchmark", response_model=dict)
def get_golden_benchmark_metrics(current_user = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)):
    """
    Run hand-verified golden dataset evaluation benchmark.
    Returns precision, recall, deadline exact-match accuracy, and calibration confidence.
    """
    metrics = run_golden_evaluation_benchmark()
    return metrics

