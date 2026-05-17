# Product Detail Extractor Sequence Diagram

This diagram provides an intuitive, high-level overview of how product details are extracted from a web page, starting with structured data and falling back to deep page interaction.

```mermaid
sequenceDiagram
    participant Extractor as Product Extractor
    participant Parser as Data Parser
    participant Page as Web Page

    Note over Extractor, Parser: Phase 1: Basic Data Extraction
    Extractor->>Parser: Extract Basic Info (Title, Brand, Images)
    Parser-->>Extractor: Check Structured Data (JSON-LD)
    alt Missing Info
        Parser-->>Extractor: Fallback to Meta Tags & Headers
    end
    
    Extractor->>Parser: Extract Pricing & Availability
    Parser-->>Extractor: Check Structured Data & Meta Tags

    Note over Extractor, Page: Phase 2: Page Interaction & Deep Extraction
    Extractor->>Page: Locate Main Product Area
    Page-->>Extractor: Product Area Identified
    
    Extractor->>Page: Search for Description/Specs Tabs
    Note right of Page: Looks for keywords like "details", "specs"
    Page-->>Extractor: List of Interactive Tabs/Buttons
    
    loop For each identified tab
        Extractor->>Page: Click Tab (to reveal hidden text)
        Extractor->>Page: Locate Tab Content
        Page-->>Extractor: HTML Content
        Extractor->>Extractor: Convert Content to Markdown
    end
    
    Note over Extractor, Page: Phase 3: Fallbacks for Missing Critical Data
    alt Price is still missing
        Extractor->>Page: Read raw text from product area
        Page-->>Extractor: Raw Text
        Extractor->>Extractor: Extract Price using Smart Patterns
    end
    
    alt Availability is still missing
        Extractor->>Page: Search for Stock Status
        Note right of Page: Looks for "in stock", "disponible", etc.
        Page-->>Extractor: Stock Status Evaluated
    end
    
    Note over Extractor: Compilation Complete
    Extractor-->>Extractor: Return Final Product Record
```
