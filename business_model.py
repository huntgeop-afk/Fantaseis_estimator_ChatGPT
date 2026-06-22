import json
import math
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd


DEFAULT_BUSINESS_CONFIG = {
    "production": {
        "shots_per_day": 250,
        "node_deployments_per_day": 500,
        "node_pickups_per_day": 800,
    },
    "crew": {
        "crew_chief_daily_rate": 850.0,
        "node_team_members": 4,
        "node_team_daily_rate_per_person": 500.0,
        "traffic_control_personnel": 2,
        "traffic_control_daily_rate_per_person": 350.0,
    },
    "mobilization": {
        "home_base": "Cincinnati, Ohio",
        "home_base_latitude": 39.1031,
        "home_base_longitude": -84.5120,
        "one_way_mobilization_distance_miles": None,
        "mileage_rate_per_mile": 0.75,
        "round_trip": True,
        "road_factor": 1.20,
    },
    "travel": {
        "hotel_rooms_per_person": 0.5,
        "hotel_cost_per_room": 125.0,
        "per_diem_per_contractor_per_day": 65.0,
    },
    "equipment": {
        "source_equipment_daily_cost": 1800.0,
        "support_equipment_daily_cost": 900.0,
        "truck_daily_cost": 250.0,
        "insurance_daily_allocation": 200.0,
        "maintenance_daily_allocation": 140.0,
        "miscellaneous_daily_overhead": 125.0,
    },
    "node_logistics": {
        "node_rental_per_node_day": 1.25,
        "node_weight_lb": 2.205,
        "pallet_weight_lb": 77.16,
        "maximum_payload_per_pallet_lb": 1102.31,
        "commercial_shipping_cost_per_pound": 0.28,
        "commercial_shipping_days": 2.0,
        "owner_pickup_enabled": True,
        "owner_return_enabled": True,
        "pickup_driver_daily_rate": 650.0,
        "return_driver_daily_rate": 650.0,
        "pickup_days": 2.0,
        "return_days": 2.0,
    },
    "pricing": {
        "method": "desired_profit_margin",
        "desired_profit_margin": 0.25,
        "markup_percentage": 0.35,
    },
}


@dataclass(frozen=True)
class ProductionBusiness:
    shots_per_day: int
    node_deployments_per_day: int
    node_pickups_per_day: int


@dataclass(frozen=True)
class CrewBusiness:
    crew_chief_daily_rate: float
    node_team_members: int
    node_team_daily_rate_per_person: float
    traffic_control_personnel: int
    traffic_control_daily_rate_per_person: float

    @property
    def contractor_count(self):
        return 1 + self.node_team_members + self.traffic_control_personnel

    @property
    def daily_crew_chief_cost(self):
        return self.crew_chief_daily_rate

    @property
    def daily_node_team_cost(self):
        return self.node_team_members * self.node_team_daily_rate_per_person

    @property
    def daily_traffic_control_cost(self):
        return self.traffic_control_personnel * self.traffic_control_daily_rate_per_person

    @property
    def daily_total_crew_cost(self):
        return self.daily_crew_chief_cost + self.daily_node_team_cost + self.daily_traffic_control_cost


@dataclass(frozen=True)
class MobilizationBusiness:
    home_base: str
    home_base_latitude: float
    home_base_longitude: float
    one_way_mobilization_distance_miles: float | None
    mileage_rate_per_mile: float
    round_trip: bool
    road_factor: float


@dataclass(frozen=True)
class TravelBusiness:
    hotel_rooms_per_person: float
    hotel_cost_per_room: float
    per_diem_per_contractor_per_day: float


@dataclass(frozen=True)
class EquipmentBusiness:
    source_equipment_daily_cost: float
    support_equipment_daily_cost: float
    truck_daily_cost: float
    insurance_daily_allocation: float
    maintenance_daily_allocation: float
    miscellaneous_daily_overhead: float

    @property
    def daily_equipment_cost(self):
        return (
            self.source_equipment_daily_cost
            + self.support_equipment_daily_cost
            + self.truck_daily_cost
            + self.insurance_daily_allocation
            + self.maintenance_daily_allocation
            + self.miscellaneous_daily_overhead
        )


