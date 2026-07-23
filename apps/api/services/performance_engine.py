import os

from services.performance_engine_aggregation import _AggregationMixin
from services.performance_engine_user import _UserMetricsMixin


class PerformanceEngine(_UserMetricsMixin, _AggregationMixin):
    """
    SECTION 12: Strategic Performance Intelligence (30 Scientific Vectors).
    Calculates granular learning trajectories for enterprise talent mapping.
    """

    pass


performance_engine = PerformanceEngine()
