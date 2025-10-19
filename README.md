# Fix&Furn Mini – Furniture Concierge & Repair Estimator

Fix&Furn Mini is a one-day demo chatbot that blends a curated showroom catalog with an IKEA Saudi partner lineup and a rule-driven repair estimator. The assistant runs entirely inside a Gradio app, taps Google Gemini with structured tool calls, and logs every customer lead, unresolved question, and post-service satisfaction note for the team.

---

## Table of Contents
1. [Demo Video](#demo-video)
2. [Key Features](#key-features)
3. [Architecture](#architecture)
4. [Datasets & Pricing References](#datasets--pricing-references)
5. [Project Layout](#project-layout)
6. [Getting Started](#getting-started)
7. [Environment Configuration](#environment-configuration)
8. [Running the App](#running-the-app)
9. [Using the Chatbot](#using-the-chatbot)
10. [Logging & Outputs](#logging--outputs)
11. [Testing](#testing)
12. [Troubleshooting](#troubleshooting)
13. [Roadmap & Ideas](#roadmap--ideas)
14. [Acknowledgements](#acknowledgements)

---

## Demo Video
> _Drop your Loom, YouTube, or MP4 link here once available._
>
> ```
> [![Fix&Furn Mini Demo](https://img.youtube.com/vi/VIDEO_ID/0.jpg)](https://www.youtube.com/watch?v=VIDEO_ID)
> ```

---

## Key Features
- **Interactive Gemini Chatbot**: Structured tool calls route user requests to product lookup, repair estimates, lead capture, feedback, and post-service satisfaction logging.
- **Two-Tier Catalog Support**: Combines five Fix&Furn hero SKUs with an IKEA Saudi dataset presented as the “Fix&Furn × IKEA Partner Line.”
- **USD-First Pricing**: IKEA prices are converted from SAR at 1 SAR ≈ 0.2667 USD; repair prices are normalized into USD tiers.
- **Repair Cost Engine**: Updated rules blend a 2023 workshop price list with 2025 U.S. averages, producing budget, standard, and rush tiers (price + ETA) per issue/material/size.
- **Customer Journey Support**: Captures leads, unresolved questions, and post-service feedback into JSONL logs for future follow-up.
- **Portable One-Day Build**: Pure Python, no database—ideal for hackathons and rapid demos.

---

## Architecture
| Layer | Description |
|-------|-------------|
| **Interface** | Gradio `ChatInterface` with a custom `chat_fn` that forwards messages to Gemini and handles multi-turn tool calls. |
| **LLM** | Google Gemini (default `models/gemini-2.5-flash`). System prompt instructs the assistant to differentiate Fix&Furn vs IKEA Partner Line, always respond in USD, and request feedback. |
| **Tooling** | `tools.py` exposes lookup, repair estimation, lead capture, unresolved question logging, and post-service feedback. Helper functions load datasets and manage append-only JSONL logs. |
| **Data** | `data/catalog.json`, `data/price_rules.json`, and `data/IKEA_SA_Furniture_*.csv` with conversion + scoring logic. |
| **Config** | `.env` holds API keys and optional model overrides. Requirements limited to Gradio, python-dotenv, google-generativeai, and supporting libs. |

---

## Datasets & Pricing References
- **Fix&Furn Catalog**: Five flagship products with SKUs, dimensions, colors, stock, warranties.
- **IKEA Saudi Dataset** (`IKEA_SA_Furniture_Web_Scrapings_sss.csv`): Scraped list of saleable furniture items; search results expose item ID, price (converted to USD), dimensions, designer, and online link.
- **Repair Pricing** (`data/price_rules.json`):
  - Levels derived from `price_list_2023.pdf` (shop rates) and `repairPriceArticle.txt` (2025 national averages).
  - Each issue contains material and size tiers with `[min_price, max_price, min_days, max_days]`.
  - Chatbot translates these into Budget / Standard / Rush options.

---

## Project Layout
```
C3/
├── app.py                     # Gradio app + Gemini orchestrator
├── tools.py                   # Tool implementations & dataset loaders
├── data/
│   ├── catalog.json
│   ├── price_rules.json
│   └── IKEA_SA_Furniture_Web_Scrapings_sss.csv
├── me/
│   ├── about_business.pdf
│   ├── business_summary.txt
│   └── system_prompt.txt
├── logs/
│   ├── feedback.jsonl         # Unanswered or unclear questions
│   ├── leads.jsonl            # Sales / repair leads
│   └── service_feedback.jsonl # Post-service satisfaction notes
├── requirements.txt
├── .env.example
└── README.md
```

---

## Getting Started
1. **Clone the repo**
   ```bash
   git clone https://github.com/your-org/fixnfurn-mini.git
   cd fixnfurn-mini
   ```
2. **Create a virtual environment (optional but recommended)**
   ```bash
   python -m venv .venv
   source .venv/bin/activate      # Windows: .venv\Scripts\activate
   ```
3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

---

## Environment Configuration
1. Copy `.env.example` to `.env`.
2. Populate the following variables:
   ```
   GEMINI_API_KEY=your-gemini-key
   # Optional override
   # GEMINI_MODEL=models/gemini-2.5-pro
   ```
3. Keep `.env` out of version control; the app loads it via `python-dotenv`.

---

## Running the App
```bash
python app.py
```
- Gradio will print a local URL (default `http://127.0.0.1:7860`).
- Add `share=True` to `demo.launch()` in `app.py` for a public tunneling link (use cautiously).

---

## Using the Chatbot
Try these starter prompts:
- “Do you have a dining table around 180 cm? What finishes are available?”
- “My glass coffee table cracked (large). How long and how much to replace the glass?”
- “I want to buy the Fix&Furn Luna desk and need it in walnut/white. Here is my email…”
- “The bookshelf repair you did last week is perfect—can I leave feedback?”

### Conversation Flow Highlights
1. **Product Discovery**: Calls `lookup_product` and returns both Fix&Furn and IKEA Partner Line matches in USD, with links.
2. **Repair Estimates**: Calls `estimate_repair`, surfaces Budget / Standard / Rush tiers with price ranges and timelines.
3. **Lead Capture**: When a user is ready to purchase or book, the assistant requests name + email + note, then calls `record_customer_interest`.
4. **Unanswered Questions**: If the dataset lacks info, the assistant logs the question via `record_feedback`.
5. **Post-Service Feedback**: The assistant can capture satisfaction, rating, and comments using `record_service_feedback`.

---

## Logging & Outputs
| File | Description |
|------|-------------|
| `logs/leads.jsonl` | Lead entries with name, email, intent, timestamp. |
| `logs/feedback.jsonl` | Unanswered questions for manual follow-up. |
| `logs/service_feedback.jsonl` | Post-service satisfaction records (purchase vs repair, sentiment, comments). |
| Console output | Mirrors log entries to aid debugging. |

---

## Testing
- **Static check**: `python -m compileall .` validates syntax.
- No automatic unit tests are bundled. For production, consider:
  - Mocking Gemini responses and validating tool routing.
  - Verifying CSV ingestion and currency conversion logic.
  - Snapshot testing of repair estimate tiers.

---

## Troubleshooting
| Symptom | Potential Fix |
|---------|----------------|
| `KeyError: 'function_calling_config'` | Ensure you upgraded `google-generativeai` to the version pinned in `requirements.txt`. |
| `google.api_core.exceptions.NotFound: models/...` | Set `GEMINI_MODEL` to one you have access to (e.g., `models/gemini-2.5-flash`). |
| Gradio refuses to start | Confirm Python 3.10+, reinstall dependencies, and check for port clashes. |
| No IKEA results | Verify `data/IKEA_SA_Furniture_Web_Scrapings_sss.csv` exists and contains rows. |

---

## Roadmap & Ideas
- Add intent-specific analytics dashboards for leads and feedback.
- Integrate real inventory APIs or ERP connectors.
- Expand IKEA dataset to include availability lead times and shipping costs.
- Introduce optional vector search or natural language filtering for the product dataset.
- Add automated tests and CI linting.

---

## Acknowledgements
- **IKEA Saudi Web Dataset**: Provided as a reference benchmark for partner products.
- **Workshop Pricing References**: `price_list_2023.pdf` and `repairPriceArticle.txt` (HomeAdvisor, Aug 2025) underpin the repair cost heuristics.
- **Gradio & Google Gemini**: Core tooling powering the conversational experience.