@dataclass(frozen=True)
class NodeLogisticsBusiness:
    node_rental_per_node_day: float
    node_weight_lb: float
    pallet_weight_lb: float
    maximum_payload_per_pallet_lb: float
    commercial_shipping_cost_per_pound: float
    commercial_shipping_days: float
    owner_pickup_enabled: bool
    owner_return_enabled: bool
    pickup_driver_daily_rate: float
    return_driver_daily_rate: float
    pickup_days: float
    return_days: float


@dataclass(frozen=True)
class PricingBusiness:
    method: str
    desired_profit_margin: float
    markup_percentage: float


class BusinessModel:
    """Single source of truth for all business assumptions and business-only calculations."""

    def __init__(self, project_folder):
        self.project_folder = Path(project_folder)
        self.business_path = self.project_folder / "business.json"
        self.config = self._load_or_create_config()
        self._validate(self.config)

        self.production = ProductionBusiness(**self.config["production"])
        self.crew = CrewBusiness(**self.config["crew"])
        self.mobilization = MobilizationBusiness(**self.config["mobilization"])
        self.travel = TravelBusiness(**self.config["travel"])
        self.equipment = EquipmentBusiness(**self.config["equipment"])
        self.node_logistics = NodeLogisticsBusiness(**self.config["node_logistics"])
        self.pricing = PricingBusiness(**self.config["pricing"])

    #################################################################

    def _load_or_create_config(self):
        if not self.business_path.exists():
            self.business_path.write_text(json.dumps(DEFAULT_BUSINESS_CONFIG, indent=2), encoding="utf-8")

        with open(self.business_path, "r", encoding="utf-8") as stream:
            return json.load(stream)

    #################################################################

    def _validate(self, config):
        required_sections = [
            "production",
            "crew",
            "mobilization",
            "travel",
            "equipment",
            "node_logistics",
            "pricing",
        ]

        for section in required_sections:
            if section not in config:
                raise ValueError(f"business.json missing required section: {section}")

        self._require_non_negative(config["crew"]["crew_chief_daily_rate"], "crew_chief_daily_rate")
        self._require_non_negative(config["crew"]["node_team_members"], "node_team_members")
        self._require_non_negative(config["crew"]["traffic_control_personnel"], "traffic_control_personnel")
        self._require_positive(config["mobilization"]["mileage_rate_per_mile"], "mileage_rate_per_mile")
        self._require_positive(config["mobilization"]["road_factor"], "road_factor")
        self._require_positive(config["travel"]["hotel_rooms_per_person"], "hotel_rooms_per_person")
        self._require_non_negative(config["travel"]["hotel_cost_per_room"], "hotel_cost_per_room")
        self._require_non_negative(config["travel"]["per_diem_per_contractor_per_day"], "per_diem_per_contractor_per_day")

        pricing_method = str(config["pricing"].get("method", "")).strip()
        if pricing_method not in {"desired_profit_margin", "markup_percentage"}:
            raise ValueError("pricing.method must be 'desired_profit_margin' or 'markup_percentage'")

    #################################################################

    def _require_positive(self, value, name):
        if float(value) <= 0.0:
            raise ValueError(f"{name} must be greater than zero")

    #################################################################

    def _require_non_negative(self, value, name):
        if float(value) < 0.0:
            raise ValueError(f"{name} must be non-negative")

    #################################################################

    @property
    def contractors_total(self):
        return self.crew.contractor_count

    #################################################################

    @property
    def vehicles_required(self):
        return 1 if self.contractors_total < 3 else 2

    #################################################################

    @property
    def rooms_required(self):
        return int(math.ceil(self.contractors_total * self.travel.hotel_rooms_per_person))

    #################################################################

    def one_way_mobilization_distance_miles(self, gis_project):
        override_distance = self.mobilization.one_way_mobilization_distance_miles
        if override_distance is not None:
            return float(override_distance)

        centroid_lat, centroid_lon = self._survey_centroid_lat_lon(gis_project)
        straight_line_miles = self._haversine_miles(
            self.mobilization.home_base_latitude,
            self.mobilization.home_base_longitude,
            centroid_lat,
            centroid_lon,
        )
        return straight_line_miles * self.mobilization.road_factor

    #################################################################

    def mobilization_cost(self, gis_project):
        base = (
            self.vehicles_required
            * self.one_way_mobilization_distance_miles(gis_project)
            * self.mobilization.mileage_rate_per_mile
        )
        if self.mobilization.round_trip:
            return base * 2.0
        return base

    #################################################################

    def hotel_cost(self, field_days):
        return self.rooms_required * self.travel.hotel_cost_per_room * float(field_days)

    #################################################################

    def per_diem_cost(self, field_days):
        return self.contractors_total * self.travel.per_diem_per_contractor_per_day * float(field_days)

    #################################################################

    def daily_crew_cost(self):
        return self.crew.daily_total_crew_cost

    #################################################################

    def total_crew_cost(self, field_days):
        return self.daily_crew_cost() * float(field_days)

    #################################################################

    def daily_equipment_cost(self):
        return self.equipment.daily_equipment_cost

    #################################################################

    def total_equipment_cost(self, field_days):
        return self.daily_equipment_cost() * float(field_days)

    #################################################################

    def node_shipping_options(self, receiver_nodes):
        nodes = float(receiver_nodes)

        pallet_count = math.ceil((nodes * self.node_logistics.node_weight_lb) / self.node_logistics.maximum_payload_per_pallet_lb)
        total_weight_lb = nodes * self.node_logistics.node_weight_lb + pallet_count * self.node_logistics.pallet_weight_lb

        commercial_cost = total_weight_lb * self.node_logistics.commercial_shipping_cost_per_pound

        owner_pickup_cost = float("inf")
        owner_return_cost = float("inf")
        owner_outbound_days = self.node_logistics.pickup_days if self.node_logistics.owner_pickup_enabled else 0.0
        owner_return_days = self.node_logistics.return_days if self.node_logistics.owner_return_enabled else 0.0

        if self.node_logistics.owner_pickup_enabled:
            owner_pickup_cost = self.node_logistics.pickup_driver_daily_rate * self.node_logistics.pickup_days

        if self.node_logistics.owner_return_enabled:
            owner_return_cost = self.node_logistics.return_driver_daily_rate * self.node_logistics.return_days

        owner_total_cost = 0.0
        if owner_pickup_cost != float("inf"):
            owner_total_cost += owner_pickup_cost
        if owner_return_cost != float("inf"):
            owner_total_cost += owner_return_cost

        choose_owner = False
        if owner_total_cost > 0.0 and owner_total_cost < commercial_cost:
            choose_owner = True

        selected_shipping_cost = owner_total_cost if choose_owner else commercial_cost
        selected_outbound_days = owner_outbound_days if choose_owner else self.node_logistics.commercial_shipping_days
        selected_return_days = owner_return_days if choose_owner else self.node_logistics.commercial_shipping_days
        selected_shipping_days = selected_outbound_days + selected_return_days
        selected_method = "owner" if choose_owner else "commercial"

        return {
            "pallet_count": int(pallet_count),
            "total_weight_lb": total_weight_lb,
            "commercial_shipping_cost": commercial_cost,
            "commercial_shipping_days": self.node_logistics.commercial_shipping_days,
            "owner_pickup_cost": 0.0 if owner_pickup_cost == float("inf") else owner_pickup_cost,
            "owner_return_cost": 0.0 if owner_return_cost == float("inf") else owner_return_cost,
            "selected_shipping_method": selected_method,
            "selected_shipping_cost": selected_shipping_cost,
            "selected_outbound_days": selected_outbound_days,
            "selected_return_days": selected_return_days,
            "selected_shipping_days": selected_shipping_days,
        }

    #################################################################

    def node_rental_cost(self, receiver_nodes, rental_days):
        return float(receiver_nodes) * float(rental_days) * self.node_logistics.node_rental_per_node_day

    #################################################################

    def price_from_internal_cost(self, internal_project_cost):
        cost = float(internal_project_cost)
        if self.pricing.method == "desired_profit_margin":
            margin = float(self.pricing.desired_profit_margin)
            if margin >= 1.0:
                raise ValueError("desired_profit_margin must be less than 1.0")
            client_price = cost / max(1.0 - margin, 1.0e-9)
        else:
            markup = float(self.pricing.markup_percentage)
            client_price = cost * (1.0 + markup)

        expected_profit = client_price - cost
        profit_margin = 0.0 if client_price == 0.0 else expected_profit / client_price

        return {
            "internal_project_cost": cost,
            "client_price": client_price,
            "expected_profit": expected_profit,
            "profit_margin": profit_margin,
        }

    #################################################################

    def profit_per_day(self, expected_profit, acquisition_days):
        days = float(acquisition_days)
        if days <= 0.0:
            return 0.0
        return float(expected_profit) / days

    #################################################################

    def profit_per_square_mile(self, expected_profit, gis_project):
        area_sq_miles = self._survey_area_square_miles(gis_project)
        if area_sq_miles <= 0.0:
            return 0.0
        return float(expected_profit) / area_sq_miles

    #################################################################

    def business_model_summary(self, gis_project, acquisition_days, receiver_nodes, node_rental_days, internal_cost):
        shipping = self.node_shipping_options(receiver_nodes)
        pricing = self.price_from_internal_cost(internal_cost)
        mobilization_cost = self.mobilization_cost(gis_project)

        return "\n".join([
            "==================================================",
            "BUSINESS MODEL SUMMARY",
            "==================================================",
            "Crew Composition",
            f"Crew Chief Daily Rate         : ${self.crew.crew_chief_daily_rate:.2f}",
            f"Node Team Members             : {self.crew.node_team_members}",
            f"Traffic Control Personnel     : {self.crew.traffic_control_personnel}",
            f"Daily Crew Cost               : ${self.daily_crew_cost():.2f}",
            f"Mobilization Cost             : ${mobilization_cost:.2f}",
            f"Hotel Cost                    : ${self.hotel_cost(acquisition_days):.2f}",
            f"Per Diem Cost                 : ${self.per_diem_cost(acquisition_days):.2f}",
            f"Equipment Cost                : ${self.total_equipment_cost(acquisition_days):.2f}",
            f"Node Rental Cost              : ${self.node_rental_cost(receiver_nodes, node_rental_days):.2f}",
            f"Shipping Cost                 : ${shipping['selected_shipping_cost']:.2f}",
            f"Internal Project Cost         : ${pricing['internal_project_cost']:.2f}",
            f"Client Price                  : ${pricing['client_price']:.2f}",
            f"Expected Profit               : ${pricing['expected_profit']:.2f}",
            f"Profit Margin                 : {pricing['profit_margin'] * 100.0:.2f}%",
            f"Profit Per Day                : ${self.profit_per_day(pricing['expected_profit'], acquisition_days):.2f}",
            f"Profit Per Square Mile        : ${self.profit_per_square_mile(pricing['expected_profit'], gis_project):.2f}",
            "==================================================",
        ])

    #################################################################

    def _survey_centroid_lat_lon(self, gis_project):
        boundary = gis_project.boundary
        if boundary is None:
            raise ValueError("GIS boundary must be loaded before computing centroid")

        centroid_native = boundary.geometry.union_all().centroid
        centroid_geo = gpd.GeoSeries([centroid_native], crs=boundary.crs).to_crs(epsg=4326).iloc[0]
        return float(centroid_geo.y), float(centroid_geo.x)

    #################################################################

    def _survey_area_square_miles(self, gis_project):
        polygon = gis_project.polygon
        if polygon is None:
            return 0.0

        area_sq_ft = float(polygon.area)
        return area_sq_ft / (5280.0 * 5280.0)

    #################################################################

    def _haversine_miles(self, lat1, lon1, lat2, lon2):
        radius_miles = 3958.7613

        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)

        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        a_value = (
            math.sin(dlat / 2.0) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2.0) ** 2
        )
        c_value = 2.0 * math.atan2(math.sqrt(a_value), math.sqrt(1.0 - a_value))

        return radius_miles * c_value
