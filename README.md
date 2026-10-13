# 🌍 Wanderlust AI Travel Planner

🚀 **Live Demo:** [Click here to try Wanderlust AI Travel Planner](https://wanderlust-ai-travel-planner-agent-system.streamlit.app/)

An AI-powered travel planning application built with **Python, Agno, and Groq** that generates personalized, day-by-day travel itineraries based on destination, travel dates, trip duration, budget, arrival airport, and travel preferences.

The application combines LLM-powered itinerary generation, web search, optional flight data, and calendar export to help users plan their trips through a simple interface.

## ✨ Features

### 🤖 AI-Powered Travel Planning
- Generates personalized, day-by-day travel itineraries.
- Organizes activities into morning, afternoon, and evening schedules.
- Considers the destination, travel dates, duration, budget, and user preferences.
- Uses Agno agents with Groq-hosted language models for itinerary generation.

### 🔍 Web Search Integration
- Uses the Tavily API to search for travel-related information.
- Helps discover attractions, restaurants, local recommendations, and practical travel tips.
- Provides additional context for itinerary generation.

### ✈️ Flight Information
- Integrates with the AviationStack API for flight information.
- Uses the specified airport code to retrieve available flight data when the API is configured.
- Supports flight-related information alongside itinerary planning.

### 📅 Calendar Export
- Exports itinerary information as an `.ics` calendar file.
- Supports importing calendar events into compatible calendar applications, such as Google Calendar, Apple Calendar, and Outlook.

### 💰 Budget-Aware Planning
- Considers the user's stated travel budget and preferences.
- Generates suggested travel activities and budget breakdowns.
- Helps users organize their trip within their planned spending limit.

### 🔐 Secure Configuration
- Stores API credentials in a local `secrets.toml` configuration file.
- Supports environment-specific configuration.
- Uses `.gitignore` to help prevent sensitive files from being committed to GitHub.

## 🛠️ Tech Stack

| Category | Technologies |
|---|---|
| Programming Language | Python 3.13 |
| Web UI | Streamlit |
| AI Agent Framework | Agno |
| LLM API | Groq API |
| AI Models | LLaMA 3.3 70B, GPT-OSS-20B, depending on model availability |
| Web Search | Tavily API |
| Flight Data | AviationStack API |
| HTTP Requests | requests |
| Calendar Export | icalendar |
| Configuration | tomllib |
| Date Handling | datetime |
| File Handling | pathlib |
| Text Parsing | re |
| Code Editor | Visual Studio Code |
| Version Control | Git and GitHub |
| Deployment | Streamlit Community Cloud |
| Terminal | PowerShell |

## 🧠 AI Models

The application can use supported language models available through Groq.

- **LLaMA 3.3 70B** — Meta's language model, when available for the configured Groq account.
- **GPT-OSS-20B** — OpenAI's open-weight model served through Groq, when available.

The configured model is controlled by the `GROQ_MODEL` setting. Model availability may change, so use a model ID currently supported by your Groq account.

## 🔑 APIs Required

### 1. Groq API
Used for AI-powered itinerary generation.

Get an API key: https://console.groq.com/keys

### 2. Tavily API
Used for travel-related web searches.

Get an API key: https://app.tavily.com/

### 3. AviationStack API (Optional)
Used to retrieve flight information.

Get an API key: https://aviationstack.com/

## 🚀 Getting Started

### Prerequisites
- Python 3.13 or a compatible Python version.
- Git.
- API keys for Groq and Tavily.
- An AviationStack API key if flight data is required.

### 1. Clone the Repository

```bash
git clone https://github.com/AfzalManihar/wanderlust-ai-travel-planner.git
cd wanderlust-ai-travel-planner
```

Replace `YOUR_USERNAME` with your GitHub username and use your actual repository URL.

### 2. Create a Virtual Environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Configure API Keys

Create the configuration file at:

```text
.streamlit/secrets.toml
```

Example configuration:

```toml
GROQ_API_KEY = "your_groq_api_key"
TAVILY_API_KEY = "your_tavily_api_key"
AVIATIONSTACK_API_KEY = "your_aviationstack_api_key"
GROQ_MODEL = "your_supported_groq_model_id"
```

Replace the example values with your own credentials. The AviationStack key is optional if flight data is not needed.

**Security:** Never commit your real API keys to GitHub. Keep the actual `secrets.toml` file private and commit only a safe example template.

### 5. Run the Application

```bash
streamlit run app.py
```

Open the local URL shown in your terminal, usually:

```text
http://localhost:8501
```

Enter your trip details and preferences, then generate your itinerary.

## 🧳 Example Trip

Try the following sample input:

- **Destination:** London, United Kingdom
- **Start Date:** 15 November 2026
- **Duration:** 3 days
- **Budget:** $1,000 USD
- **Arrival Airport:** LHR
- **Travelers:** 2 adults

**Travel Preferences:**

```text
Plan a 3-day London trip for 2 adults with a budget of $1,000 USD.

Include:
- Top attractions to visit
- Budget-friendly accommodation suggestions
- Local transport tips
- Affordable food recommendations
- Budget breakdown
- Suggested visiting times
- Practical travel tips

Use a clear day-by-day format with morning, afternoon, and evening activities. Label each day as Day 1, Day 2, and Day 3.
```

The generated recommendations should be treated as AI-generated suggestions. Verify current prices, opening hours, availability, and travel information before booking.

## 📁 Project Structure

```text
wanderlust-ai-travel-planner/
│
├── app.py                    # Main Streamlit application
├── requirements.txt          # Python dependencies
├── README.md                 # Project documentation
├── .gitignore                # Git ignore rules
│
└── .streamlit/
    ├── secrets.toml          # Local API credentials (not committed)
    └── secrets.toml.example  # Safe configuration template
```

## ⚙️ How It Works

1. **User Input:** The user enters the destination, start date, duration, budget, airport code, and preferences.
2. **Travel Research:** The application uses Tavily to search for relevant travel information.
3. **Flight Lookup:** AviationStack can provide flight information when configured.
4. **AI Generation:** An Agno agent uses the configured Groq language model to generate a personalized itinerary.
5. **Itinerary Display:** The generated travel plan is presented in the Streamlit interface.
6. **Calendar Export:** The user can export itinerary information as an `.ics` file.

## 🛡️ Security Best Practices

- Keep API keys in `.streamlit/secrets.toml`.
- Add the real secrets file and virtual environment to `.gitignore`.
- Never upload API keys, passwords, or other private credentials.
- Use Streamlit's secrets configuration when deploying the app.
- Rotate any API key that is accidentally exposed.

## 🔮 Future Improvements

- React frontend with a FastAPI backend.
- Interactive maps and route visualization.
- Live hotel and accommodation integrations.
- More detailed transportation and cost estimates.
- Multi-agent travel planning workflows.
- Improved itinerary validation and user feedback.

## 👨‍💻 Author

**Afzal Manihar**

- **GitHub:** [Afzal Manihar](https://github.com/AfzalManihar)
- **LinkedIn:** [Afzal Manihar](https://www.linkedin.com/in/afzal-manihar-bb0183308/)
- **Portfolio:** [Afzal Manihar](https://afzalmanihar.github.io/)

---

*Wanderlust AI Travel Planner — Plan smarter, explore more.*
