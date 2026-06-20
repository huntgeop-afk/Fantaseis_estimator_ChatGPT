from dataclasses import dataclass


@dataclass
class CostSummary:
    """Stores the final aggregated survey cost values from completed model outputs."""

    receiver_nodes: int
    shots: int
    field_days: int
    node_rental_cost: float
    logistics_cost: float
    total_project_cost: float

    #################################################################

    def summary(self):
        return "\n".join([
            "Survey Cost Summary",
            f"Receiver Nodes : {self.receiver_nodes}",
            f"Shots : {self.shots}",
            f"Field Days : {self.field_days}",
            f"Node Rental Cost : ${self.node_rental_cost:.2f}",
            f"Logistics Cost : ${self.logistics_cost:.2f}",
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
    ):
        receiver_nodes = geometry.receiver_count
        shots = geometry.shot_count
        field_days = production_summary.critical_path_days
        node_rental_cost = node_rental_summary.total_node_cost
        logistics_cost = logistics_summary.total_logistics_cost

        total_project_cost = node_rental_cost + logistics_cost

        return CostSummary(
            receiver_nodes=receiver_nodes,
            shots=shots,
            field_days=field_days,
            node_rental_cost=node_rental_cost,
            logistics_cost=logistics_cost,
            total_project_cost=total_project_cost,
        )
