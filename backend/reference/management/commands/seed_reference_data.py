"""
Seed reference data — PlantMaster, UoMSynonymMap, EmissionFactorTable, AirportReferenceTable.

Also creates a demo tenant and seed users (admin + analyst).

Usage: python manage.py seed_reference_data
"""
from datetime import date
from django.core.management.base import BaseCommand
from core.models import Tenant, User, UserRole
from reference.models import (
    PlantMaster,
    UoMSynonymMap,
    EmissionFactorTable,
    AirportReferenceTable,
)


class Command(BaseCommand):
    help = "Seed reference data, demo tenant, and seed users"

    def handle(self, *args, **options):
        tenant = self._seed_tenant()
        self._seed_users(tenant)
        self._seed_plants(tenant)
        self._seed_uom()
        self._seed_emission_factors(tenant)
        self._seed_airports()
        self.stdout.write(self.style.SUCCESS("✓ All reference data seeded."))

    def _seed_tenant(self):
        tenant, created = Tenant.objects.get_or_create(
            name="Acme Corp",
            defaults={
                "reporting_currency": "INR",
                "fiscal_year_start": date(2024, 4, 1),
            },
        )
        action = "Created" if created else "Exists"
        self.stdout.write(f"  {action}: Tenant '{tenant.name}'")
        return tenant

    def _seed_users(self, tenant):
        for username, email, role in [
            ("admin", "admin@acmecorp.com", UserRole.ADMIN),
            ("analyst", "analyst@acmecorp.com", UserRole.ANALYST),
            ("viewer", "viewer@acmecorp.com", UserRole.VIEWER),
        ]:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": email,
                    "role": role,
                    "tenant": tenant,
                    "is_staff": role == UserRole.ADMIN,
                },
            )
            if created:
                user.set_password("esg2025")
                user.save()
                self.stdout.write(f"  Created: User '{username}' ({role})")
            else:
                self.stdout.write(f"  Exists: User '{username}'")

    def _seed_plants(self, tenant):
        plants = [
            {
                "plant_id": "1000",
                "tenant": tenant,
                "plant_name": "Mumbai Manufacturing",
                "country": "IND",
                "state_province": "Maharashtra",
                "city": "Mumbai",
                "latitude": 19.076090,
                "longitude": 72.877426,
                "grid_emission_factor": 0.708000,
                "is_virtual": False,
            },
            {
                "plant_id": "2000",
                "tenant": tenant,
                "plant_name": "Delhi Distribution Center",
                "country": "IND",
                "state_province": "Delhi",
                "city": "New Delhi",
                "latitude": 28.613939,
                "longitude": 77.209021,
                "grid_emission_factor": 0.708000,
                "is_virtual": False,
            },
            {
                "plant_id": "3000",
                "tenant": tenant,
                "plant_name": "Bangalore R&D Center",
                "country": "IND",
                "state_province": "Karnataka",
                "city": "Bangalore",
                "latitude": 12.971599,
                "longitude": 77.594566,
                "grid_emission_factor": 0.708000,
                "is_virtual": False,
            },
            {
                "plant_id": "4000",
                "tenant": tenant,
                "plant_name": "Chennai Port Facility",
                "country": "IND",
                "state_province": "Tamil Nadu",
                "city": "Chennai",
                "latitude": 13.082680,
                "longitude": 80.270718,
                "grid_emission_factor": 0.708000,
                "is_virtual": False,
            },
            {
                "plant_id": "9999",
                "tenant": tenant,
                "plant_name": "Virtual / Placeholder Plant",
                "country": "ZZZ",
                "state_province": "",
                "city": "",
                "latitude": None,
                "longitude": None,
                "grid_emission_factor": None,
                "is_virtual": True,
            },
        ]
        for p in plants:
            _, created = PlantMaster.objects.get_or_create(
                plant_id=p["plant_id"], defaults=p
            )
        self.stdout.write(f"  Seeded {len(plants)} plants")

    def _seed_uom(self):
        uoms = [
            # Volume
            {"internal_code": "L", "language_key": "EN", "iso_code": "L", "dimension": "volume", "base_unit": "L", "conversion_factor": 1.0},
            {"internal_code": "KL", "language_key": "EN", "iso_code": "L", "dimension": "volume", "base_unit": "L", "conversion_factor": 1000.0},
            {"internal_code": "GAL", "language_key": "EN", "iso_code": "L", "dimension": "volume", "base_unit": "L", "conversion_factor": 3.78541},
            {"internal_code": "L", "language_key": "DE", "iso_code": "L", "dimension": "volume", "base_unit": "L", "conversion_factor": 1.0},
            {"internal_code": "KL", "language_key": "DE", "iso_code": "L", "dimension": "volume", "base_unit": "L", "conversion_factor": 1000.0},
            # Mass
            {"internal_code": "KG", "language_key": "EN", "iso_code": "KG", "dimension": "mass", "base_unit": "KG", "conversion_factor": 1.0},
            {"internal_code": "KG", "language_key": "DE", "iso_code": "KG", "dimension": "mass", "base_unit": "KG", "conversion_factor": 1.0},
            {"internal_code": "TO", "language_key": "EN", "iso_code": "KG", "dimension": "mass", "base_unit": "KG", "conversion_factor": 1000.0},
            {"internal_code": "TO", "language_key": "DE", "iso_code": "KG", "dimension": "mass", "base_unit": "KG", "conversion_factor": 1000.0},
            # Energy
            {"internal_code": "KWH", "language_key": "EN", "iso_code": "kWh", "dimension": "energy", "base_unit": "kWh", "conversion_factor": 1.0},
            {"internal_code": "MWH", "language_key": "EN", "iso_code": "kWh", "dimension": "energy", "base_unit": "kWh", "conversion_factor": 1000.0},
            {"internal_code": "kWh", "language_key": "EN", "iso_code": "kWh", "dimension": "energy", "base_unit": "kWh", "conversion_factor": 1.0},
            {"internal_code": "MWh", "language_key": "EN", "iso_code": "kWh", "dimension": "energy", "base_unit": "kWh", "conversion_factor": 1000.0},
            {"internal_code": "kVARh", "language_key": "EN", "iso_code": "kVARh", "dimension": "reactive_power", "base_unit": "kVARh", "conversion_factor": 1.0},
            # Count
            {"internal_code": "ST", "language_key": "DE", "iso_code": "EA", "dimension": "count", "base_unit": "EA", "conversion_factor": 1.0},
            {"internal_code": "EA", "language_key": "EN", "iso_code": "EA", "dimension": "count", "base_unit": "EA", "conversion_factor": 1.0},
            # Distance
            {"internal_code": "KM", "language_key": "EN", "iso_code": "km", "dimension": "distance", "base_unit": "km", "conversion_factor": 1.0},
            {"internal_code": "MI", "language_key": "EN", "iso_code": "km", "dimension": "distance", "base_unit": "km", "conversion_factor": 1.60934},
        ]
        for u in uoms:
            UoMSynonymMap.objects.get_or_create(
                internal_code=u["internal_code"],
                language_key=u["language_key"],
                defaults=u,
            )
        self.stdout.write(f"  Seeded {len(uoms)} UoM synonyms")

    def _seed_emission_factors(self, tenant):
        factors = [
            # Scope 1 — fuels
            {"material_group": "DIESEL", "scope_category": "SCOPE_1", "activity_type": "fuel_combustion", "unit": "L", "factor_value": 2.68787, "source": "DEFRA 2024", "valid_from": date(2024, 1, 1)},
            {"material_group": "PETROL", "scope_category": "SCOPE_1", "activity_type": "fuel_combustion", "unit": "L", "factor_value": 2.31485, "source": "DEFRA 2024", "valid_from": date(2024, 1, 1)},
            {"material_group": "LPG", "scope_category": "SCOPE_1", "activity_type": "fuel_combustion", "unit": "L", "factor_value": 1.55537, "source": "DEFRA 2024", "valid_from": date(2024, 1, 1)},
            {"material_group": "FURNACE_OIL", "scope_category": "SCOPE_1", "activity_type": "fuel_combustion", "unit": "L", "factor_value": 3.17500, "source": "DEFRA 2024", "valid_from": date(2024, 1, 1)},
            {"material_group": "NATURAL_GAS", "scope_category": "SCOPE_1", "activity_type": "fuel_combustion", "unit": "KG", "factor_value": 2.02000, "source": "DEFRA 2024", "valid_from": date(2024, 1, 1)},
            # Scope 2 — grid electricity (India)
            {"material_group": "GRID_ELECTRICITY", "scope_category": "SCOPE_2", "activity_type": "grid_electricity", "unit": "kWh", "factor_value": 0.70800, "source": "CEA India 2023", "valid_from": date(2023, 1, 1)},
            # Scope 3 — purchased goods (simplified)
            {"material_group": "CHEMICALS", "scope_category": "SCOPE_3", "activity_type": "upstream_purchased_goods", "unit": "KG", "factor_value": 0.91600, "source": "DEFRA 2024", "valid_from": date(2024, 1, 1)},
            {"material_group": "STEEL", "scope_category": "SCOPE_3", "activity_type": "upstream_purchased_goods", "unit": "KG", "factor_value": 1.46000, "source": "DEFRA 2024", "valid_from": date(2024, 1, 1)},
            {"material_group": "PACKAGING", "scope_category": "SCOPE_3", "activity_type": "upstream_purchased_goods", "unit": "KG", "factor_value": 0.94200, "source": "DEFRA 2024", "valid_from": date(2024, 1, 1)},
            # Scope 3 — waste
            {"material_group": "WASTE_GENERAL", "scope_category": "SCOPE_3", "activity_type": "waste_generation", "unit": "KG", "factor_value": 0.46700, "source": "DEFRA 2024", "valid_from": date(2024, 1, 1)},
            # Scope 3 — business travel (flights)
            {"material_group": "FLIGHT_DOMESTIC", "scope_category": "SCOPE_3", "activity_type": "air_travel", "unit": "km", "factor_value": 0.24587, "source": "DEFRA 2024", "valid_from": date(2024, 1, 1)},
            {"material_group": "FLIGHT_SHORT_HAUL", "scope_category": "SCOPE_3", "activity_type": "air_travel", "unit": "km", "factor_value": 0.15353, "source": "DEFRA 2024", "valid_from": date(2024, 1, 1)},
            {"material_group": "FLIGHT_LONG_HAUL", "scope_category": "SCOPE_3", "activity_type": "air_travel", "unit": "km", "factor_value": 0.19309, "source": "DEFRA 2024", "valid_from": date(2024, 1, 1)},
        ]
        for f in factors:
            EmissionFactorTable.objects.get_or_create(
                material_group=f["material_group"],
                scope_category=f["scope_category"],
                activity_type=f["activity_type"],
                unit=f["unit"],
                defaults={**f, "tenant": None},
            )
        self.stdout.write(f"  Seeded {len(factors)} emission factors")

    def _seed_airports(self):
        airports = [
            # India
            {"iata_code": "DEL", "airport_name": "Indira Gandhi International", "city": "New Delhi", "country": "IND", "latitude": 28.5562, "longitude": 77.1000, "is_city_code": False},
            {"iata_code": "BOM", "airport_name": "Chhatrapati Shivaji Maharaj International", "city": "Mumbai", "country": "IND", "latitude": 19.0896, "longitude": 72.8656, "is_city_code": False},
            {"iata_code": "BLR", "airport_name": "Kempegowda International", "city": "Bangalore", "country": "IND", "latitude": 13.1986, "longitude": 77.7066, "is_city_code": False},
            {"iata_code": "MAA", "airport_name": "Chennai International", "city": "Chennai", "country": "IND", "latitude": 12.9941, "longitude": 80.1709, "is_city_code": False},
            {"iata_code": "CCU", "airport_name": "Netaji Subhas Chandra Bose International", "city": "Kolkata", "country": "IND", "latitude": 22.6547, "longitude": 88.4467, "is_city_code": False},
            {"iata_code": "HYD", "airport_name": "Rajiv Gandhi International", "city": "Hyderabad", "country": "IND", "latitude": 17.2403, "longitude": 78.4294, "is_city_code": False},
            # International
            {"iata_code": "JFK", "airport_name": "John F. Kennedy International", "city": "New York", "country": "USA", "latitude": 40.6413, "longitude": -73.7781, "is_city_code": False},
            {"iata_code": "LHR", "airport_name": "London Heathrow", "city": "London", "country": "GBR", "latitude": 51.4700, "longitude": -0.4543, "is_city_code": False},
            {"iata_code": "SIN", "airport_name": "Singapore Changi", "city": "Singapore", "country": "SGP", "latitude": 1.3644, "longitude": 103.9915, "is_city_code": False},
            {"iata_code": "DXB", "airport_name": "Dubai International", "city": "Dubai", "country": "ARE", "latitude": 25.2532, "longitude": 55.3657, "is_city_code": False},
            {"iata_code": "EWR", "airport_name": "Newark Liberty International", "city": "Newark", "country": "USA", "latitude": 40.6895, "longitude": -74.1745, "is_city_code": False},
            {"iata_code": "LGA", "airport_name": "LaGuardia", "city": "New York", "country": "USA", "latitude": 40.7769, "longitude": -73.8740, "is_city_code": False},
            {"iata_code": "NRT", "airport_name": "Narita International", "city": "Tokyo", "country": "JPN", "latitude": 35.7647, "longitude": 140.3864, "is_city_code": False},
            {"iata_code": "FRA", "airport_name": "Frankfurt am Main", "city": "Frankfurt", "country": "DEU", "latitude": 50.0379, "longitude": 8.5622, "is_city_code": False},
            # City codes (ambiguous)
            {"iata_code": "NYC", "airport_name": "New York City (multi-airport)", "city": "New York", "country": "USA", "latitude": 40.7128, "longitude": -74.0060, "is_city_code": True},
            {"iata_code": "BJS", "airport_name": "Beijing (multi-airport)", "city": "Beijing", "country": "CHN", "latitude": 39.9042, "longitude": 116.4074, "is_city_code": True},
            {"iata_code": "TYO", "airport_name": "Tokyo (multi-airport)", "city": "Tokyo", "country": "JPN", "latitude": 35.6762, "longitude": 139.6503, "is_city_code": True},
        ]
        for a in airports:
            AirportReferenceTable.objects.get_or_create(
                iata_code=a["iata_code"], defaults=a
            )
        self.stdout.write(f"  Seeded {len(airports)} airports")
