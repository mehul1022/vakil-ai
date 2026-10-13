# ⚖️ VakilAI — Indian Constitutional Law Chatbot

An AI-powered legal advisor chatbot specializing in **Indian Constitutional Law**, built with Python, Flask, and Anthropic's Claude LLM.

---

## 🚀 Features

- 💬 **Interactive Chat Interface** — Clean, dark-themed UI inspired by the Indian tricolor
- 🏛️ **Deep Legal Knowledge** — Covers Indian Constitution, IPC/BNS, CrPC/BNSS, RTI, Consumer Law, Family Law
- 📜 **Article Citations** — References specific Articles, Sections, and landmark judgments
- 🔄 **Multi-turn Conversations** — Maintains context across the conversation
- ⚡ **Quick Questions** — Pre-loaded common legal questions in the sidebar
- 🔒 **Session Management** — Each user gets their own conversation history

---

## 📋 Prerequisites

- Python 3.9+
- Anthropic API Key ([Get one here](https://console.anthropic.com))

---

## 🛠️ Setup & Installation

### 1. Clone or download the project
```bash
cd ai_law_chatbot
```

### 2. Create a virtual environment
```bash
python -m venv venv

# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables
```bash
# Copy the example file
cp .env.example .env

# Edit .env and add your Anthropic API key
ANTHROPIC_API_KEY=your_api_key_here
FLASK_SECRET_KEY=any-random-secret-string
```

### 5. Run the application
```bash
python app.py
```

Open your browser and go to: **http://localhost:5000**

---

## 📁 Project Structure

```
ai_law_chatbot/
│
├── app.py                  # Main Flask application
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variables template
├── .env                    # Your actual env vars (not committed)
├── README.md               # This file
│
└── templates/
    └── index.html          # Chat interface (HTML/CSS/JS)
```

---

## 🧠 Legal Topics Covered

| Category | Details |
|---|---|
| Constitution | All 395 Articles, 12 Schedules, 104 Amendments |
| Fundamental Rights | Articles 12–35 (Part III) |
| Directive Principles | Articles 36–51 (Part IV) |
| Fundamental Duties | Article 51A (Part IVA) |
| Criminal Law | IPC/BNS 2023, CrPC/BNSS 2023 |
| Civil Law | CPC, Property, Contract Law |
| Special Laws | RTI Act, Consumer Protection, Labor Laws, Family Laws |
| Remedies | PIL, Writs (Habeas Corpus, Mandamus, etc.), FIR |

---

## 🔧 Configuration

You can customize the chatbot by modifying the `SYSTEM_PROMPT` in `app.py`:
- Add more specific legal domains
- Change the chatbot's persona/name
- Adjust response style (more formal/informal)
- Add regional language support

---

## ⚠️ Legal Disclaimer

VakilAI is for **educational and informational purposes only**. It does not constitute legal advice. For specific legal matters, always consult a qualified and licensed advocate registered with the Bar Council of India.

---

## 🛡️ Production Deployment

For production use, consider:
- Using **Redis** or a database for session/conversation storage
- Adding **rate limiting** to prevent API abuse
- Deploying with **Gunicorn**: `gunicorn -w 4 app:app`
- Setting `FLASK_DEBUG=False`
- Using **HTTPS** (SSL certificate)

---

## 📜 License

MIT License — Free to use, modify, and distribute.

---

*Satyameva Jayate — Truth Alone Triumphs* 🇮🇳
