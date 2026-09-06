import json
import sys
from pathlib import Path

from models.company_data import CompanyData
from craft.parsers.company_page_parser import CraftParser

crawler_root = Path(__file__).resolve().parents[1]
common_root = crawler_root.parent / "company-common"
sys.path.insert(0, str(crawler_root))
sys.path.insert(0, str(common_root))


# Example usage
craft_parser = CraftParser()

data_dir = Path("/mnt/storage/My Programming project/company-data/company-crawler")

with open(data_dir / "craft_data.json", "r") as f:
    sample_data = f.read()

company_data = craft_parser.parse(sample_data)

with open(data_dir / "parsed_craft_data.json", "w") as f:
    if isinstance(company_data, CompanyData):
        json.dump(company_data.model_dump(mode="json"), f, indent=2)
    else:
        json.dump(company_data, f, indent=2)
