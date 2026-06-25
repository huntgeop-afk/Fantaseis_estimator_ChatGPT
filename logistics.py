from dataclasses import dataclass


@dataclass
class EquipmentInventory:
    """Represents transport inventory and weight assumptions for receiver nodes and pallets."""

    receiver_nodes: int
    node_weight_kg: float
    empty_pallet_weight_kg: float
    maximum_payload_per_pallet_kg: float
    active_receiver_nodes: int | None = None

    #################################################################

    def active_receiver_count(self):
        if self.active_receiver_nodes is not None:
            return int(self.active_receiver_nodes)
        return int(self.receiver_nodes)

    #################################################################

    def total_node_weight(self):
        return self.active_receiver_count() * self.node_weight_kg


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
    shipping_details: dict


@dataclass
class LogisticsSummary:
    """Summarizes expected transit time and transportation-only logistics costs."""

    shipping_weight_kg: float
    pallet_count: int
    outbound_shipping_distance_miles: float
    return_shipping_distance_miles: float
    shipping_distance_miles: float
    effective_shipping_rate_per_lb: float
    outbound_shipping_cost: float
    return_shipping_cost: float
    shipping_cost: float
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
            f"Outbound Shipping Distance (miles): {self.outbound_shipping_distance_miles:.2f}",
            f"Return Shipping Distance (miles): {self.return_shipping_distance_miles:.2f}",
            f"Shipping Distance (miles): {self.shipping_distance_miles:.2f}",
            f"Effective Shipping Rate ($/lb): {self.effective_shipping_rate_per_lb:.4f}",
            f"Outbound Shipping Cost: {self.outbound_shipping_cost:.2f}",
            f"Return Shipping Cost: {self.return_shipping_cost:.2f}",
            f"Total Shipping Cost: {self.shipping_cost:.2f}",
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
        shipping_details = dict(self.scenario.shipping_details)
        shipping_weight_lb = float(shipping_details.get("total_weight_lb", 0.0))
        shipping_weight_kg = shipping_weight_lb * 0.45359237
        pallet_count = int(shipping_details.get("pallet_count", 0))
        outbound_shipping_distance_miles = float(shipping_details.get("commercial_outbound_distance_miles", 0.0))
        return_shipping_distance_miles = float(shipping_details.get("commercial_return_distance_miles", 0.0))
        shipping_distance_miles = float(shipping_details.get("shipping_distance_miles", 0.0))
        effective_shipping_rate_per_lb = float(shipping_details.get("effective_shipping_rate_per_lb", 0.0))
        outbound_shipping_cost = float(shipping_details.get("commercial_outbound_cost", 0.0))
        return_shipping_cost = float(shipping_details.get("commercial_return_cost", 0.0))
        shipping_cost = float(shipping_details.get("commercial_shipping_cost", 0.0))

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

        transport_cost = float(shipping_details.get("selected_shipping_cost", 0.0))
        crew_cost = 0.0
        vehicle_cost = 0.0
        total_logistics_cost = transport_cost

        return LogisticsSummary(
            shipping_weight_kg=shipping_weight_kg,
            pallet_count=pallet_count,
            outbound_shipping_distance_miles=outbound_shipping_distance_miles,
            return_shipping_distance_miles=return_shipping_distance_miles,
            shipping_distance_miles=shipping_distance_miles,
            effective_shipping_rate_per_lb=effective_shipping_rate_per_lb,
            outbound_shipping_cost=outbound_shipping_cost,
            return_shipping_cost=return_shipping_cost,
            shipping_cost=shipping_cost,
            expected_outbound_days=expected_outbound_days,
            expected_return_days=expected_return_days,
            expected_total_transit_days=expected_total_transit_days,
            transport_cost=transport_cost,
            crew_cost=crew_cost,
            vehicle_cost=vehicle_cost,
            total_logistics_cost=total_logistics_cost,
            expected_node_rental_days=expected_node_rental_days,
        )

    #################################################################

    def _triangular_expected(self, minimum, most_likely, maximum):
        return (minimum + most_likely + maximum) / 3.0
