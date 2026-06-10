import argparse
import json
import os
import sys
from pydantic import BaseModel, Field
from rapidocr import RapidOCR
from pydantic_ai import Agent
from dotenv import load_dotenv

load_dotenv()

class TransactionData(BaseModel):
    status: str | None = None
    amount: float | None = None
    sender_name: str | None = None
    sender_upi: str | None = None
    receiver_name: str | None = None
    receiver_upi: str | None = None
    bank: str | None = None
    timestamp: str | None = None
    reference_id: str | None = None
    payment_type: str | None = None
    utr_id: str | None = None


def image_ocr(image_path):
    if not os.path.exists(image_path):
        print(f"Error: Image file '{image_path}' not found.", file=sys.stderr)
        sys.exit(1)
    
    engine = RapidOCR()
    result = engine(image_path)
    if result and result[0]:
        return [item[1] for item in result[0]] if isinstance(result[0], list) and isinstance(result[0][0], list) else result.txts
    return result.txts if hasattr(result, 'txts') else []


def build_raw_text(txts):
    if not txts:
        return ""
    return " ".join(str(token) for token in txts)


def extract_with_gemini(raw_text):
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("Error: GOOGLE_API_KEY environment variable is not set.", file=sys.stderr)
        print("Please set it in your .env file or run with '--no-llm' to skip LLM extraction.", file=sys.stderr)
        sys.exit(1)

    agent = Agent('google:gemini-flash-lite-latest', output_type=TransactionData)
    prompt = (
        "Extract transaction details from the raw OCR text below. "
        "Return ONLY valid JSON matching this schema exactly: "
        "{status, amount, sender_name, sender_upi, receiver_name, receiver_upi, bank, timestamp, reference_id, payment_type, raw_text}. "
        "For `payment_type` return a single value: either 'received', 'sent', or null. "
        "If a field is missing, use null. Do not add extra keys.\n\n"
        f"RAW TEXT:\n{raw_text}"
    )
    result = agent.run_sync(prompt)
    return result.output

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hybrid OCR — Transaction Extractor")
    parser.add_argument(
        "--image", 
        type=str, 
        default="1.jpeg", 
        help="Path to the transaction receipt/screenshot image (default: 1.jpeg)"
    )
    parser.add_argument(
        "--no-llm", 
        action="store_true", 
        help="Skip Gemini LLM extraction and only display raw OCR text"
    )
    args = parser.parse_args()

    print(f"--- Running OCR on: {args.image} ---")
    txts = image_ocr(args.image)
    raw_text = build_raw_text(txts)

    if not raw_text.strip():
        print("Warning: No text could be extracted from the image.", file=sys.stderr)
        sys.exit(1)

    print("\nEXTRACTED RAW TEXT:")
    print("-" * 40)
    print(raw_text)
    print("-" * 40)

    if args.no-llm:
        print("\nSkipping LLM extraction as requested (--no-llm).")
    else:
        print("\nInvoking Gemini for structured extraction...")
        parsed = extract_with_gemini(raw_text)
        print("\nSTRUCTURED JSON:")
        print(parsed.model_dump_json(indent=2))