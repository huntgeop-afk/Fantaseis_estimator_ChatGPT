from dataclasses import dataclass


@dataclass
class CostSummary:
    """Stores the final aggregated survey cost values from completed model outputs."""

    receiver_nodes: int
    shots: int
    field_days: int
    node_rental_cost: float
    logistics_cost: float
    labor_cost: float
    mobilization_cost: float
    hotel_cost: float
    per_diem_cost: float
    equipment_cost: float
    total_project_cost: float

    #################################################################

    def summary(self):
        return "\n".join([
            "Survey Cost Summary",
            f"Live Nodes Leased : {self.receiver_nodes}",
            f"Shots : {self.shots}",
            f"Field Days : {self.field_days}",
            f"Node Rental Cost : ${self.node_rental_cost:.2f}",
            f"Logistics Cost : ${self.logistics_cost:.2f}",
            f"Labor Cost : ${self.labor_cost:.2f}",
            f"Mobilization Cost : ${self.mobilization_cost:.2f}",
            f"Hotel Cost : ${self.hotel_cost:.2f}",
            f"Per Diem Cost : ${self.per_diem_cost:.2f}",
            f"Equipment Cost : ${self.equipment_cost:.2f}",
            "--------------------------------",
            f"Total Project Cost : ${self.total_project_cost:.2f}",
        ])


class CostModel:
    """Aggregates outputs from other models without performing subsystem calculations."""

    def __init__(self):
        pass

    #################################################################

    def estimate(
        self,
        geometry,
        production_summary,
        logistics_summary,
        node_rental_summary,
        labor_cost,
        mobilization_cost,
        hotel_cost,
        per_diem_cost,
        equipment_cost,
    ):
        receiver_nodes = self._live_receiver_nodes(geometry)
        shots = geometry.shot_count
        field_days = production_summary.critical_path_days
        node_rental_cost = node_rental_summary.total_node_cost
        logistics_cost = logistics_summary.total_logistics_cost

        total_project_cost = (
            node_rental_cost
            + logistics_cost
            + float(labor_cost)
            + float(mobilization_cost)
            + float(hotel_cost)
            + float(per_diem_cost)
            + float(equipment_cost)
        )

        return CostSummary(
            receiver_nodes=receiver_nodes,
            shots=shots,
            field_days=field_days,
            node_rental_cost=node_rental_cost,
            logistics_cost=logistics_cost,
            labor_cost=float(labor_cost),
            mobilization_cost=float(mobilization_cost),
            hotel_cost=float(hotel_cost),
            per_diem_cost=float(per_diem_cost),
            equipment_cost=float(equipment_cost),
            total_project_cost=total_project_cost,
        )

    #################################################################

    def _live_receiver_nodes(self, geometry):
        active_lines = int(getattr(getattr(geometry, "survey", None), "active_receiver_lines", 0) or 0)
        receivers = list(getattr(geometry, "receivers", []))

        if active_lines <= 0 or not receivers:
            return int(getattr(geometry, "receiver_count", 0) or 0)

        first_line = min(receiver.line for receiver in receivers)
        stations_per_line = sum(1 for receiver in receivers if receiver.line == first_line)

        return int(active_lines * stations_per_line)
