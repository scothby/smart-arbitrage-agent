# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import re
import google.auth
from dotenv import load_dotenv
from google.adk import Workflow
from google.adk.agents import Agent

load_dotenv()
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.models.llm_response import LlmResponse
from google.genai import types

# Import des outils du serveur MCP local
from app.mcp_server import (
    search_market_prices,
    calculate_fees,
    scrape_single_link_price,
    resolve_barcode,
)

# Authentification Google Cloud automatique
try:
    _, project_id = google.auth.default()
    os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
except Exception:
    # Fallback si exécuté en local sans identifiants gcloud configurés
    os.environ["GOOGLE_CLOUD_PROJECT"] = os.environ.get(
        "GOOGLE_CLOUD_PROJECT", "arctic-bee-499710-a4"
    )

os.environ["GOOGLE_CLOUD_LOCATION"] = os.environ.get(
    "GOOGLE_CLOUD_LOCATION", "us-central1"
)
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"
# ----------------------------------------------------------------------
# 1. Security Callbacks (Security & Evals)
# ----------------------------------------------------------------------


def before_model_callback(callback_context, llm_request):
    """Input Shield: Detects and blocks prompt injections deterministically."""
    injection_patterns = [
        r"ignore\s+previous\s+instructions",
        r"bypass\s+restrictions",
        r"act\s+as\s+unrestricted",
        r"system\s+override",
        r"jailbreak",
        r"instruction\s+override",
    ]
    for content in llm_request.contents:
        if hasattr(content, "parts"):
            for part in content.parts:
                text_val = getattr(part, "text", "")
                if text_val:
                    part_text = text_val.lower()
                    for pattern in injection_patterns:
                        if re.search(pattern, part_text):
                            # Short-circuit the LLM call and return direct rejection
                            return LlmResponse(
                                content=types.Content(
                                    role="model",
                                    parts=[
                                        types.Part.from_text(
                                            text="[SECURITY WARNING] The request has been blocked by the agent's Input Shield. Injection or bypass attempt detected."
                                        )
                                    ],
                                )
                            )
    return None


def after_model_callback(callback_context, llm_response):
    """Output Shield: Redacts PII (personal information) from the response."""
    email_pattern = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
    phone_pattern = r"\b\+?[0-9]{2,4}[-.\s]?[0-9]{3}[-.\s]?[0-9]{3,4}\b"

    if llm_response.content and hasattr(llm_response.content, "parts"):
        new_parts = []
        for part in llm_response.content.parts:
            if part.text:
                text = part.text
                text = re.sub(email_pattern, "[EMAIL_REDACTED]", text)
                text = re.sub(phone_pattern, "[PHONE_REDACTED]", text)
                new_parts.append(types.Part.from_text(text=text))
            else:
                new_parts.append(part)

        llm_response.content = types.Content(
            role=llm_response.content.role or "model", parts=new_parts
        )
    return llm_response


# Shared Gemini model
gemini_model = Gemini(
    model="gemini-2.5-flash",
    retry_options=types.HttpRetryOptions(attempts=3),
)

