from dataclasses import dataclass
import math


@dataclass
class ProductionRates:
    shots_per_day: int = 250
    node_deployments_per_day: int = 500
    node_pickups_per_day: int = 800


@dataclass
class ProductionSummary:
    deployment_days: int
    shooting_days: int
    pickup_days: int
    critical_path_days: int
    receiver_count: int
    shot_count: int
    shots_per_day: int
    node_deployments_per_day: int
    node_pickups_per_day: int

    #################################################################

    def summary(self):
        return "\n".join([
            "Production Summary",
            "",
            f"Receivers: {self.receiver_count}",
            f"Shots: {self.shot_count}",
            "",
            f"Deployment Days: {self.deployment_days}",
            f"Shooting Days: {self.shooting_days}",
            f"Pickup Days: {self.pickup_days}",
            "",
            f"Critical Path: {self.critical_path_days} days",
        ])


class ProductionModel:

    def __init__(self, rates):
        self.rates = rates

    #################################################################

    def estimate(self, acquisition_events, geometry):
        receiver_count = geometry.receiver_count
        shot_count = geometry.shot_count

        deployment_days = self._ceil_days(
            receiver_count,
            self.rates.node_deployments_per_day,
        )

        pickup_days = self._ceil_days(
            receiver_count,
            self.rates.node_pickups_per_day,
        )

        shooting_days = self._ceil_days(
            shot_count,
            self.rates.shots_per_day,
        )

        critical_path_days = max(
            deployment_days,
            shooting_days,
            pickup_days,
        )

        return ProductionSummary(
            deployment_days=deployment_days,
            shooting_days=shooting_days,
            pickup_days=pickup_days,
            critical_path_days=critical_path_days,
            receiver_count=receiver_count,
            shot_count=shot_count,
            shots_per_day=self.rates.shots_per_day,
            node_deployments_per_day=self.rates.node_deployments_per_day,
            node_pickups_per_day=self.rates.node_pickups_per_day,
        )

    #################################################################

    def _ceil_days(self, units, rate_per_day):
        if rate_per_day <= 0:
            raise ValueError("Production rates must be greater than zero")

        return math.ceil(units / rate_per_day)
