from dataclasses import dataclass
import math


@dataclass
class EquipmentInventory:
    """Represents transport inventory and weight assumptions for receiver nodes and pallets."""

    receiver_nodes: int
    node_weight_kg: float = 1.0
    empty_pallet_weight_kg: float = 35.0
    maximum_payload_per_pallet_kg: float = 500.0

    #################################################################

    def pallet_count(self):
        if self.maximum_payload_per_pallet_kg <= 0:
            raise ValueError("maximum_payload_per_pallet_kg must be greater than zero")

        return math.ceil(self.total_node_weight() / self.maximum_payload_per_pallet_kg)

    #################################################################

    def total_node_weight(self):
        return self.receiver_nodes * self.node_weight_kg

    #################################################################

    def total_shipping_weight(self):
        pallets = self.pallet_count()
        return self.total_node_weight() + pallets * self.empty_pallet_weight_kg


@dataclass
class LogisticsScenario:
    """Stores transportation assumptions for one outbound/return logistics scenario."""

    name: str
    transport_method: str
    outbound_days_min: float
    outbound_days_most_likely: float
    outbound_days_max: float
    return_days_min: float
    return_days_most_likely: float
    return_days_max: float
    transport_cost: float
    crew_members: int
    crew_daily_cost: float
    vehicle_cost_per_mile: float
    round_trip_miles: float


@dataclass
class LogisticsSummary:
    """Summarizes expected transit time and transportation-only logistics costs."""

    shipping_weight_kg: float
    pallet_count: int
    expected_outbound_days: float
    expected_return_days: float
    expected_total_transit_days: float
    transport_cost: float
    crew_cost: float
    vehicle_cost: float
    total_logistics_cost: float
    expected_node_rental_days: float

    #################################################################

    def summary(self):
        return "\n".join([
            "Logistics Summary",
            "",
            f"Shipping Weight (kg): {self.shipping_weight_kg:.2f}",
            f"Pallet Count: {self.pallet_count}",
            "",
            f"Expected Outbound Days: {self.expected_outbound_days:.2f}",
            f"Expected Return Days: {self.expected_return_days:.2f}",
            f"Expected Transit Days: {self.expected_total_transit_days:.2f}",
            f"Expected Node Rental Days: {self.expected_node_rental_days:.2f}",
            "",
            f"Transport Cost: {self.transport_cost:.2f}",
            f"Crew Cost: {self.crew_cost:.2f}",
            f"Vehicle Cost: {self.vehicle_cost:.2f}",
            f"Total Logistics Cost: {self.total_logistics_cost:.2f}",
        ])


class LogisticsModel:
    """Estimates transportation effort only: transit time and logistics cost components."""

    def __init__(self, inventory, scenario):
        self.inventory = inventory
        self.scenario = scenario

    #################################################################

    def estimate(self, field_days):
        shipping_weight_kg = self.inventory.total_shipping_weight()
        pallet_count = self.inventory.pallet_count()

        expected_outbound_days = self._triangular_expected(
            self.scenario.outbound_days_min,
            self.scenario.outbound_days_most_likely,
            self.scenario.outbound_days_max,
        )

        expected_return_days = self._triangular_expected(
            self.scenario.return_days_min,
            self.scenario.return_days_most_likely,
            self.scenario.return_days_max,
        )

        expected_total_transit_days = expected_outbound_days + expected_return_days
        expected_node_rental_days = field_days + expected_total_transit_days

        crew_cost = (
            self.scenario.crew_members *
            self.scenario.crew_daily_cost *
            expected_total_transit_days
        )

        vehicle_cost = self.scenario.vehicle_cost_per_mile * self.scenario.round_trip_miles

        total_logistics_cost = (
            self.scenario.transport_cost +
            crew_cost +
            vehicle_cost
        )

        return LogisticsSummary(
            shipping_weight_kg=shipping_weight_kg,
            pallet_count=pallet_count,
            expected_outbound_days=expected_outbound_days,
            expected_return_days=expected_return_days,
            expected_total_transit_days=expected_total_transit_days,
            transport_cost=self.scenario.transport_cost,
            crew_cost=crew_cost,
            vehicle_cost=vehicle_cost,
            total_logistics_cost=total_logistics_cost,
            expected_node_rental_days=expected_node_rental_days,
        )

    #################################################################

    def _triangular_expected(self, minimum, most_likely, maximum):
        return (minimum + most_likely + maximum) / 3.0