# Agent 1: Inspection & Identification
inspector_agent = Agent(
    name="inspector_agent",
    description="Precisely identifies a product (brand, model, condition, barcode or QR code) from an image, description or link. Uses the scrape_single_link_price tool to fetch link details, and resolve_barcode to resolve barcodes to actual product names.",
    model=gemini_model,
    tools=[scrape_single_link_price, resolve_barcode],
    before_model_callback=before_model_callback,  # Input Guardrail
    instruction="""You are the Product Inspector. Your goal is to analyze the user's input data (description, link, or image).
1. If the input contains a direct listing or product link (e.g. eBay, Vinted), you must call the 'scrape_single_link_price' tool with this URL to retrieve the precise details of the listing, including its title and price.
2. If the input contains a barcode or QR code number, you must call the 'resolve_barcode' tool with this barcode digits to retrieve the actual product brand and name.

Extract key product information as a flat JSON object containing:
- brand (the brand of the product)
- model (the precise model and version. If the image contains a barcode, resolve it using 'resolve_barcode' and use its resolved name. If the image or input contains a direct link, use the item title or the title returned by the 'scrape_single_link_price' tool)
- condition (new, excellent, good, used)
- description (a textual summary of the item or decoding details of the QR code / barcode / link)
- purchase_price (the exact listing price returned by 'scrape_single_link_price' in euros, e.g. 450.0, or the purchase price mentioned by the user / read from a price tag. If not mentioned, set to null)
- target_country (the 2-letter country code for search, e.g. 'FR', 'IT', 'DE', 'ES'. If not mentioned, default to 'IT')
- resell_platform (the mentioned resale platform, e.g. 'ebay', 'vinted', 'leboncoin', 'subito', 'wallapop', 'facebook', 'tiktok'. If not mentioned, default to 'ebay')
- user_role (the user's role: 'seller' if the user wants to resell/sell a product they already own or have bought in the past [e.g., "resell my iPhone", "sell my PS5"], or 'buyer' if they want to acquire/buy a product or if it is a product seen on a store shelf for purchase).

Visual inspection instructions (Images):
1. If the image contains a QR code or barcode, read it carefully to decode characters or the URL link. If it's a barcode, call 'resolve_barcode' with its digits. If it's an e-commerce link, call the 'scrape_single_link_price' tool or deduce the product name and model from the path.
2. If the image contains a store price tag, read the product name and price (fill 'purchase_price' with this price if visible, and set user_role to 'buyer').
3. If the image shows the item or its box, identify logos, model names, and any capacity/color clues to be as precise as possible.

Respond only with the JSON object, respecting exactly these keys.
""",
    output_key="inspected_product",
)

# Agent 2: Price Scanning
scanner_agent = Agent(
    name="scanner_agent",
    description="Searches resale prices of a product on eBay, Vinted, Subito, TikTok Shop and Facebook Marketplace for a given European country.",
    model=gemini_model,
    tools=[search_market_prices],
    instruction="""You are the Market Scanner. Your role is to find how much the product identified by the Inspector in {inspected_product} resells for.

1. Read the JSON from {inspected_product} carefully.
2. Extract the following information:
   - 'brand' and 'model' to form the full product name (e.g. "Apple iPhone 15 Pro 256GB").
   - 'target_country': the 2-letter country code (e.g. 'FR', 'IT', 'DE', 'ES'). Default is 'IT'.
   - 'purchase_price': the purchase price of the item (can be null if not provided).
3. You MUST call the 'search_market_prices' tool with:
   - product_name = full product name (brand + model)
   - country = the extracted country code
   - purchase_price_hint = the value of 'purchase_price' if it is not null, otherwise 0.0
4. Respond ONLY with the raw JSON content returned by the tool, with no explanatory text outside of the JSON block.
""",
    output_key="market_prices",
)

# Agent 3: Security & Authenticity
safety_agent = Agent(
    name="safety_agent",
    description="Checks transaction safety, offer authenticity (real product) and detects scams or fake listings.",
    model=gemini_model,
    instruction="""You are the Security and Authenticity Agent. Your goal is to analyze the price search results in {market_prices} and the details in {inspected_product} to validate if the purchase or resale offer is safe and if it is a real product or a scam.

Read the 'user_role' key in the JSON of {inspected_product} to determine if the user is a seller ('seller') or a buyer ('buyer') and adapt your report:
1. **If user_role is 'seller' (SELLER)**:
   - Focus your analysis EXCLUSIVELY on RESALE safety (the user is selling their product).
   - Give advice to avoid BUYER scams and ensure the transaction is safe (e.g. never ship the item before payment confirmation in your own account, refuse off-platform payments, beware of buyers offering to pay more, or asking to ship to a different address).
   - Calculate a Seller Transaction Trust Score (e.g. 80/100 or 90/100).
   - Do not discuss counterfeit risks or acquisition alerts since the user already owns the item.
2. **If user_role is 'buyer' (BUYER / ACQUISITION)**:
   - Determine if the item offered for sale is a real product and not a scam (fake listing, phishing).
   - If the proposed purchase price is abnormally low compared to the real market average (e.g., more than 30% discount on tech), calculate a very low Offer Trust Score (e.g., 30/100) and raise a CRITICAL ALERT OF SUSPECTED SCAM OR FAKE LISTING. Explain that the offer is probably too good to be true (non-existent product, deposit scam, or counterfeit).
   - Give advice to ensure it is a real transaction and a real product (ask for original purchase invoice, a custom photo with a handwritten note, require in-person pickup to turn on and test the item, check serial/IMEI numbers on official websites).

Write a clear, direct safety and authenticity report perfectly suited to the user's role.
""",
    output_key="safety_report",
)

