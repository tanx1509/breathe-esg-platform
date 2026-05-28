"""
Reference data models — PlantMaster, UoMSynonymMap, EmissionFactorTable, AirportReferenceTable.

These are lookup tables required before normalization can run. They provide
geographic context, unit conversion rules, emission factors, and airport
coordinates for distance enrichment.
"""
import uuid
from django.db import models


class PlantMaster(models.Model):
    """
    Maps SAP plant codes to geographic reality.

    Required because emission factor selection for Scope 2 electricity depends
    on the power grid of the physical location, and Scope 1 regional fuel
    standards vary by jurisdiction.
    """

    plant_id = models.CharField(max_length=20, primary_key=True)
    tenant = models.ForeignKey(
        "core.Tenant", on_delete=models.CASCADE, related_name="plants"
    )
    plant_name = models.CharField(max_length=255)
    country = models.CharField(
        max_length=3, help_text="ISO 3166-1 alpha-3"
    )
    state_province = models.CharField(max_length=100, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    grid_emission_factor = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="kgCO2e/kWh for Scope 2",
    )
    is_virtual = models.BooleanField(
        default=False,
        help_text="True for placeholder codes like 9999",
    )

    class Meta:
        db_table = "plant_master"

    def __str__(self):
        return f"{self.plant_id} — {self.plant_name} ({'VIRTUAL' if self.is_virtual else self.country})"


class UoMSynonymMap(models.Model):
    """
    Simulates the T006/T006A/T006I chain from SAP.
    Maps localized internal codes to ISO standards.

    This table is why the parser does not hardcode unit mappings.
    "ST" → "EA" because language_key=DE and dimension=count.
    "KL" → "L" because conversion_factor=1000.
    """

    id = models.AutoField(primary_key=True)
    internal_code = models.CharField(max_length=10, help_text='e.g. "ST", "KL", "GAL"')
    language_key = models.CharField(max_length=2, help_text='e.g. "DE", "EN"')
    iso_code = models.CharField(max_length=10, help_text='e.g. "EA", "L", "GLL"')
    dimension = models.CharField(
        max_length=20, help_text='"count", "volume", "mass", "energy"'
    )
    base_unit = models.CharField(
        max_length=10, help_text="SI base unit for this dimension"
    )
    conversion_factor = models.DecimalField(
        max_digits=20,
        decimal_places=10,
        help_text="Multiplier to convert to base unit",
    )

    class Meta:
        db_table = "uom_synonym_map"
        unique_together = ["internal_code", "language_key"]

    def __str__(self):
        return f"{self.internal_code} ({self.language_key}) → {self.iso_code} [{self.dimension}]"


class EmissionFactorTable(models.Model):
    """
    Emission factor lookup table.

    tenant_id=NULL means global factor (e.g., DEFRA).
    Tenant-specific overrides use the tenant's UUID.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "core.Tenant",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="emission_factors",
        help_text="NULL for global factors",
    )
    material_group = models.CharField(
        max_length=50, help_text="SAP MATKL or canonical activity category"
    )
    scope_category = models.CharField(
        max_length=10,
        choices=[
            ("SCOPE_1", "Scope 1"),
            ("SCOPE_2", "Scope 2"),
            ("SCOPE_3", "Scope 3"),
        ],
    )
    activity_type = models.CharField(max_length=100)
    unit = models.CharField(
        max_length=20, help_text='Denominator unit, e.g. "L", "kWh", "km"'
    )
    factor_value = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        help_text="kgCO2e per unit",
    )
    source = models.CharField(
        max_length=255,
        help_text='e.g. "DEFRA 2024", "IEA 2024", "CEA India 2023"',
    )
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "emission_factor_table"

    def __str__(self):
        return f"{self.material_group} | {self.factor_value} kgCO2e/{self.unit} ({self.source})"


class AirportReferenceTable(models.Model):
    """
    Airport coordinates for travel enrichment.

    When a Concur row has origin="DEL" and destination="BOM", the pipeline
    computes great-circle distance from coordinates without calling an
    external API.

    is_city_code=TRUE flags ambiguous codes (NYC, BJS, TYO) that map to
    multiple airports.
    """

    iata_code = models.CharField(max_length=3, primary_key=True)
    airport_name = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=3, help_text="ISO 3166-1 alpha-3")
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    is_city_code = models.BooleanField(
        default=False,
        help_text="True for city codes (NYC, BJS) that map to multiple airports",
    )

    class Meta:
        db_table = "airport_reference_table"

    def __str__(self):
        suffix = " [CITY CODE]" if self.is_city_code else ""
        return f"{self.iata_code} — {self.airport_name}, {self.city}{suffix}"
