# Pagination Engine Sequence Diagram

This diagram provides an intuitive overview of how the Hybrid Pagination Engine navigates through multiple pages of products. It detects the type of pagination automatically and loops until all products are collected.

```mermaid
sequenceDiagram
    participant Worker as Scraper Worker
    participant Paginator as Pagination Engine
    participant Extractor as Product Extractor
    participant Page as Web Page

    Note over Worker, Paginator: Phase 1: Initialization & Detection
    Worker->>Paginator: Start extracting products across pages
    Paginator->>Page: Analyze page structure
    Page-->>Paginator: Detect pagination style (URL, Next Button, Load More, or Scroll)
    
    Paginator->>Extractor: Extract products from the first page
    Extractor-->>Paginator: Initial List of Products
    
    Note over Paginator, Page: Phase 2: The Pagination Loop
    loop Until max pages reached OR no new products found
        
        alt URL Pagination
            Paginator->>Page: Update URL page number & navigate
        else Next Button
            Paginator->>Page: Find and click "Next Page" button
        else Load More Button
            Paginator->>Page: Find and click "Load More" button
        else Infinite Scroll
            Paginator->>Page: Scroll to the bottom of the page
        end
        
        Note right of Page: Wait for new content to load...
        
        Paginator->>Extractor: Extract products from current view
        Extractor-->>Paginator: Additional List of Products
        
        alt Strategy failed (e.g., button broken)
            Note over Paginator: The system is resilient!
            Paginator->>Paginator: Switch to fallback strategy (e.g., try scrolling instead)
        else No new products added
            Paginator->>Paginator: Stop (End of catalog reached)
        end
    end
    
    Note over Worker: Collection Complete
    Paginator-->>Worker: Return all unique products collected
```
