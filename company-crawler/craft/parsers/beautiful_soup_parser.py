from base.parser import Parser
from models.company_data import CompanyData, CompanyStatus
import json


class CraftParser(Parser):
    def parse(self, data: str) -> CompanyData:
        # Implement the parsing logic for Craft data here
        # For example, you can use BeautifulSoup or regex to extract information
        # from the HTML or JSON data provided by Craft.
        # Return a CompanyData object containing the parsed company data.
        json_data = json.loads(data)
        print(json_data)
        return json_data  #! TESTING


if __name__ == "__main__":
    # Example usage
    craft_parser = CraftParser()
    sample_data = "<html>Sample Craft data</html>"  # Replace with actual Craft data
    company_data = craft_parser.parse(sample_data)