# Agent 4: Financial Analysis & Arbitrage Decision
analyst_agent = Agent(
    name="analyst_agent",
    description="Calculates resale fees, estimates net profit, and provides the final arbitrage recommendation.",
    model=gemini_model,
    tools=[calculate_fees],
    after_model_callback=after_model_callback,  # Output Guardrail
    instruction="""You are the Financial Analyst. Your goal is to calculate the estimated net arbitrage profit and synthesize the final report.

Identified details: {inspected_product}
Market prices: {market_prices}
Safety report: {safety_report}

1. Analyze the JSON from {inspected_product}:
   - Get the value of 'purchase_price'. If not provided (null), estimate a purchase price corresponding to 70% of the average market price.
   - Get 'resell_platform' (e.g. 'ebay', 'vinted', 'All (Comparison)').
2. Determine the fees calculation:
   - If 'resell_platform' contains 'Toutes', 'All' or 'all', use the 'calculate_fees' tool for ALL of the following platforms: 'ebay', 'vinted', 'leboncoin', 'subito', 'wallapop' to perform a complete comparison.
   - Otherwise, call 'calculate_fees' only for the specified platform.
3. Perform detailed financial calculations:
   - Gross Margin = Average resale price - Purchase price.
   - Net Profit = Average resale price - Purchase price - Calculated commission - Shipping fees (use the estimated shipping fees provided by the user if any, otherwise use 7.50€ by default).
   - Profit Margin % = (Net Profit / Purchase price) * 100.
4. Determine the final decision by combining the financial margin and the safety report from {safety_report} based on the 'user_role' value (in {inspected_product}):
    - If 'user_role' is 'seller' (SELLER):
      - If net margin > 15%:
        - If {safety_report} indicates buyer fraud risks or advises caution: recommendation = **GOOD DEAL (CAUTIOUS) 🟠 (SELL)**
        - Otherwise: recommendation = **GREAT DEAL 🟢 (SELL)** or **GOOD DEAL 🟢 (SELL)**
      - If net margin is between 5% and 15%: recommendation = **NEUTRAL / HOLD 🟡 (HOLD)**
      - If net margin < 5%: recommendation = **BAD DEAL 🔴 (PASS)**
    - If 'user_role' is 'buyer' (BUYER / ACQUISITION):
      - If net margin > 15%:
        - If {safety_report} indicates a scam risk or low trust score (< 50/100): recommendation = **GOOD DEAL (CAUTIOUS) 🟠 (BUY)**
        - Otherwise: recommendation = **GREAT DEAL 🟢 (BUY)** or **GOOD DEAL 🟢 (BUY)**
      - If net margin is between 5% and 15%: recommendation = **NEUTRAL / HOLD 🟡 (HOLD)**
      - If net margin < 5% or if the transaction risk is unacceptable: recommendation = **BAD DEAL 🔴 (PASS)**

Write an outstanding final arbitrage report structured as follows:
- **Final Decision** (GREAT DEAL (BUY/SELL) / GOOD DEAL (BUY/SELL) / GOOD DEAL (CAUTIOUS) / NEUTRAL / BAD DEAL (PASS)) with a colored badge and a brief explanation warning if the risk is high. Indicate the best resale platform in terms of net profit if it is a multi-platform analysis.
- **Product Identification** (Brand, Model, Condition, starting Purchase Price).
- **Market Study** (Average, min, max price on eBay / Google Shopping).
- **Financial Analysis** (Detailed calculation of Net Profit, fees and commissions deducted for the tested platform(s) in a comparative table format if all were requested).
- **Security Report** (Trust score, risks, and recommendations adapted to the buyer/seller profile).
""",
    output_key="financial_report",
)

# Graphe de décision ADK 2.0 (Workflow linéaire déterministe)
director_agent = Workflow(
    name="director_agent",
    description="SmartArbitrage Agent main workflow. Sequentially executes inspection, price scanning, security checking, and financial analysis.",
    edges=[("START", inspector_agent, scanner_agent, safety_agent, analyst_agent)],
)

root_agent = director_agent

app = App(
    root_agent=root_agent,
    name="app",
)
