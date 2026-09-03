# Company Crawler

A comprehensive, extensible library for searching and scraping company data from multiple sources. Built with a modular architecture that makes it easy to add new data sources.

## Features

- 🔍 **Multi-Source Support**: Search and scrape from multiple company data sources (Craft.co and more)
- 🎯 **Flexible Search**: Find companies by name or stock ticker
- 📄 **Page Scraping**: Extract structured data from company pages
- 📊 **Multiple Export Formats**: Export data to CSV, JSON, and Parquet
- 🔌 **Extensible Architecture**: Add new data sources without modifying core code
- ⛓️ **Failover Chains**: Automatic fallback between HTTP and Selenium-based scrapers
- 💾 **Pluggable Storage**: Persist scraped data to MongoDB or PostgreSQL

## Installation

### Requirements
- Python 3.8+
- See `requirements.txt` for dependencies

### Setup

```bash
# Clone or navigate to the project
cd company-crawler

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install .
```

## Quick Start

### Using the Generic API (Recommended for multi-source)

```python
from company_crawler import get_search_service, get_scraping_service
from interfaces.iconfig import IQuery, ICrawlerConfig

# Create services
search_service = get_search_service("craft")
scraping_service = get_scraping_service("craft")

# Search for a company
results = search_service.search_company(
    IQuery(company_name="Amazon")
)

# Scrape a company page
company_data = scraping_service.scrape_company_page(
    "https://craft.co/amazon",
    ICrawlerConfig()
)
```

### Using the Craft-Specific API

```python
from craft import create_search_service, create_scraping_service
from interfaces.iconfig import IQuery, ICrawlerConfig

# Create Craft services
search_service = create_search_service()
scraping_service = create_scraping_service()

# Search companies
results = search_service.search_company(
    IQuery(company_name="Amazon")
)

# Scrape company pages
data = scraping_service.scrape_company_page(
    "https://craft.co/amazon",
    ICrawlerConfig()
)
```

### Direct Service Access

```python
from company_crawler import CraftCompanySearchingService, CraftCompanyPageScrapingService
from craft.parsers.company_page_parser import CraftParser

# Instantiate services directly
search_service = CraftCompanySearchingService()
scraping_service = CraftCompanyPageScrapingService(
    url_scraper=None,  # Uses default chain
    page_parser=CraftParser()
)
```

## Architecture

### Multi-Source Design

The library is built around a **service registry** that maps data sources to their corresponding search and scraping services.

```
company_crawler/
├── Generic API (get_search_service, get_scraping_service)
│   └── Service Registry (AVAILABLE_SOURCES)
│       └── Craft Source
│           ├── CraftCompanySearchingService
│           └── CraftCompanyPageScrapingService
└── craft/
    ├── Source-Specific API
    ├── Orchestrators
    ├── Crawlers
    ├── Parsers
    └── Searchers
```

### How Services Work

#### Search Service
- Searches for companies by name or stock ticker
- Returns a list of search results
- Supports multiple fallback crawlers (HTTP → Selenium)

#### Scraping Service
- Fetches company pages via URL
- Parses structured data from HTML
- Handles errors gracefully with logging

### Adding New Data Sources

To add a new data source (e.g., LinkedIn):

1. **Create a new module** (e.g., `linkedin/`)
2. **Implement orchestrators** for search and scraping
3. **Register in root `__init__.py`**:

```python
AVAILABLE_SOURCES = {
    "craft": {...},
    "linkedin": {
        "search_service": LinkedInCompanySearchingService,
        "scraping_service": LinkedInCompanyPageScrapingService,
    }
}
```

4. **Use it**:

```python
service = get_search_service("linkedin")
```

## API Reference

### Root-Level API

#### `get_search_service(source="craft", **kwargs)`

Create a search service for the specified data source.

**Parameters:**
- `source` (str): Data source name. Default: `"craft"`
- `**kwargs`: Additional arguments passed to the service constructor

**Returns:** Search service instance

**Raises:** `ValueError` if source is not available

**Example:**
```python
from company_crawler import get_search_service
service = get_search_service("craft")
```

#### `get_scraping_service(source="craft", **kwargs)`

Create a scraping service for the specified data source.

**Parameters:**
- `source` (str): Data source name. Default: `"craft"`
- `**kwargs`: Additional arguments passed to the service constructor

**Returns:** Scraping service instance

**Raises:** `ValueError` if source is not available

**Example:**
```python
from company_crawler import get_scraping_service
service = get_scraping_service("craft")
```

#### `get_storage(driver="mongodb", config=None, **config_kwargs)`

Create a storage backend for persisting scraped company data.

**Parameters:**
- `driver` (str): Backend name - `"mongodb"` or `"postgresql"` (case-insensitive). Default: `"mongodb"`
- `config` (IDatabaseConfig, optional): Pre-built database config. When omitted, one is created from the keyword arguments
- `**config_kwargs`: Forwarded to `IDatabaseConfig` (e.g. `name`, `host`, `port`, `user`, `password`, plus driver-specific extra options)

**Returns:** A `DataStorage` instance (`MongoDBStorage` or `PostgreSQLStorage`). The connection is not opened yet - call `.connect()` before `.store_data(...)`

**Raises:** `ValueError` if driver is not available

**Example:**
```python
from company_crawler import get_storage
storage = get_storage("mongodb", name="companies")
storage.connect()
```

### Craft-Specific API

#### `create_search_service(searcher=None)`

Create a Craft search service with optional custom searcher.

**Parameters:**
- `searcher` (CompanySearcher, optional): Custom searcher implementation

**Returns:** `CraftCompanySearchingService` instance

#### `create_scraping_service(url_scraper=None, page_parser=None)`

