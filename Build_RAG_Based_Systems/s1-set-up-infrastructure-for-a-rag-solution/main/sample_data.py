from langchain_core.documents import Document

# LangChain Documents to seed the vectorstore with initial data 
SAMPLE_DOCUMENTS = [
    Document(
        page_content=(
            "The 2024 EcoSport Hybrid model features a 2.5L hybrid powertrain delivering 191 horsepower, "
            "advanced driver-assistance systems including adaptive cruise control and lane-keeping assist, "
            "and a 12.3-inch infotainment display with wireless Apple CarPlay and Android Auto. "
            "Available in three trim levels: Base ($28,500), Premium ($32,000), and Luxury ($36,500). "
            "Current inventory shows 15 units available across dealerships, with delivery within 2-3 weeks. "
            "Key features include panoramic sunroof, premium leather seats, and 360-degree camera system."
        ),
        metadata={
            "document": "Vehicle Catalog",
            "category": "Models & Features",
            "model": "EcoSport Hybrid 2024",
            "section": "Product Specifications",
            "page": 1,
            "id": "doc_vehicle_001"
        }
    ),
    Document(
        page_content=(
            "Pricing and availability for the 2024 EcoSport Hybrid: Base trim starts at $28,500 MSRP with "
            "financing options available at 2.9% APR for qualified buyers. Premium trim priced at $32,000 "
            "includes additional safety features and premium audio system. Luxury trim at $36,500 features "
            "all premium options including heated and ventilated seats. Current inventory status: 8 Base models, "
            "5 Premium models, and 2 Luxury models available. Special promotions: $2,000 cashback on Base trim, "
            "free extended warranty on Premium and Luxury trims. Delivery timeline: 2-3 weeks for in-stock models, "
            "4-6 weeks for custom orders."
        ),
        metadata={
            "document": "Pricing Guide",
            "category": "Pricing & Availability",
            "model": "EcoSport Hybrid 2024",
            "section": "Sales Information",
            "page": 1,
            "id": "doc_pricing_001"
        }
    )
]

# Plain text sentences for basic embedding and similarity search tests
# Contains automotive-related content covering engine, sensor, brake, transmission, calibration
SAMPLE_SENTENCES = [
    "The engine management system uses advanced sensor data to optimize fuel injection timing for maximum efficiency.",
    "Brake-by-wire technology replaces traditional hydraulic systems with electronic actuators for precise stopping control.",
    "The automatic transmission uses adaptive calibration algorithms to learn driver preferences and road conditions.",
    "Wheel speed sensors provide real-time data to the ABS and traction control modules for safe vehicle dynamics.",
    "Engine torque output is continuously monitored and adjusted based on throttle position and load sensor readings.",
]