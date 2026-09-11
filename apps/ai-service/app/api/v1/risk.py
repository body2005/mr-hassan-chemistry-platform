from fastapi import APIRouter, Depends, Request
from app.core.security import verify_api_key
from app.schemas.risk import (
    BatchRiskPredictionRequest,
    BatchRiskPredictionResponse,
    RiskModelTrainRequest,
    RiskModelTrainResponse,
)
from app.services.risk_service import risk_engine
from app.traffic.rate_limiter import rate_limiter

router = APIRouter(prefix="/risk", tags=["Student Risk Predictive ML"])


@router.post("/predict", response_model=BatchRiskPredictionResponse, dependencies=[Depends(verify_api_key)])
async def predict_student_risk(
    request_data: BatchRiskPredictionRequest,
    request: Request
) -> BatchRiskPredictionResponse:
    """
    Evaluates student drop-off / academic risk using trained scikit-learn / XGBoost tabular models.
    Produces honest calibrated probabilities and student-specific risk factor explanations.
    """
    client_ip = request.client.host if request.client else "unknown_client"
    await rate_limiter.check_rate_limit(f"risk:{client_ip}", limit=60, window_seconds=60)

    return risk_engine.predict_student_risk(request_data.students)


@router.post("/train", response_model=RiskModelTrainResponse, dependencies=[Depends(verify_api_key)])
async def train_risk_model(
    request_data: RiskModelTrainRequest
) -> RiskModelTrainResponse:
    """
    Trains the risk prediction model on historical student records.
    Automatically applies StratifiedGroupKFold (if cohort_id is provided) or StratifiedKFold.
    """
    return risk_engine.train_model(request_data)