Create a Craft scraping service with optional custom components.

**Parameters:**
- `url_scraper` (UrlScraper, optional): Custom URL scraper (default: chain of HTTP + Selenium)
- `page_parser` (Parser, optional): Custom page parser (default: `CraftParser`)

**Returns:** `CraftCompanyPageScrapingService` instance

### Search Service

#### `search_company(query, config=None)`

Search for companies.

**Parameters:**
- `query` (IQuery): Query object with `company_name` and/or `stock_ticket`
- `config` (ICrawlerConfig, optional): Crawler configuration

**Returns:** List of search results

**Example:**
```python
from interfaces.iconfig import IQuery

results = service.search_company(
    IQuery(company_name="Amazon")
)
```

### Scraping Service

#### `scrape_company_page(url, config=None)`

Scrape and parse a company page.

**Parameters:**
- `url` (str): Company page URL
- `config` (ICrawlerConfig, optional): Crawler configuration

**Returns:** Parsed page data

**Example:**
```python
from interfaces.iconfig import ICrawlerConfig

data = service.scrape_company_page(
    "https://craft.co/amazon",
    ICrawlerConfig()
)
```

## Project Structure

```
company-crawler/
├── base/                      # Base classes and interfaces
│   ├── scraper.py             # UrlScraper base class
│   ├── parser.py              # Parser base class
│   ├── searcher.py            # CompanySearcher base class
│   └── ...
├── craft/                     # Craft.co implementation
│   ├── scraping_orchestrator.py
│   ├── search_orchestrator.py
│   ├── crawlers/              # HTTP and Selenium crawlers
│   ├── parsers/               # BeautifulSoup parser
│   ├── searchers/             # Company search implementation
│   ├── services/              # Data exporters (CSV, JSON, Parquet)
│   └── utils/                 # Scraping utilities
├── interfaces/                # Config and response interfaces
│   ├── iconfig.py
│   └── search_response.py
├── tests/                     # Unit tests
├── logger.py                  # Logging configuration
├── requirements.txt
└── __init__.py               # Root API
```

## Data Export

The library supports exporting data in multiple formats:

- **CSV** via `craft.services.csv_exporter.CSVExporter`
- **JSON** via `craft.services.json_exporter.JSONExporter`
- **Parquet** via `craft.services.parquet_exporter.ParquetExporter`

```python
from craft.services.json_exporter import JSONExporter

exporter = JSONExporter()
exporter.export(data, "output.json")
```

## Data Storage

Scraped `CompanyData` can be persisted to MongoDB or PostgreSQL. Both backends
implement the same `DataStorage` interface (`connect()` / `store_data()`), so
switching is a one-line change.

### Using the factory (recommended)

```python
from company_crawler import get_storage

# MongoDB: upserts one document per company domain
mongo_storage = get_storage("mongodb", name="companies")

# PostgreSQL: upserts one JSONB row per company domain
postgres_storage = get_storage("postgresql", name="companies")

storage = mongo_storage  # or postgres_storage
storage.connect()
storage.store_data(company_data)
```

Connection settings are forwarded to `IDatabaseConfig` (`DB_*` environment
variables work too):

```python
storage = get_storage(
    "postgresql",
    name="companies",
    host="db.internal",
    port=5432,
    user="crawler",
    password="secret",
    table="companies",  # extra option: custom table name (PostgreSQL)
)
```

> **MongoDB `authSource`:** pymongo authenticates against the database named
> in the connection (here `companies`). Users created by the official Docker
> image (`MONGO_INITDB_ROOT_USERNAME`) live in the `admin` database, so
> authenticate against it explicitly:
>
> ```python
> storage = get_storage("mongodb", name="companies", authSource="admin")
> ```

### Direct class access

```python
from company_crawler import MongoDBStorage, PostgreSQLStorage, IDatabaseConfig

config = IDatabaseConfig(driver="mongodb", name="companies")
storage = MongoDBStorage(config)
storage.connect()
```

## Configuration

### ICrawlerConfig

Control scraper behavior:

```python
from interfaces.iconfig import ICrawlerConfig

config = ICrawlerConfig()
# Customize as needed (see interfaces/iconfig.py)
```

### IQuery

Define search queries:

```python
from interfaces.iconfig import IQuery

# Search by company name
query = IQuery(company_name="Amazon")

# Search by stock ticker
query = IQuery(stock_ticket="AMZN")

# Search by both (results from both)
query = IQuery(company_name="Amazon", stock_ticket="AMZN")
```

## Testing

Run tests:

```bash
# Run all tests
python -m unittest discover tests -v

# Run specific test
python -m unittest tests.craft_searcher_test -v
```

## Logging

The library uses Python's logging module. Configure logging:

```python
import logging
from logger import get_logger

logger = get_logger("my_app")
logger.info("Starting company search...")
```

## Available Data Sources

### Craft (craft.co)
- ✅ Company search by name and stock ticker
- ✅ Company page scraping
- ✅ Dual-mode crawlers (HTTP with Selenium fallback)
- ✅ BeautifulSoup HTML parsing


## Error Handling

The library includes comprehensive error handling:

```python
from company_crawler import get_search_service

try:
    service = get_search_service("craft")
    results = service.search_company(query)
except ValueError as e:
    print(f"Invalid source: {e}")
except Exception as e:
    print(f"Scraping error: {e}")
```

## Contributing

To add a new data source:

1. Create a new module in `company-crawler/`
2. Implement search and scraping orchestrators
3. Register in the root `__init__.py`
4. Add tests in the `tests/` directory
5. Update this README

## Requirements

See `requirements.txt` for a complete list of dependencies.


## Support

For issues or questions, please refer to the documentation or submit an issue.
