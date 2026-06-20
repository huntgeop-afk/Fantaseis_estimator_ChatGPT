from dataclasses import dataclass


@dataclass
class NodeRentalRates:
    """Stores per-node rental and service fee assumptions for rented receiver nodes."""

    daily_rental_rate: float = 1.25
    prep_fee_per_node: float = 1.25
    download_fee_per_node: float = 1.25


@dataclass
class NodeRentalSummary:
    """Summarizes node rental duration, component costs, and total rental expense."""

    receiver_nodes: int
    rental_days: float
    daily_rental_rate: float
    prep_fee_per_node: float
    download_fee_per_node: float
    rental_cost: float
    prep_cost: float
    download_cost: float
    total_node_cost: float

    #################################################################

    def summary(self):
        return "\n".join([
            "Node Rental Summary",
            f"Receiver Nodes: {self.receiver_nodes}",
            f"Rental Days: {self.rental_days}",
            f"Rental Cost: ${self.rental_cost:.2f}",
            f"Preparation Cost: ${self.prep_cost:.2f}",
            f"Download Cost: ${self.download_cost:.2f}",
            f"Total Node Cost: ${self.total_node_cost:.2f}",
        ])


class NodeRentalModel:
    """Converts receiver count and rental duration into total node rental cost only."""

    def __init__(self, rates):
        self.rates = rates

    #################################################################

    def estimate(self, receiver_nodes, rental_days):
        rental_cost = (
            receiver_nodes *
            rental_days *
            self.rates.daily_rental_rate
        )

        prep_cost = receiver_nodes * self.rates.prep_fee_per_node

        download_cost = receiver_nodes * self.rates.download_fee_per_node

        total_node_cost = rental_cost + prep_cost + download_cost

        return NodeRentalSummary(
            receiver_nodes=receiver_nodes,
            rental_days=rental_days,
            daily_rental_rate=self.rates.daily_rental_rate,
            prep_fee_per_node=self.rates.prep_fee_per_node,
            download_fee_per_node=self.rates.download_fee_per_node,
            rental_cost=rental_cost,
            prep_cost=prep_cost,
            download_cost=download_cost,
            total_node_cost=total_node_cost,
        )
