import argparse
import sys
import json
from models import ProductPayload
from embedding_factory import EmbeddingFactory, format_product_text

def main():
    parser = argparse.ArgumentParser(
        description="CLI tool to generate local vector embeddings from a product JSON."
    )
    # Allows reading from a file path or taking input via stdin/pipe
    parser.add_argument(
        "input_file", 
        nargs="?", 
        type=argparse.FileType("r"), 
        default=sys.stdin,
        help="Path to the JSON file payload. If empty, reads from stdin."
    )
    
    args = parser.parse_args()

    if args.input_file.isatty():
        print("Error: No input provided. Provide a JSON file path or pipe data to stdin.", file=sys.stderr)
        parser.print_help(sys.stderr)
        sys.exit(1)

    try:
        # Load and parse the JSON string
        data = json.load(args.input_file)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        # Validate data matches our ProductPayload schema
        product = ProductPayload(**data)
    except Exception as e:
        print(f"Schema Validation Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Convert the JSON payload into the text block we want embedded
    text_to_embed = format_product_text(product)
    if not text_to_embed.strip():
        print("Error: The provided JSON resulted in empty text after formatting.", file=sys.stderr)
        sys.exit(1)

    # Load Model & Generate Output
    try:
        provider = EmbeddingFactory.get_provider()
        vector = provider.generate_embedding(text_to_embed)
    except Exception as e:
        print(f"Error generating embedding: {e}", file=sys.stderr)
        sys.exit(1)

    # Print out results directly to stdout
    output = {
        "url_hash": product.url_hash or "N/A",
        "title": product.title or "N/A",
        "dimension": len(vector),
        "vector_preview": vector[:10] + ["..."] + vector[-10:], # Show start and end
        "embedding": vector
    }

    # Output to stdout safely as a valid JSON string
    print(json.dumps(output))

if __name__ == "__main__":
    main()
