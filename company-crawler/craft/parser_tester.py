import sys
from pathlib import Path

from models.company_data import CompanyData

crawler_root = Path(__file__).resolve().parents[1]
common_root = crawler_root.parent / "company-common"
sys.path.insert(0, str(crawler_root))
sys.path.insert(0, str(common_root))
from craft.parsers.company_page_parser import CraftParser
import json

# Example usage
craft_parser = CraftParser()
sample_data = "<html>Sample Craft data</html>"  # Replace with actual Craft data
with open(
    "/mnt/storage/My Programming project/company-data/company-crawler/craft_data.json",
    "r",
) as f:
    sample_data = f.read()
company_data = craft_parser.parse(sample_data)
with open(
    "/mnt/storage/My Programming project/company-data/company-crawler/parsed_craft_data.json",
    "w",
) as f:
    if type(company_data) == CompanyData:
        json.dump(company_data.model_dump(mode="json"), f, indent=2)
    else:
        json.dump(company_data, f, indent=2)
