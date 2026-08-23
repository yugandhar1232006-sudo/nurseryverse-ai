"""Seed plant catalog: fruit category + 33 species + 33 plants + inventory.

Revision ID: 0021
Revises: 0020
Create Date: 2026-08-18
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# ---------------------------------------------------------------------------
# Demo nursery & branch (deterministic UUIDs from earlier migrations)
# ---------------------------------------------------------------------------
NURSERY_ID = "0bdea99c-565b-4992-a743-4462079e5a72"
BRANCH_ID = "ed32b449-2b18-470a-a932-a074ca9030a6"
SUPPLIER_ID = "89d108f3-206a-4106-beac-43bb139a98e2"  # Pacific NW Growers Supply

# ---------------------------------------------------------------------------
# Category IDs (from 0002 seed migration)
# ---------------------------------------------------------------------------
CAT_HERB = "ce511a00-4aa1-4369-aa2c-e5293adf9558"
CAT_ANNUAL = "95d77aa8-1941-4b80-97d7-22ef15f0e9f5"
CAT_PERENNIAL = "c7552f8d-01e2-425a-8f9b-dac99c2061ba"
CAT_SHRUB = "f7370c5e-56ca-4c76-90d1-242fff777092"
CAT_TREE = "b90529f5-0449-4627-8968-5711d397f8db"
CAT_FRUIT = "d0336d43-fae3-566d-9f97-5a0d0373e8c9"
CAT_VEGETABLE = "88bb2be3-0434-4a7d-bb3f-d62b04c5f9ac"
CAT_HOUSEPLANT = "06c1e227-6462-449e-b33c-6983e3597989"
CAT_GRASS = "12de2437-b49c-4faa-a405-781155734b18"

# Unit IDs (from 0002 seed migration)
UNIT_EACH = "eec3d4bd-ab0c-4231-a442-0a7ac506c16d"  # "each" — from 0002

# ---------------------------------------------------------------------------
# Lightweight table definitions (no ORM imports — migration stability)
# ---------------------------------------------------------------------------
fruit_categories_table = sa.table(
    "plant_categories",
    sa.column("id", sa.UUID()),
    sa.column("code", sa.String()),
    sa.column("name", sa.String()),
    sa.column("description", sa.String()),
)

species_table = sa.table(
    "species",
    sa.column("id", sa.UUID()),
    sa.column("nursery_id", sa.UUID()),
    sa.column("category_id", sa.UUID()),
    sa.column("common_name", sa.String()),
    sa.column("botanical_name", sa.String()),
    sa.column("light_requirement", sa.String()),
    sa.column("water_baseline_ml_per_week", sa.Integer()),
    sa.column("soil_type", sa.String()),
    sa.column("temperature_min_celsius", sa.Numeric(5, 2)),
    sa.column("temperature_max_celsius", sa.Numeric(5, 2)),
)

plants_table = sa.table(
    "plants",
    sa.column("id", sa.UUID()),
    sa.column("nursery_id", sa.UUID()),
    sa.column("branch_id", sa.UUID()),
    sa.column("species_id", sa.UUID()),
    sa.column("common_label", sa.String()),
    sa.column("status", sa.String()),
    sa.column("qr_code_token", sa.String()),
    sa.column("price", sa.Numeric(10, 2)),
    sa.column("planted_at", sa.DateTime(timezone=True)),
    sa.column("supplier_id", sa.UUID()),
    sa.column("purchase_price", sa.Numeric(10, 2)),
    sa.column("purchase_date", sa.DateTime(timezone=True)),
    sa.column("description", sa.Text()),
)

inventory_table = sa.table(
    "inventory",
    sa.column("id", sa.UUID()),
    sa.column("nursery_id", sa.UUID()),
    sa.column("branch_id", sa.UUID()),
    sa.column("species_id", sa.UUID()),
    sa.column("category_id", sa.UUID()),
    sa.column("unit_id", sa.UUID()),
    sa.column("name", sa.String()),
    sa.column("quantity", sa.Integer()),
    sa.column("unit_cost", sa.Numeric(10, 2)),
    sa.column("unit_price", sa.Numeric(10, 2)),
    sa.column("low_stock_threshold", sa.Integer()),
)

# ---------------------------------------------------------------------------
# New category: Fruit
# ---------------------------------------------------------------------------
FRUIT_CATEGORY = {
    "id": CAT_FRUIT,
    "code": "fruit",
    "name": "Fruit",
    "description": "Fruit trees, berries, and edible fruit plants",
}

# ---------------------------------------------------------------------------
# Species data — 33 species across 9 categories
# ---------------------------------------------------------------------------
SPECIES_DATA = [
    # === Herbs (5) ===
    # Basil (Ocimum basilicum) already exists in this nursery — reuse existing ID
    {
        "id": "d506746e-b26d-4b4a-870d-fdbb9b8d78a1",
        "nursery_id": NURSERY_ID,
        "category_id": CAT_HERB,
        "common_name": "Sweet Basil",
        "botanical_name": "Ocimum basilicum",
        "light_requirement": "Full Sun",
        "water_baseline_ml_per_week": 500,
        "soil_type": "Well-drained, fertile",
        "temperature_min_celsius": 10,
        "temperature_max_celsius": 35,
    },
    {
        "id": "da573a21-477d-51e5-a2d9-3256ffe36f7d",
        "nursery_id": NURSERY_ID,
        "category_id": CAT_HERB,
        "common_name": "Spearmint",
        "botanical_name": "Mentha spicata",
        "light_requirement": "Partial Shade",
        "water_baseline_ml_per_week": 600,
        "soil_type": "Moist, well-drained",
        "temperature_min_celsius": -15,
        "temperature_max_celsius": 30,
    },
    {
        "id": "ecc3984a-905f-5567-ba3d-1613fe82c550",
        "nursery_id": NURSERY_ID,
        "category_id": CAT_HERB,
        "common_name": "Rosemary",
        "botanical_name": "Salvia rosmarinus",
        "light_requirement": "Full Sun",
        "water_baseline_ml_per_week": 300,
        "soil_type": "Sandy, well-drained",
        "temperature_min_celsius": -10,
        "temperature_max_celsius": 35,
    },
    {
        "id": "9a355d14-9ed0-59cb-9717-1c9b58a53ec7",
        "nursery_id": NURSERY_ID,
        "category_id": CAT_HERB,
        "common_name": "English Lavender",
        "botanical_name": "Lavandula angustifolia",
        "light_requirement": "Full Sun",
        "water_baseline_ml_per_week": 250,
        "soil_type": "Sandy, alkaline",
        "temperature_min_celsius": -12,
        "temperature_max_celsius": 35,
    },
    {
        "id": "669c733c-dc0c-5a44-9b34-c2a9b3311cbb",
        "nursery_id": NURSERY_ID,
        "category_id": CAT_HERB,
        "common_name": "Cilantro",
        "botanical_name": "Coriandrum sativum",
        "light_requirement": "Full Sun",
        "water_baseline_ml_per_week": 400,
        "soil_type": "Well-drained, fertile",
        "temperature_min_celsius": 10,
        "temperature_max_celsius": 30,
    },
    # === Annual Flowers (4) ===
    {
        "id": "34df45a1-4ee2-52c9-86d9-ecb11408b03c",
        "nursery_id": NURSERY_ID,
        "category_id": CAT_ANNUAL,
        "common_name": "French Marigold",
        "botanical_name": "Tagetes patula",
        "light_requirement": "Full Sun",
        "water_baseline_ml_per_week": 350,
        "soil_type": "Well-drained, moderate fertility",
        "temperature_min_celsius": 12,
        "temperature_max_celsius": 35,
    },
    {
        "id": "26e5d6c0-6667-5469-aebe-6687fe62c22f",
        "nursery_id": NURSERY_ID,
        "category_id": CAT_ANNUAL,
        "common_name": "Grandiflora Petunia",
        "botanical_name": "Petunia x hybrida",
        "light_requirement": "Full Sun",
        "water_baseline_ml_per_week": 500,
        "soil_type": "Well-drained, fertile",
        "temperature_min_celsius": 12,
        "temperature_max_celsius": 32,
    },
    {
        "id": "ead6a03b-d344-5854-bd79-32908e1d0a6a",
        "nursery_id": NURSERY_ID,
        "category_id": CAT_ANNUAL,
        "common_name": "State Fair Zinnia",
        "botanical_name": "Zinnia elegans",
        "light_requirement": "Full Sun",
        "water_baseline_ml_per_week": 400,
        "soil_type": "Well-drained, moderate fertility",
        "temperature_min_celsius": 10,
        "temperature_max_celsius": 35,
    },
    {
        "id": "7bae5bbd-dbf4-52fe-bbf3-d5b95d748fe3",
        "nursery_id": NURSERY_ID,
        "category_id": CAT_ANNUAL,
        "common_name": "Rocket Mix Snapdragon",
        "botanical_name": "Antirrhinum majus",
        "light_requirement": "Full Sun",
        "water_baseline_ml_per_week": 400,
        "soil_type": "Well-drained, fertile",
        "temperature_min_celsius": 7,
        "temperature_max_celsius": 30,
    },
    # === Perennial Flowers (4) ===
    {
        "id": "97aba8e0-9556-5a34-9dc5-0254144d0fb7",
        "nursery_id": NURSERY_ID,
        "category_id": CAT_PERENNIAL,
        "common_name": "Dinner Plate Dahlia",
        "botanical_name": "Dahlia pinnata",
        "light_requirement": "Full Sun",
        "water_baseline_ml_per_week": 600,
        "soil_type": "Rich, well-drained",
        "temperature_min_celsius": -5,
        "temperature_max_celsius": 32,
    },
    {
        "id": "36bfa415-ada8-580c-b519-8fb377382786",
        "nursery_id": NURSERY_ID,
        "category_id": CAT_PERENNIAL,
        "common_name": "Purple Coneflower",
        "botanical_name": "Echinacea purpurea",
        "light_requirement": "Full Sun",
        "water_baseline_ml_per_week": 350,
        "soil_type": "Well-drained, average",
        "temperature_min_celsius": -25,
        "temperature_max_celsius": 35,
    },
    {
        "id": "7960496a-c791-5211-a242-34e77bdb0bd1",
        "nursery_id": NURSERY_ID,
        "category_id": CAT_PERENNIAL,
        "common_name": "Goldsturm Black-Eyed Susan",
        "botanical_name": "Rudbeckia hirta",
        "light_requirement": "Full Sun",
        "water_baseline_ml_per_week": 350,
        "soil_type": "Well-drained, average",
        "temperature_min_celsius": -25,
        "temperature_max_celsius": 35,
    },
    {
        "id": "4f27d698-0618-5a77-93c2-ee4219d25d07",
        "nursery_id": NURSERY_ID,
        "category_id": CAT_PERENNIAL,
        "common_name": "Plantain Hosta",
        "botanical_name": "Hosta plantaginea",
        "light_requirement": "Full Shade",
        "water_baseline_ml_per_week": 500,
        "soil_type": "Rich, moist, well-drained",
        "temperature_min_celsius": -25,
        "temperature_max_celsius": 30,
    },
    # === Shrubs (3) ===
    {
        "id": "ba3e07e4-d8c8-5726-9b2d-86b36b0247ac",
        "nursery_id": NURSERY_ID,
        "category_id": CAT_SHRUB,
        "common_name": "Nikko Blue Hydrangea",
        "botanical_name": "Hydrangea macrophylla",
        "light_requirement": "Partial Shade",
        "water_baseline_ml_per_week": 800,
        "soil_type": "Rich, moist, well-drained",
        "temperature_min_celsius": -12,
        "temperature_max_celsius": 32,
    },
    {
        "id": "070bc0ce-dd51-5cc9-be3b-6d86112b58ec",
        "nursery_id": NURSERY_ID,
        "category_id": CAT_SHRUB,
        "common_name": "Common Lilac",
        "botanical_name": "Syringa vulgaris",
        "light_requirement": "Full Sun",
        "water_baseline_ml_per_week": 500,
        "soil_type": "Well-drained, neutral to alkaline",
        "temperature_min_celsius": -30,
        "temperature_max_celsius": 32,
    },
    {
        "id": "4e74ac15-fc83-5ddc-84c6-c9a39bd77176",
        "nursery_id": NURSERY_ID,
        "category_id": CAT_SHRUB,
        "common_name": "Hino Crimson Azalea",
        "botanical_name": "Rhododendron spp.",
        "light_requirement": "Partial Shade",
        "water_baseline_ml_per_week": 600,
        "soil_type": "Acidic, well-drained",
        "temperature_min_celsius": -15,
        "temperature_max_celsius": 30,
    },
    # === Trees (3) ===
    {
        "id": "51738488-9196-5438-bdc7-3dfc39d6cd5d",
        "nursery_id": NURSERY_ID,
        "category_id": CAT_TREE,
        "common_name": "Bloodgood Japanese Maple",
        "botanical_name": "Acer palmatum",
        "light_requirement": "Partial Shade",
        "water_baseline_ml_per_week": 700,
        "soil_type": "Acidic, well-drained",
        "temperature_min_celsius": -18,
        "temperature_max_celsius": 32,
    },
    {
        "id": "2057a471-becd-56d6-9c48-e089ee0c5c05",
        "nursery_id": NURSERY_ID,
        "category_id": CAT_TREE,
        "common_name": "Florida Dogwood",
        "botanical_name": "Cornus florida",
        "light_requirement": "Partial Shade",
        "water_baseline_ml_per_week": 600,
        "soil_type": "Acidic, moist, well-drained",
        "temperature_min_celsius": -18,
        "temperature_max_celsius": 32,
    },
    {
        "id": "0aa0d1f3-0082-5a0e-a1dc-e5519305baff",
        "nursery_id": NURSERY_ID,
        "category_id": CAT_TREE,
        "common_name": "Dynamite Crepe Myrtle",
        "botanical_name": "Lagerstroemia indica",
        "light_requirement": "Full Sun",
        "water_baseline_ml_per_week": 500,
        "soil_type": "Well-drained, average",
        "temperature_min_celsius": -12,
        "temperature_max_celsius": 38,
    },
    # === Fruit (4) ===
    {
        "id": "c955ceee-82a6-5931-a048-cea99937c92f",
        "nursery_id": NURSERY_ID,
        "category_id": CAT_FRUIT,
        "common_name": "Seascape Strawberry",
        "botanical_name": "Fragaria x ananassa",
        "light_requirement": "Full Sun",
        "water_baseline_ml_per_week": 500,
        "soil_type": "Rich, well-drained",
        "temperature_min_celsius": -10,
        "temperature_max_celsius": 32,
    },
    {
        "id": "c5d37d16-e7d1-5415-aa5c-5994dbd5ae24",
        "nursery_id": NURSERY_ID,
        "category_id": CAT_FRUIT,
        "common_name": "Bluecrop Blueberry",
        "botanical_name": "Vaccinium corymbosum",
        "light_requirement": "Full Sun",
        "water_baseline_ml_per_week": 500,
        "soil_type": "Acidic, well-drained",
        "temperature_min_celsius": -25,
        "temperature_max_celsius": 32,
    },
    {
        "id": "66870540-7e2d-561c-b92f-19ec465d9d71",
        "nursery_id": NURSERY_ID,
        "category_id": CAT_FRUIT,
        "common_name": "Heritage Raspberry",
        "botanical_name": "Rubus idaeus",
        "light_requirement": "Full Sun",
        "water_baseline_ml_per_week": 500,
        "soil_type": "Rich, well-drained",
        "temperature_min_celsius": -25,
        "temperature_max_celsius": 32,
    },
    {
        "id": "c592e36a-4c23-5754-bbf6-5be8f001c5fa",
        "nursery_id": NURSERY_ID,
        "category_id": CAT_FRUIT,
        "common_name": "Honeycrisp Apple",
        "botanical_name": "Malus domestica",
        "light_requirement": "Full Sun",
        "water_baseline_ml_per_week": 700,
        "soil_type": "Well-drained, moderate fertility",
        "temperature_min_celsius": -25,
        "temperature_max_celsius": 35,
    },
    # === Vegetable Starts (4) ===
    # Tomato (Solanum lycopersicum) already exists in this nursery — reuse existing ID
    {
        "id": "496ad0dc-ccf3-4fc9-ba57-15c7b3c71972",
        "nursery_id": NURSERY_ID,
        "category_id": CAT_VEGETABLE,
        "common_name": "Early Girl Tomato",
        "botanical_name": "Solanum lycopersicum",
        "light_requirement": "Full Sun",
        "water_baseline_ml_per_week": 800,
        "soil_type": "Rich, well-drained",
        "temperature_min_celsius": 12,
        "temperature_max_celsius": 35,
    },
    {
        "id": "2ebcbe0f-0d15-536e-a29f-f4f988a69150",
        "nursery_id": NURSERY_ID,
        "category_id": CAT_VEGETABLE,
        "common_name": "California Wonder Pepper",
        "botanical_name": "Capsicum annuum",
        "light_requirement": "Full Sun",
        "water_baseline_ml_per_week": 600,
        "soil_type": "Rich, well-drained",
        "temperature_min_celsius": 15,
        "temperature_max_celsius": 35,
    },
    {
        "id": "c6159a3a-37ab-51fc-8754-34f38b5ebb6e",
        "nursery_id": NURSERY_ID,
        "category_id": CAT_VEGETABLE,
        "common_name": "Marketmore Cucumber",
        "botanical_name": "Cucumis sativus",
        "light_requirement": "Full Sun",
        "water_baseline_ml_per_week": 800,
        "soil_type": "Rich, well-drained",
        "temperature_min_celsius": 15,
        "temperature_max_celsius": 35,
    },
    {
        "id": "4163be20-e92d-59a0-abab-7404523fd7aa",
        "nursery_id": NURSERY_ID,
        "category_id": CAT_VEGETABLE,
        "common_name": "Buttercrunch Lettuce",
        "botanical_name": "Lactuca sativa",
        "light_requirement": "Partial Shade",
        "water_baseline_ml_per_week": 400,
        "soil_type": "Rich, moist, well-drained",
        "temperature_min_celsius": 4,
        "temperature_max_celsius": 25,
    },
    # === Houseplants (4) ===
    {
        "id": "011a2535-db19-53a1-85fc-aa4d5aa548d7",
        "nursery_id": NURSERY_ID,
        "category_id": CAT_HOUSEPLANT,
        "common_name": "Snake Plant",
        "botanical_name": "Dracaena trifasciata",
        "light_requirement": "Low Light",
        "water_baseline_ml_per_week": 200,
        "soil_type": "Sandy, well-drained",
        "temperature_min_celsius": 10,
        "temperature_max_celsius": 30,
    },
    {
        "id": "fa318b35-8a31-5ea4-8376-6479d487d642",
        "nursery_id": NURSERY_ID,
        "category_id": CAT_HOUSEPLANT,
        "common_name": "Golden Pothos",
        "botanical_name": "Epipremnum aureum",
        "light_requirement": "Low Light",
        "water_baseline_ml_per_week": 300,
        "soil_type": "Well-drained, peat-based",
        "temperature_min_celsius": 12,
        "temperature_max_celsius": 30,
    },
    {
        "id": "029a0163-eabe-5a5a-aef8-872e07d0fcc4",
        "nursery_id": NURSERY_ID,
        "category_id": CAT_HOUSEPLANT,
        "common_name": "ZZ Plant",
        "botanical_name": "Zamioculcas zamiifolia",
        "light_requirement": "Low Light",
        "water_baseline_ml_per_week": 150,
        "soil_type": "Well-drained, sandy",
        "temperature_min_celsius": 12,
        "temperature_max_celsius": 30,
    },
    {
        "id": "01aace4b-bc8e-5429-abdb-c5f3948daa14",
        "nursery_id": NURSERY_ID,
        "category_id": CAT_HOUSEPLANT,
        "common_name": "Peace Lily",
        "botanical_name": "Spathiphyllum wallisii",
        "light_requirement": "Low Light",
        "water_baseline_ml_per_week": 400,
        "soil_type": "Rich, well-drained",
        "temperature_min_celsius": 15,
        "temperature_max_celsius": 30,
    },
    # === Ornamental Grasses (2) ===
    {
        "id": "b9eefeba-ecb9-57db-84f5-d14ffde5ef01",
        "nursery_id": NURSERY_ID,
        "category_id": CAT_GRASS,
        "common_name": "Morning Light Maiden Grass",
        "botanical_name": "Miscanthus sinensis",
        "light_requirement": "Full Sun",
        "water_baseline_ml_per_week": 400,
        "soil_type": "Well-drained, average",
        "temperature_min_celsius": -20,
        "temperature_max_celsius": 35,
    },
    {
        "id": "780a87b1-bd25-518b-a3c8-1d00f2c538bb",
        "nursery_id": NURSERY_ID,
        "category_id": CAT_GRASS,
        "common_name": "Hameln Fountain Grass",
        "botanical_name": "Pennisetum alopecuroides",
        "light_requirement": "Full Sun",
        "water_baseline_ml_per_week": 350,
        "soil_type": "Well-drained, average",
        "temperature_min_celsius": -20,
        "temperature_max_celsius": 35,
    },
]

# ---------------------------------------------------------------------------
# Plant instances — one per species, in the demo nursery / Main Greenhouse
# ---------------------------------------------------------------------------
PLANTS_DATA = [
    # Herbs
    {
        "id": "35ebdf3e-7b08-5b44-91cd-a2c025f1cf7f",
        "nursery_id": NURSERY_ID,
        "branch_id": BRANCH_ID,
        "species_id": "d506746e-b26d-4b4a-870d-fdbb9b8d78a1",
        "common_label": "Sweet Basil — Display",
        "status": "IN_PRODUCTION",
        "qr_code_token": "NV-BASIL-001",
        "price": 5.99,
        "planted_at": "2025-04-15T08:00:00Z",
        "supplier_id": SUPPLIER_ID,
        "purchase_price": 2.50,
        "purchase_date": "2025-03-20T08:00:00Z",
        "description": "Fragrant culinary basil, perfect for pesto and caprese salads.",
    },
    {
        "id": "4dd3ff5e-cc40-57ae-ad29-3395dded6603",
        "nursery_id": NURSERY_ID,
        "branch_id": BRANCH_ID,
        "species_id": "da573a21-477d-51e5-a2d9-3256ffe36f7d",
        "common_label": "Spearmint — Display",
        "status": "IN_PRODUCTION",
        "qr_code_token": "NV-MINT-001",
        "price": 5.49,
        "planted_at": "2025-04-10T08:00:00Z",
        "supplier_id": SUPPLIER_ID,
        "purchase_price": 2.25,
        "purchase_date": "2025-03-20T08:00:00Z",
        "description": "Cool, refreshing mint ideal for teas, cocktails, and garnishes.",
    },
    {
        "id": "80f0a3ff-9582-5393-b578-a5a16f93924c",
        "nursery_id": NURSERY_ID,
        "branch_id": BRANCH_ID,
        "species_id": "ecc3984a-905f-5567-ba3d-1613fe82c550",
        "common_label": "Rosemary — Display",
        "status": "IN_PRODUCTION",
        "qr_code_token": "NV-ROSEMARY-001",
        "price": 6.99,
        "planted_at": "2025-03-15T08:00:00Z",
        "supplier_id": SUPPLIER_ID,
        "purchase_price": 3.00,
        "purchase_date": "2025-02-28T08:00:00Z",
        "description": "Hardy, aromatic rosemary with needle-like leaves for roasts and breads.",
    },
    {
        "id": "04edebc1-10ce-5dab-b042-572a2eec7cf9",
        "nursery_id": NURSERY_ID,
        "branch_id": BRANCH_ID,
        "species_id": "9a355d14-9ed0-59cb-9717-1c9b58a53ec7",
        "common_label": "English Lavender — Display",
        "status": "READY_FOR_SALE",
        "qr_code_token": "NV-LAVENDER-001",
        "price": 8.99,
        "planted_at": "2025-02-20T08:00:00Z",
        "supplier_id": SUPPLIER_ID,
        "purchase_price": 3.50,
        "purchase_date": "2025-02-10T08:00:00Z",
        "description": "Classic English lavender with silvery foliage and purple flower spikes.",
    },
    {
        "id": "0612cf69-a5fe-54e1-85cb-c279c2771ed5",
        "nursery_id": NURSERY_ID,
        "branch_id": BRANCH_ID,
        "species_id": "669c733c-dc0c-5a44-9b34-c2a9b3311cbb",
        "common_label": "Cilantro — Display",
        "status": "IN_PRODUCTION",
        "qr_code_token": "NV-CILANTRO-001",
        "price": 4.99,
        "planted_at": "2025-05-01T08:00:00Z",
        "supplier_id": SUPPLIER_ID,
        "purchase_price": 2.00,
        "purchase_date": "2025-04-20T08:00:00Z",
        "description": "Fresh cilantro for salsas, curries, and Mexican cuisine.",
    },
    # Annual Flowers
    {
        "id": "6eec96b6-5590-5897-8223-9815d09a1015",
        "nursery_id": NURSERY_ID,
        "branch_id": BRANCH_ID,
        "species_id": "34df45a1-4ee2-52c9-86d9-ecb11408b03c",
        "common_label": "French Marigold — Display",
        "status": "READY_FOR_SALE",
        "qr_code_token": "NV-MARIGOLD-001",
        "price": 3.99,
        "planted_at": "2025-04-20T08:00:00Z",
        "supplier_id": SUPPLIER_ID,
        "purchase_price": 1.50,
        "purchase_date": "2025-04-10T08:00:00Z",
        "description": "Vibrant orange and gold marigolds, excellent for borders and pest deterrence.",
    },
    {
        "id": "15d5c284-c8b8-5d9f-9215-1a2a0c6615b3",
        "nursery_id": NURSERY_ID,
        "branch_id": BRANCH_ID,
        "species_id": "26e5d6c0-6667-5469-aebe-6687fe62c22f",
        "common_label": "Grandiflora Petunia — Display",
        "status": "READY_FOR_SALE",
        "qr_code_token": "NV-PETUNIA-001",
        "price": 4.49,
        "planted_at": "2025-04-18T08:00:00Z",
        "supplier_id": SUPPLIER_ID,
        "purchase_price": 1.75,
        "purchase_date": "2025-04-08T08:00:00Z",
        "description": "Large, showy petunia blooms in pink, purple, and white for containers and beds.",
    },
    {
        "id": "2419a181-367c-551b-b7d6-b8cb25c58ea0",
        "nursery_id": NURSERY_ID,
        "branch_id": BRANCH_ID,
        "species_id": "ead6a03b-d344-5854-bd79-32908e1d0a6a",
        "common_label": "State Fair Zinnia — Display",
        "status": "READY_FOR_SALE",
        "qr_code_token": "NV-ZINNIA-001",
        "price": 3.49,
        "planted_at": "2025-04-22T08:00:00Z",
        "supplier_id": SUPPLIER_ID,
        "purchase_price": 1.25,
        "purchase_date": "2025-04-12T08:00:00Z",
        "description": "Bold, colorful zinnias that attract butterflies and make great cut flowers.",
    },
    {
        "id": "3eb69c56-ecd8-54f0-b41b-40df4a4fc640",
        "nursery_id": NURSERY_ID,
        "branch_id": BRANCH_ID,
        "species_id": "7bae5bbd-dbf4-52fe-bbf3-d5b95d748fe3",
        "common_label": "Rocket Mix Snapdragon — Display",
        "status": "IN_PRODUCTION",
        "qr_code_token": "NV-SNAPDRAGON-001",
        "price": 4.99,
        "planted_at": "2025-04-25T08:00:00Z",
        "supplier_id": SUPPLIER_ID,
        "purchase_price": 1.80,
        "purchase_date": "2025-04-15T08:00:00Z",
        "description": "Tall, spiky snapdragons in mixed colors for vertical garden interest.",
    },
    # Perennial Flowers
    {
        "id": "25967bf6-9d50-5f60-a0f2-cffeb9dc3e61",
        "nursery_id": NURSERY_ID,
        "branch_id": BRANCH_ID,
        "species_id": "97aba8e0-9556-5a34-9dc5-0254144d0fb7",
        "common_label": "Dinner Plate Dahlia — Display",
        "status": "IN_PRODUCTION",
        "qr_code_token": "NV-DAHLIA-001",
        "price": 12.99,
        "planted_at": "2025-04-01T08:00:00Z",
        "supplier_id": SUPPLIER_ID,
        "purchase_price": 5.00,
        "purchase_date": "2025-03-15T08:00:00Z",
        "description": "Showstopping dinner-plate dahlias with enormous blooms up to 10 inches across.",
    },
    {
        "id": "bb1a28b2-aa6c-5204-a631-2aba00a7f62b",
        "nursery_id": NURSERY_ID,
        "branch_id": BRANCH_ID,
        "species_id": "36bfa415-ada8-580c-b519-8fb377382786",
        "common_label": "Purple Coneflower — Display",
        "status": "READY_FOR_SALE",
        "qr_code_token": "NV-ECHINACEA-001",
        "price": 9.99,
        "planted_at": "2025-03-20T08:00:00Z",
        "supplier_id": SUPPLIER_ID,
        "purchase_price": 4.00,
        "purchase_date": "2025-03-10T08:00:00Z",
        "description": "Native prairie coneflower that attracts pollinators and tolerates drought.",
    },
    {
        "id": "dfb9a235-1081-5e4e-88ac-6b18a5db6d18",
        "nursery_id": NURSERY_ID,
        "branch_id": BRANCH_ID,
        "species_id": "7960496a-c791-5211-a242-34e77bdb0bd1",
        "common_label": "Goldsturm Black-Eyed Susan — Display",
        "status": "READY_FOR_SALE",
        "qr_code_token": "NV-BLACK-EYED-SUSAN-001",
        "price": 8.49,
        "planted_at": "2025-03-25T08:00:00Z",
        "supplier_id": SUPPLIER_ID,
        "purchase_price": 3.50,
        "purchase_date": "2025-03-15T08:00:00Z",
        "description": "Cheerful golden-yellow daisies with dark centers, blooming late summer.",
    },
    {
        "id": "38c21b9e-0f44-5fae-9b2e-61da9a573189",
        "nursery_id": NURSERY_ID,
        "branch_id": BRANCH_ID,
        "species_id": "4f27d698-0618-5a77-93c2-ee4219d25d07",
        "common_label": "Plantain Hosta — Display",
        "status": "READY_FOR_SALE",
        "qr_code_token": "NV-HOSTA-001",
        "price": 11.99,
        "planted_at": "2025-03-10T08:00:00Z",
        "supplier_id": SUPPLIER_ID,
        "purchase_price": 4.50,
        "purchase_date": "2025-03-01T08:00:00Z",
        "description": "Bold, glossy hosta with large heart-shaped leaves for shady gardens.",
    },
    # Shrubs
    {
        "id": "8ae5451d-898f-5f8e-8265-2dac9c172afd",
        "nursery_id": NURSERY_ID,
        "branch_id": BRANCH_ID,
        "species_id": "ba3e07e4-d8c8-5726-9b2d-86b36b0247ac",
        "common_label": "Nikko Blue Hydrangea — Display",
        "status": "READY_FOR_SALE",
        "qr_code_token": "NV-HYDRANGEA-001",
        "price": 24.99,
        "planted_at": "2025-02-15T08:00:00Z",
        "supplier_id": SUPPLIER_ID,
        "purchase_price": 10.00,
        "purchase_date": "2025-02-05T08:00:00Z",
        "description": "Classic mophead hydrangea with large blue flower clusters in acidic soil.",
    },
    {
        "id": "87ab98eb-51b4-5511-b340-e2ccc84ee3fc",
        "nursery_id": NURSERY_ID,
        "branch_id": BRANCH_ID,
        "species_id": "070bc0ce-dd51-5cc9-be3b-6d86112b58ec",
        "common_label": "Common Lilac — Display",
        "status": "READY_FOR_SALE",
        "qr_code_token": "NV-LILAC-001",
        "price": 19.99,
        "planted_at": "2025-02-10T08:00:00Z",
        "supplier_id": SUPPLIER_ID,
        "purchase_price": 8.00,
        "purchase_date": "2025-02-01T08:00:00Z",
        "description": "Fragrant spring-blooming lilac with dense purple flower panicles.",
    },
    {
        "id": "1151645b-fe53-5062-81e7-6a5860af7cfd",
        "nursery_id": NURSERY_ID,
        "branch_id": BRANCH_ID,
        "species_id": "4e74ac15-fc83-5ddc-84c6-c9a39bd77176",
        "common_label": "Hino Crimson Azalea — Display",
        "status": "READY_FOR_SALE",
        "qr_code_token": "NV-AZALEA-001",
        "price": 18.99,
        "planted_at": "2025-01-20T08:00:00Z",
        "supplier_id": SUPPLIER_ID,
        "purchase_price": 7.50,
        "purchase_date": "2025-01-10T08:00:00Z",
        "description": "Brilliant red early-season azalea, compact and showy.",
    },
    # Trees
    {
        "id": "f68fcaf6-4ecd-58df-b1f3-4c2b6c29e526",
        "nursery_id": NURSERY_ID,
        "branch_id": BRANCH_ID,
        "species_id": "51738488-9196-5438-bdc7-3dfc39d6cd5d",
        "common_label": "Bloodgood Japanese Maple — Display",
        "status": "READY_FOR_SALE",
        "qr_code_token": "NV-JAPANESE-MAPLE-001",
        "price": 89.99,
        "planted_at": "2024-11-15T08:00:00Z",
        "supplier_id": SUPPLIER_ID,
        "purchase_price": 40.00,
        "purchase_date": "2024-11-05T08:00:00Z",
        "description": "Deep burgundy foliage Japanese maple, a specimen tree for any landscape.",
    },
    {
        "id": "24543dd7-7d0e-5a84-a30c-c56901ffbb80",
        "nursery_id": NURSERY_ID,
        "branch_id": BRANCH_ID,
        "species_id": "2057a471-becd-56d6-9c48-e089ee0c5c05",
        "common_label": "Florida Dogwood — Display",
        "status": "READY_FOR_SALE",
        "qr_code_token": "NV-DOGWOOD-001",
        "price": 74.99,
        "planted_at": "2024-11-20T08:00:00Z",
        "supplier_id": SUPPLIER_ID,
        "purchase_price": 35.00,
        "purchase_date": "2024-11-10T08:00:00Z",
        "description": "Native flowering dogwood with white bracts and brilliant fall color.",
    },
    {
        "id": "61779b8a-6b99-5e6e-8138-3ca2caae5a7f",
        "nursery_id": NURSERY_ID,
        "branch_id": BRANCH_ID,
        "species_id": "0aa0d1f3-0082-5a0e-a1dc-e5519305baff",
        "common_label": "Dynamite Crepe Myrtle — Display",
        "status": "READY_FOR_SALE",
        "qr_code_token": "NV-CREPE-MYRTLE-001",
        "price": 59.99,
        "planted_at": "2024-12-01T08:00:00Z",
        "supplier_id": SUPPLIER_ID,
        "purchase_price": 28.00,
        "purchase_date": "2024-11-20T08:00:00Z",
        "description": "Vibrant red crepe myrtle with summer-long blooms and exfoliating bark.",
    },
    # Fruit
    {
        "id": "5eb5ae0d-8258-51a0-b90d-63cc0ebf19a1",
        "nursery_id": NURSERY_ID,
        "branch_id": BRANCH_ID,
        "species_id": "c955ceee-82a6-5931-a048-cea99937c92f",
        "common_label": "Seascape Strawberry — Display",
        "status": "IN_PRODUCTION",
        "qr_code_token": "NV-STRAWBERRY-001",
        "price": 6.99,
        "planted_at": "2025-04-01T08:00:00Z",
        "supplier_id": SUPPLIER_ID,
        "purchase_price": 3.00,
        "purchase_date": "2025-03-25T08:00:00Z",
        "description": "Day-neutral strawberry producing large, sweet fruit all season long.",
    },
    {
        "id": "4459b261-0d3c-562f-a9b8-e92e7523257e",
        "nursery_id": NURSERY_ID,
        "branch_id": BRANCH_ID,
        "species_id": "c5d37d16-e7d1-5415-aa5c-5994dbd5ae24",
        "common_label": "Bluecrop Blueberry — Display",
        "status": "READY_FOR_SALE",
        "qr_code_token": "NV-BLUEBERRY-001",
        "price": 14.99,
        "planted_at": "2025-02-10T08:00:00Z",
        "supplier_id": SUPPLIER_ID,
        "purchase_price": 6.00,
        "purchase_date": "2025-02-01T08:00:00Z",
        "description": "High-yield northern highbush blueberry with sweet, large berries.",
    },
    {
        "id": "914c8f92-23f5-5e06-873d-12243b43ebd5",
        "nursery_id": NURSERY_ID,
        "branch_id": BRANCH_ID,
        "species_id": "66870540-7e2d-561c-b92f-19ec465d9d71",
        "common_label": "Heritage Raspberry — Display",
        "status": "IN_PRODUCTION",
        "qr_code_token": "NV-RASPBERRY-001",
        "price": 9.99,
        "planted_at": "2025-03-15T08:00:00Z",
        "supplier_id": SUPPLIER_ID,
        "purchase_price": 4.00,
        "purchase_date": "2025-03-05T08:00:00Z",
        "description": "Everbearing raspberry producing fruit in summer and again in fall.",
    },
    {
        "id": "0e35c3c1-1604-5006-9d39-42ad2adedeae",
        "nursery_id": NURSERY_ID,
        "branch_id": BRANCH_ID,
        "species_id": "c592e36a-4c23-5754-bbf6-5be8f001c5fa",
        "common_label": "Honeycrisp Apple — Display",
        "status": "READY_FOR_SALE",
        "qr_code_token": "NV-APPLE-001",
        "price": 64.99,
        "planted_at": "2024-11-01T08:00:00Z",
        "supplier_id": SUPPLIER_ID,
        "purchase_price": 30.00,
        "purchase_date": "2024-10-20T08:00:00Z",
        "description": "Beloved Honeycrisp apple tree, known for its explosive crunch and balanced sweetness.",
    },
    # Vegetable Starts
    {
        "id": "2a750ca6-2213-5d6b-84f1-1718073db389",
        "nursery_id": NURSERY_ID,
        "branch_id": BRANCH_ID,
        "species_id": "496ad0dc-ccf3-4fc9-ba57-15c7b3c71972",
        "common_label": "Early Girl Tomato — Display",
        "status": "IN_PRODUCTION",
        "qr_code_token": "NV-TOMATO-001",
        "price": 4.49,
        "planted_at": "2025-04-20T08:00:00Z",
        "supplier_id": SUPPLIER_ID,
        "purchase_price": 1.50,
        "purchase_date": "2025-04-10T08:00:00Z",
        "description": "Fast-maturing indeterminate tomato, perfect for short-season gardens.",
    },
    {
        "id": "9f6e07b7-cce6-5491-b1de-10c6e513e33d",
        "nursery_id": NURSERY_ID,
        "branch_id": BRANCH_ID,
        "species_id": "2ebcbe0f-0d15-536e-a29f-f4f988a69150",
        "common_label": "California Wonder Pepper — Display",
        "status": "IN_PRODUCTION",
        "qr_code_token": "NV-PEPPER-001",
        "price": 4.99,
        "planted_at": "2025-04-22T08:00:00Z",
        "supplier_id": SUPPLIER_ID,
        "purchase_price": 1.75,
        "purchase_date": "2025-04-12T08:00:00Z",
        "description": "Thick-walled sweet bell pepper, great for stuffing and fresh eating.",
    },
    {
        "id": "cace9a8a-3d00-5f4c-b0a4-dd6ca9787af8",
        "nursery_id": NURSERY_ID,
        "branch_id": BRANCH_ID,
        "species_id": "c6159a3a-37ab-51fc-8754-34f38b5ebb6e",
        "common_label": "Marketmore Cucumber — Display",
        "status": "IN_PRODUCTION",
        "qr_code_token": "NV-CUCUMBER-001",
        "price": 3.99,
        "planted_at": "2025-05-01T08:00:00Z",
        "supplier_id": SUPPLIER_ID,
        "purchase_price": 1.25,
        "purchase_date": "2025-04-25T08:00:00Z",
        "description": "Reliable slicing cucumber with dark green, uniform fruits.",
    },
    {
        "id": "7fca63ef-6474-54e7-83d3-d11c5c46c6a4",
        "nursery_id": NURSERY_ID,
        "branch_id": BRANCH_ID,
        "species_id": "4163be20-e92d-59a0-abab-7404523fd7aa",
        "common_label": "Buttercrunch Lettuce — Display",
        "status": "IN_PRODUCTION",
        "qr_code_token": "NV-LETTUCE-001",
        "price": 3.49,
        "planted_at": "2025-05-05T08:00:00Z",
        "supplier_id": SUPPLIER_ID,
        "purchase_price": 1.00,
        "purchase_date": "2025-04-28T08:00:00Z",
        "description": "Buttery, heat-tolerant bibb lettuce with soft, flavorful leaves.",
    },
    # Houseplants
    {
        "id": "c83a14fb-7de1-5599-90df-de6fec537301",
        "nursery_id": NURSERY_ID,
        "branch_id": BRANCH_ID,
        "species_id": "011a2535-db19-53a1-85fc-aa4d5aa548d7",
        "common_label": "Snake Plant — Display",
        "status": "READY_FOR_SALE",
        "qr_code_token": "NV-SNAKE-PLANT-001",
        "price": 14.99,
        "planted_at": "2025-01-10T08:00:00Z",
        "supplier_id": SUPPLIER_ID,
        "purchase_price": 5.00,
        "purchase_date": "2025-01-01T08:00:00Z",
        "description": "Indestructible snake plant that purifies air and thrives on neglect.",
    },
    {
        "id": "4a44f3ad-6341-5903-b460-f032096640e5",
        "nursery_id": NURSERY_ID,
        "branch_id": BRANCH_ID,
        "species_id": "fa318b35-8a31-5ea4-8376-6479d487d642",
        "common_label": "Golden Pothos — Display",
        "status": "READY_FOR_SALE",
        "qr_code_token": "NV-POTHOS-001",
        "price": 9.99,
        "planted_at": "2025-01-15T08:00:00Z",
        "supplier_id": SUPPLIER_ID,
        "purchase_price": 3.50,
        "purchase_date": "2025-01-05T08:00:00Z",
        "description": "Fast-growing trailing pothos with golden-variegated heart-shaped leaves.",
    },
    {
        "id": "7915affc-669f-5001-bc1a-1a7557d8182c",
        "nursery_id": NURSERY_ID,
        "branch_id": BRANCH_ID,
        "species_id": "029a0163-eabe-5a5a-aef8-872e07d0fcc4",
        "common_label": "ZZ Plant — Display",
        "status": "READY_FOR_SALE",
        "qr_code_token": "NV-ZZ-PLANT-001",
        "price": 16.99,
        "planted_at": "2025-01-05T08:00:00Z",
        "supplier_id": SUPPLIER_ID,
        "purchase_price": 6.00,
        "purchase_date": "2024-12-28T08:00:00Z",
        "description": "Glossy, upright ZZ plant that tolerates deep shade and drought.",
    },
    {
        "id": "7fc1f19c-18bd-5c6e-9fb8-61d9527dadd9",
        "nursery_id": NURSERY_ID,
        "branch_id": BRANCH_ID,
        "species_id": "01aace4b-bc8e-5429-abdb-c5f3948daa14",
        "common_label": "Peace Lily — Display",
        "status": "READY_FOR_SALE",
        "qr_code_token": "NV-PEACE-LILY-001",
        "price": 12.99,
        "planted_at": "2025-01-20T08:00:00Z",
        "supplier_id": SUPPLIER_ID,
        "purchase_price": 4.50,
        "purchase_date": "2025-01-10T08:00:00Z",
        "description": "Elegant peace lily with white spathes, blooms reliably in low light.",
    },
    # Ornamental Grasses
    {
        "id": "82094c0d-7d37-5190-9674-0c5ce543a28b",
        "nursery_id": NURSERY_ID,
        "branch_id": BRANCH_ID,
        "species_id": "b9eefeba-ecb9-57db-84f5-d14ffde5ef01",
        "common_label": "Morning Light Maiden Grass — Display",
        "status": "READY_FOR_SALE",
        "qr_code_token": "NV-MAIDEN-GRASS-001",
        "price": 18.99,
        "planted_at": "2025-02-20T08:00:00Z",
        "supplier_id": SUPPLIER_ID,
        "purchase_price": 7.00,
        "purchase_date": "2025-02-10T08:00:00Z",
        "description": "Graceful, fine-textured maiden grass with silver-variegated foliage.",
    },
    {
        "id": "7acb0a8f-fae7-5d67-9d51-37e50f583064",
        "nursery_id": NURSERY_ID,
        "branch_id": BRANCH_ID,
        "species_id": "780a87b1-bd25-518b-a3c8-1d00f2c538bb",
        "common_label": "Hameln Fountain Grass — Display",
        "status": "READY_FOR_SALE",
        "qr_code_token": "NV-FOUNTAIN-GRASS-001",
        "price": 15.99,
        "planted_at": "2025-02-25T08:00:00Z",
        "supplier_id": SUPPLIER_ID,
        "purchase_price": 6.00,
        "purchase_date": "2025-02-15T08:00:00Z",
        "description": "Compact fountain grass with fluffy, buff-colored plumes in late summer.",
    },
]

# ---------------------------------------------------------------------------
# Inventory — stock records for each species at the Main Greenhouse
# ---------------------------------------------------------------------------
INVENTORY_IDS = [
    "b5cee5de-c79a-5a94-90ca-4cbfad17bcc2",  # basil
    "c2e9f456-42ed-5eac-8a0f-e81ad21a525b",  # mint
    "f39b5418-f4bc-562c-86b0-27be4fb590d5",  # rosemary
    "4ffd9ed9-3f6b-553b-8d38-3ef0afe2f233",  # lavender
    "bd137f15-dd67-5a52-8a1d-474f75dbf549",  # cilantro
    "861cea65-e5c2-5e5b-b75f-f099cf4d6cd3",  # marigold
    "47ed5fe6-8cb1-5937-9643-01b4b802a63c",  # petunia
    "9c207b9d-13ef-5e2f-b4f8-3648267e1d12",  # zinnia
    "94507d97-3fe0-5fb6-87ff-9267acb7867f",  # snapdragon
    "c0bdce5e-7371-5b75-829b-ae4fa6ea5ac3",  # dahlia
    "56052d32-2ea3-535e-9763-5cbfe52c78c4",  # echinacea
    "82528d67-92d3-5b61-ab9f-2777187df352",  # black_eyed_susan
    "99aae40d-b2cd-5880-90ca-d27a6aec7289",  # hosta
    "561ba106-f409-5c76-bf42-b843e76e7cbf",  # hydrangea
    "65a21862-9a5c-5b54-ade3-4ff603abf4de",  # lilac
    "918a11f4-9f13-5501-a922-4c42ca210ff3",  # azalea
    "d7e0fd0c-848c-5c13-add1-298325876515",  # japanese_maple
    "61b19fe8-6ad4-5a83-b9d6-711648f52f31",  # dogwood
    "cc7e5be2-2d94-5df9-a4d0-c21edee08cc9",  # crepe_myrtle
    "87ec9335-5a89-5305-b0ca-b61694f2a40b",  # strawberry
    "d460f589-f271-5dbb-a6c6-02966273c5f5",  # blueberry
    "872966ff-3d2c-5226-b5aa-9448fa96eff7",  # raspberry
    "1c04666f-d5d9-5541-a4d9-2403d5403fce",  # apple
    "64a2d7a8-b820-5827-a28e-84fd741c97c8",  # tomato
    "fb4f1739-48a2-5e28-bf36-fe5363d0bdec",  # pepper
    "27c55a46-6d35-551b-b863-ed3b369a89b5",  # cucumber
    "a7e96828-02e5-595b-94fc-a913e3d00815",  # lettuce
    "50133f46-e353-5af8-8b70-502e5f0c1e84",  # snake_plant
    "c6fa1949-e211-5c21-9495-56e3d3d3c604",  # pothos
    "51f14c55-0d88-5fa4-ae72-e65c4a334981",  # zz_plant
    "1623d7e5-01c5-52ad-b869-2b32c0173533",  # peace_lily
    "d60bfee8-e59f-5629-990c-cfa2b6cf534e",  # maiden_grass
    "043d2fae-169f-5461-894e-60bbf5831cba",  # fountain_grass
]

INVENTORY_DATA = [
    {
        "id": inv_id,
        "nursery_id": NURSERY_ID,
        "branch_id": BRANCH_ID,
        "species_id": s["id"],
        "category_id": s["category_id"],
        "unit_id": UNIT_EACH,
        "name": s["common_name"],
        "quantity": 12,
        "unit_cost": float(p["purchase_price"]),
        "unit_price": float(p["price"]),
        "low_stock_threshold": 5,
    }
    for inv_id, s, p in zip(INVENTORY_IDS, SPECIES_DATA, PLANTS_DATA)
]


def _s(v: str) -> str:
    """Escape single quotes for safe SQL literal embedding."""
    return str(v).replace("'", "''")


def upgrade() -> None:
    # 1. Add "fruit" plant category (idempotent)
    c = FRUIT_CATEGORY
    op.execute(sa.text(
        f"INSERT INTO plant_categories (id, code, name, description) "
        f"VALUES ('{_s(c['id'])}'::uuid, '{_s(c['code'])}', '{_s(c['name'])}', '{_s(c['description'])}') "
        f"ON CONFLICT (code) DO NOTHING"
    ))

    # 2. Seed species (idempotent)
    for s in SPECIES_DATA:
        op.execute(sa.text(
            f"INSERT INTO species (id, nursery_id, category_id, common_name, botanical_name, "
            f"light_requirement, water_baseline_ml_per_week, soil_type, "
            f"temperature_min_celsius, temperature_max_celsius) "
            f"VALUES ('{_s(s['id'])}'::uuid, '{_s(s['nursery_id'])}'::uuid, "
            f"'{_s(s['category_id'])}'::uuid, '{_s(s['common_name'])}', "
            f"'{_s(s['botanical_name'])}', '{_s(s['light_requirement'])}', "
            f"{int(s['water_baseline_ml_per_week'])}, '{_s(s['soil_type'])}', "
            f"{float(s['temperature_min_celsius'])}, {float(s['temperature_max_celsius'])}) "
            f"ON CONFLICT (nursery_id, botanical_name) DO NOTHING"
        ))

    # 3. Seed plant instances (idempotent)
    for p in PLANTS_DATA:
        op.execute(sa.text(
            f"INSERT INTO plants (id, nursery_id, branch_id, species_id, common_label, "
            f"status, qr_code_token, price, planted_at, "
            f"supplier_id, purchase_price, purchase_date, description) "
            f"VALUES ('{_s(p['id'])}'::uuid, '{_s(p['nursery_id'])}'::uuid, "
            f"'{_s(p['branch_id'])}'::uuid, '{_s(p['species_id'])}'::uuid, "
            f"'{_s(p['common_label'])}', '{_s(p['status'])}'::plant_status, "
            f"'{_s(p['qr_code_token'])}', {float(p['price'])}::numeric, "
            f"'{_s(p['planted_at'])}'::timestamptz, "
            f"'{_s(p['supplier_id'])}'::uuid, {float(p['purchase_price'])}::numeric, "
            f"'{_s(p['purchase_date'])}'::timestamptz, '{_s(p['description'])}') "
            f"ON CONFLICT (qr_code_token) DO NOTHING"
        ))

    # 4. Seed inventory records (idempotent)
    for inv in INVENTORY_DATA:
        op.execute(sa.text(
            f"INSERT INTO inventory (id, nursery_id, branch_id, species_id, category_id, "
            f"unit_id, name, quantity, unit_cost, unit_price, "
            f"low_stock_threshold, reserved_quantity, damaged_quantity, "
            f"disposed_quantity, version) "
            f"VALUES ('{_s(inv['id'])}'::uuid, '{_s(inv['nursery_id'])}'::uuid, "
            f"'{_s(inv['branch_id'])}'::uuid, '{_s(inv['species_id'])}'::uuid, "
            f"'{_s(inv['category_id'])}'::uuid, '{_s(inv['unit_id'])}'::uuid, "
            f"'{_s(inv['name'])}', {int(inv['quantity'])}, "
            f"{float(inv['unit_cost'])}::numeric, {float(inv['unit_price'])}::numeric, "
            f"{int(inv['low_stock_threshold'])}, 0, 0, 0, 1) "
            f"ON CONFLICT (branch_id, name) DO NOTHING"
        ))


def downgrade() -> None:
    nid = _s(NURSERY_ID)
    op.execute(sa.text(f"DELETE FROM inventory WHERE nursery_id = '{nid}'::uuid"))
    op.execute(sa.text(f"DELETE FROM plants WHERE nursery_id = '{nid}'::uuid"))
    op.execute(sa.text(f"DELETE FROM species WHERE nursery_id = '{nid}'::uuid"))
    op.execute(sa.text("DELETE FROM plant_categories WHERE code = 'fruit'"))
