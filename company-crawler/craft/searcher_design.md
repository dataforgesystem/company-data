```mermaid
classDiagram
    direction TB

    class CompanySearcher {
        <<abstract>>
        -searcher: CompanyNameScraper
        +__init__(searcher: CompanyNameScraper)
        +search_by_name(name: str, config: ICrawlerConfig): List~ISearchResponse~
        +search_by_symbol(symbol: str, config: ICrawlerConfig): List~ISearchResponse~
    }

    class CompanySearchByName {
        -search_response_parser: SearchResponseParser
        +__init__(searcher: CompanyNameScraper, parser: SearchResponseParser)
        +search_by_name(name: str, config: ICrawlerConfig): List~ISearchResponse~
        +search_by_symbol(symbol: str, config: ICrawlerConfig): List~ISearchResponse~
    }

    class CompanyNameScraper {
        <<abstract>>
        +scrape(query: str, config: ICrawlerConfig)
    }

    class CompanySearchCrawler {
        +build_proxies(proxy: str)
        +scrape(query: str, config: ICrawlerConfig): str
    }

    class SearchResponseParser {
        <<abstract>>
        +parse(data: Dict): List~ISearchResponse~
    }

    class CraftSearchParser {
        +parse(data: str): List~ISearchResponse~
    }

    class CraftCompanySearchingService {
        -searcher: CompanySearcher
        +__init__(searcher: CompanySearcher)
        +search_company(query: IQuery, config: ICrawlerConfig): List~ISearchResponse~
    }

    class IQuery {
        +company_name: str
        +stock_ticket: str
    }

    class ICrawlerConfig {
        +proxy: str
    }

    class ISearchResponse {
        +company_name: str
        +source_url: HttpUrl
        +logo_url: Optional~str~
        +slug: str
    }

    CompanySearcher <|-- CompanySearchByName
    CompanyNameScraper <|-- CompanySearchCrawler
    SearchResponseParser <|-- CraftSearchParser

    CompanySearcher o--> CompanyNameScraper : delegates scraping to
    CompanySearchByName o--> SearchResponseParser : parses raw response
    CraftCompanySearchingService o--> CompanySearcher : delegates searching to

    CompanySearcher --> ICrawlerConfig
    CompanyNameScraper --> ICrawlerConfig
    SearchResponseParser --> ISearchResponse
    CraftCompanySearchingService --> IQuery
    CraftCompanySearchingService --> ISearchResponse
```

<br>
<hr>

```mermaid
sequenceDiagram
    participant Client
    participant Service as CraftCompanySearchingService
    participant Searcher as CompanySearchByName
    participant Crawler as CompanySearchCrawler
    participant Parser as CraftSearchParser
    participant External as External Search API

    Client->>Service: search_company(query, config)

    alt query.company_name exists
        Service->>Searcher: search_by_name(company_name, config)
        Searcher->>Crawler: scrape(company_name, config)
        Crawler->>Crawler: prepare headers, payload, URL
        Crawler->>External: POST search request
        External-->>Crawler: raw JSON response text
        Crawler-->>Searcher: raw response text
        Searcher->>Parser: parse(raw response text)
        Parser-->>Searcher: List[ISearchResponse]
        Searcher-->>Service: parsed search responses
    end

    alt query.stock_ticket exists
        Service->>Searcher: search_by_symbol(stock_ticket, config)
        Searcher-->>Service: NotImplementedError
    end

    Service-->>Client: combined results
```

**Dependency injection setup**

```mermaid
flowchart LR
    Crawler["CompanySearchCrawler"]
    Parser["CraftSearchParser"]
    Searcher["CompanySearchByName"]
    Service["CraftCompanySearchingService"]

    Crawler -->|"injected into constructor"| Searcher
    Parser -->|"injected into constructor"| Searcher
    Searcher -->|"injected into constructor"| Service

    Service -->|"search_company()"| Searcher
    Searcher -->|"scrape()"| Crawler
    Searcher -->|"parse()"| Parser
```

**Runtime responsibility summary**

```mermaid
flowchart LR
    Query["IQuery"] --> Service["CraftCompanySearchingService"]
    Service --> Searcher["CompanySearchByName"]
    Searcher --> Crawler["CompanySearchCrawler"]
    Crawler --> Raw["Raw JSON text"]
    Raw --> Parser["CraftSearchParser"]
    Parser --> Responses["List[ISearchResponse]"]
    Responses --> Service
```

`CompanySearchCrawler` fetches data, `CraftSearchParser` transforms the raw JSON into `ISearchResponse` objects, and `CraftCompanySearchingService` returns the parsed responses. `CompanySearchByName` must receive both the crawler and parser so `self.search_response_parser` is initialized before `search_by_name()` is called.