# Product List Extractor Sequence Diagram

This diagram provides an intuitive overview of how a list of products (like a category page or search results) is processed to extract individual product URLs. It shows how the system falls back to visually scanning the page if clean data isn't provided.

```mermaid
sequenceDiagram
    participant Extractor as List Extractor
    participant Page as Web Page
    participant JS as Browser Engine

    Note over Extractor, Page: Phase 1: Structured Data Check (Optional)
    Extractor->>Page: Check for hidden structured data (JSON-LD)
    Page-->>Extractor: Data Elements
    
    alt Found 'ItemList' or 'Product' Data
        Extractor->>Extractor: Extract URLs directly from data
    else No Structured Data Found
        Note over Extractor, JS: Phase 2: Smart Visual Scanning
        Extractor->>JS: Scan page for "Product Hints"
        Note right of JS: Looks for visible text like "Buy", "Add to cart", prices, or "Out of stock"
        JS->>JS: Ignore elements in menus, headers, or footers
        JS-->>Extractor: Found Product Card hints
        
        Extractor->>JS: Find Product Links near Hints
        Note right of JS: Climbs up the layout from the hint to find the main product link (e.g., clicking the image or title)
        JS->>JS: Try multiple link extraction strategies (e.g., Title links, Image links)
        JS->>JS: Group found links by the strategy used
        
        Note over JS, Extractor: Phase 3: Strategy Selection
        JS->>JS: Pick the strategy that found the MOST unique products
        JS-->>Extractor: Best list of Product URLs
    end
    
    Note over Extractor: Extraction Complete
    Extractor-->>Extractor: Return List of Product URLs
```
