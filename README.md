# AI Career Assistant Engine 🚀

An intelligent, full-stack career platform that automates the job search lifecycle. By leveraging **Generative AI (Google Gemini)** and advanced web scraping, this application transforms how candidates find and apply for jobs—moving from manual searching to AI-driven "point-and-click" matching.

## 🏛️ System Architecture
The platform is built on a modular **Flask** backend with a focus on high-performance parallel processing and sophisticated AI integration.

### Core Engineering Features:
- **AI-Powered CV Parsing:** Uses **Google Gemini LLM** to perform Named Entity Recognition (NER) on PDF/DOCX files, extracting structured JSON data (Skills, Experience, Education) with high accuracy.
- **Distributed Meta-Search Engine:** A modular `scrapers/` package (one file per source) runs concurrently via `ThreadPoolExecutor` with per-source timeouts, aggregating LinkedIn, Indeed, Bing, Arbeitnow, Remotive, Himalayas, FindWork.dev, RemoteOK, WeWorkRemotely, Yenibiris.com, Eleman.net, and (optionally, with a free API key) Jooble. Kariyer.net (PerimeterX bot protection) and SecretCV.com (login-gated listing pages) cannot be scraped directly and fall back to DuckDuckGo `site:` discovery, which is lower-coverage and clearly labeled as such in the code (`scrapers/ddg_fallback.py`).
- **Semantic Match Scoring:** Beyond keyword matching, the engine performs a deep semantic analysis of job descriptions vs. CV data, generating a 0-100 suitability score across five dimensions (Technical, Experience, Education, Language, and Certifications).[cite: 6, 16]
- **Automated Cover Letter Generation:** Generates professional, HTML-formatted cover letters tailored specifically to each job listing and candidate profile.[cite: 6, 19]
- **Parallel Analysis Pipeline:** Features a bulk analysis mode that processes multiple job listings simultaneously using thread-pool synchronization to minimize API latency.[cite: 1, 16]

## ✨ Key Features
- **Interactive Dashboard:** Real-time statistics tracking for job listings and CVs.[cite: 1, 20]
- **Smart Analytics:** Radar chart visualizations (Chart.js) comparing candidate profiles against "Ideal Candidate" benchmarks.[cite: 12, 16]
- **Admin Control Center:** Comprehensive management of system logs, user settings, and global AI model configurations.[cite: 1]
- **Security & Validation:** Implements CSRF protection, secure password hashing (Werkzeug), and strict file validation.[cite: 1]

## 🛠️ Tech Stack
- **Backend:** Python 3.x, Flask (Web Framework)[cite: 1]
- **AI/LLM:** Google Gemini API (Generative AI)[cite: 6, 9]
- **Database:** SQLite with SQLAlchemy ORM[cite: 1, 8]
- **Scraping:** BeautifulSoup4, DuckDuckGo Search (DDGS), Requests
- **File Processing:** PyMuPDF (PDF), python-docx (DOCX)
- **Frontend:** HTML5, CSS3 (Modern UI Kit), Bootstrap 5, Chart.js[cite: 12]

## 📂 Installation & Execution
### 1. Clone & Setup Environment
```bash
git clone [https://github.com/BerkeBey01/Akilli-is-bulma-asistani.git](https://github.com/BerkeBey01/Akilli-is-bulma-asistani.git)
cd Akilli-is-bulma-asistani
python -m venv venv
source venv/bin/activate # or venv\Scripts\activate on Windows
pip install -r requirements.txt
