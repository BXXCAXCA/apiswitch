class GatewayError(Exception):
    error_type = "gateway_error"


class UnifiedModelNotFoundError(GatewayError):
    error_type = "unified_model_not_found"


class NoAvailableCandidateError(GatewayError):
    error_type = "no_available_candidate"


class BudgetExceededError(GatewayError):
    error_type = "budget_exceeded"
