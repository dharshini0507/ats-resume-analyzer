import os
import re
import json
import requests
import io
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from models import db, init_db, AnalysisHistory
from pypdf import PdfReader
import docx

load_dotenv()

app = Flask(__name__)
CORS(app)

# Initialize Database
init_db(app)

# API Configuration
NVIDIA_API_KEY = os.getenv('NVIDIA_API_KEY')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

def call_llm_api(messages, json_mode=False):
    # Determine which provider to use
    if OPENAI_API_KEY and OPENAI_API_KEY.startswith('sk-'):
        url = 'https://api.openai.com/v1/chat/completions'
        key = OPENAI_API_KEY
        model = os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')
    elif NVIDIA_API_KEY and NVIDIA_API_KEY.startswith('nvapi-'):
        url = 'https://integrate.api.nvidia.com/v1/chat/completions'
        key = NVIDIA_API_KEY
        model = 'meta/llama-3.1-405b-instruct' # Powerful NVIDIA model
    elif GROQ_API_KEY:
        url = 'https://api.groq.com/openai/v1/chat/completions'
        key = GROQ_API_KEY
        # model = 'llama-3.3-70b-versatile'
        model = 'llama-3.3-70b-specdec' # Fast and capable Groq model
    else:
        raise Exception("Missing API key. Set OPENAI_API_KEY or NVIDIA_API_KEY or GROQ_API_KEY in backend/.env")

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {key}',
    }
    
    payload = {
        'model': model,
        'messages': messages,
        'temperature': 0.2, # Lower temperature for better accuracy
        'max_tokens': 4096,
    }
    
    if json_mode:
        payload['response_format'] = {'type': 'json_object'}
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=45)
        if response.status_code != 200:
            print(f"LLM API error: {response.text}")
            raise Exception(f"LLM API error: {response.status_code}")
        
        data = response.json()
        return data['choices'][0]['message']['content']
    except Exception as e:
        print(f"API Call failed: {e}")
        raise

def _is_provider_config_error(error: Exception) -> bool:
    msg = str(error).lower()
    return "missing api key" in msg or "model" in msg

def extract_text_from_pdf(file_bytes):
    try:
        pdf = PdfReader(io.BytesIO(file_bytes))
        text = ""
        for page in pdf.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        print(f"PDF extraction error: {e}")
        return ""

def extract_text_from_docx(file_bytes):
    try:
        doc = docx.Document(io.BytesIO(file_bytes))
        text = "\n".join([para.text for para in doc.paragraphs])
        return text.strip()
    except Exception as e:
        print(f"DOCX extraction error: {e}")
        return ""

def get_text_from_file(file):
    if not file:
        return ""
    filename = file.filename.lower()
    content = file.read()
    if filename.endswith('.pdf'):
        return extract_text_from_pdf(content)
    elif filename.endswith('.docx') or filename.endswith('.doc'):
        return extract_text_from_docx(content)
    else:
        try:
            return content.decode('utf-8')
        except:
            return content.decode('latin-1', errors='ignore')

def parse_json_from_response(text):
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except:
            cleaned = json_match.group(0).replace(r',\s*}', '}').replace(r',\s*]', ']').replace("'", '"')
            try:
                return json.loads(cleaned)
            except:
                pass
    return {}

COMMON_SKILLS = [
    "python", "java", "javascript", "typescript", "react", "node", "express", "flask", "django",
    "sql", "postgres", "postgresql", "mysql", "mongodb", "redis", "pandas", "numpy",
    "aws", "gcp", "azure", "docker", "kubernetes", "terraform", "ci/cd", "github", "git",
    "data structures", "algorithms", "rest", "rest api", "graphql",
    "machine learning", "ml", "natural language processing", "nlp",
    "html", "css", "tailwind", "tailwind css", "redux",
    "testing", "unit testing", "system design",
]

def _normalize_text(text: str) -> str:
    return (text or "").lower()

def _extract_keywords(text: str) -> set[str]:
    text = _normalize_text(text)
    tokens = re.findall(r"[a-z]{3,}", text)
    stopwords = {
        "and", "the", "for", "with", "from", "that", "this", "your",
        "have", "will", "role", "job", "experience", "years", "more",
        "about", "into", "within", "team", "work", "able",
        "you", "are", "can", "our", "their", "they",
    }
    return {t for t in tokens if t not in stopwords}

def fallback_analyze(resume_text: str, jd_text: str) -> dict:
    resume_lower = _normalize_text(resume_text)
    jd_lower = _normalize_text(jd_text)
    jd_skills = [s for s in COMMON_SKILLS if s in jd_lower]
    resume_skills = [s for s in COMMON_SKILLS if s in resume_lower]
    matched_skills = [s for s in jd_skills if s in resume_lower]
    missing_skills = [s for s in jd_skills if s not in resume_lower]
    denom = max(len(jd_skills), 1)
    score = int(round((len(matched_skills) / denom) * 100)) if jd_skills else 0
    if score == 0:
        jd_keywords = _extract_keywords(jd_text)
        resume_keywords = _extract_keywords(resume_text)
        overlap = jd_keywords & resume_keywords
        denom_kw = max(len(jd_keywords), 1)
        kw_score = int(round((len(overlap) / denom_kw) * 100))
        if kw_score > 0: score = kw_score
        if not jd_skills:
            matched_skills = sorted(list(overlap))[:10]
            missing_skills = sorted(list(jd_keywords - overlap))[:10]
            skill_weightage = {k: 100 for k in list(jd_keywords)[:6]}
        else: skill_weightage = {}
    else: skill_weightage = {}
    if not skill_weightage:
        skill_counts = {s: jd_lower.count(s) for s in jd_skills}
        max_count = max(skill_counts.values()) if skill_counts else 1
        top_skills = sorted(jd_skills, key=lambda s: skill_counts.get(s, 0), reverse=True)[:6]
        skill_weightage = {s: int(round((skill_counts.get(s, 0) / max_count) * 100)) for s in top_skills}
    if score == 0 and len(resume_text.strip()) > 200 and len(jd_text.strip()) > 200: score = 20
    hiring_probability = max(0, min(100, score + (len(resume_skills) >= 5) * 5 - (len(missing_skills) > 6) * 10))
    rejection_reasons = ["Low keyword alignment"] if score < 60 else ["Good coverage"]
    return {
        "score": score, "hiring_probability": int(hiring_probability),
        "rejection_reasons": rejection_reasons, "matched_skills": matched_skills[:10],
        "missing_skills": missing_skills[:10], "skill_weightage": skill_weightage,
        "ats_extracted": sorted(resume_skills, key=lambda s: resume_lower.count(s), reverse=True)[:10],
        "ats_missed": missing_skills[:10], "suggestions": [], "suggested_roles": ["Software Engineer"], "feedback": []
    }

def fallback_rewrite(resume_text: str, jd_text: str, template: str) -> str:
    resume_text = (resume_text or "").strip()
    analysis = fallback_analyze(resume_text, jd_text)
    missing = analysis.get("missing_skills", [])[:8]
    matched = analysis.get("matched_skills", [])[:8]
    header = "ATS-Optimized Resume"
    keywords_line = f"\n\nKey strengths to highlight: {', '.join(matched)}" if matched else ""
    missing_bullets = f"\n\nSuggested ATS keywords to include:\n" + "\n".join([f"- {s}" for s in missing]) if missing else ""
    return f"{header}\n\n{resume_text}{keywords_line}{missing_bullets}\n"

@app.route('/api/analyze', methods=['POST'])
def analyze():
    if request.is_json:
        data = request.json
        resume_text = data.get('resumeText', '')
        jd_text = data.get('jdText', '')
    else:
        resume_file = request.files.get('resumeFile')
        jd_file = request.files.get('jdFile')
        resume_text = get_text_from_file(resume_file) if resume_file else request.form.get('resumeText', '')
        jd_text = get_text_from_file(jd_file) if jd_file else request.form.get('jdText', '')

    if not resume_text or not jd_text:
        return jsonify({"error": "Missing resume or job description content"}), 400

    prompt = f"""You are an elite HR Analyst and ATS Optimization expert. 
Analyze the Resume against the Job Description with 100% accuracy.

RESUME CONTENT:
{resume_text[:5000]}

JOB DESCRIPTION:
{jd_text[:4000]}

Return a precise JSON object with these exact features:
{{
  "score": <0-100 based on keyword match, experience, and skills>,
  "hiring_probability": <0-100 based on how well they fit the role>,
  "rejection_reasons": ["Reason 1", "Reason 2", "Reason 3"],
  "matched_skills": ["Skill A", "Skill B", ...],
  "missing_skills": ["Skill X", "Skill Y", ...],
  "skill_weightage": {{"Skill A": 95, "Skill B": 80, ...}},
  "ats_extracted": ["Key ATS Keyword 1", ...],
  "ats_missed": ["Critical Keyword 1", ...],
  "suggestions": ["Advice 1", "Advice 2", ...],
  "suggested_roles": ["Role 1", "Role 2", ...],
  "feedback": ["Strategic feedback 1", "Strategic feedback 2", ...]
}}"""

    try:
        response_text = call_llm_api([
            {'role': 'system', 'content': 'You are a professional HR data analyst. You output ONLY valid JSON.'},
            {'role': 'user', 'content': prompt}
        ], json_mode=True)

        parsed = parse_json_from_response(response_text)
        
        if not parsed or 'score' not in parsed:
            parsed = fallback_analyze(resume_text, jd_text)
        # Save to database
        try:
            history = AnalysisHistory(
                resume_text=resume_text[:2000], 
                jd_text=jd_text[:1000],
                score=parsed.get('score', 0),
                hiring_probability=parsed.get('hiring_probability', 0)
            )
            db.session.add(history)
            db.session.commit()
        except Exception as e:
            print(f"Database save failed: {e}")

        # Return extracted text for the frontend to use in rewriting
        parsed['extractedResumeText'] = resume_text
        parsed['extractedJdText'] = jd_text

        return jsonify(parsed)
    except Exception as e:
        print(f"Analyze endpoint error: {e}")
        if _is_provider_config_error(e):
            return jsonify({
                "error": str(e),
                "hint": "Configure OPENAI_API_KEY or NVIDIA_API_KEY or GROQ_API_KEY in backend/.env and restart backend."
            }), 503
        fallback_data = fallback_analyze(resume_text, jd_text)
        fallback_data['extractedResumeText'] = resume_text
        fallback_data['extractedJdText'] = jd_text
        return jsonify(fallback_data)

@app.route('/api/rewrite', methods=['POST'])
def rewrite():
    data = request.json
    resume_text = data.get('resumeText', '')
    jd_text = data.get('jdText', '')
    template = data.get('template', 'professional')
    
    prompt = f"""You are the world's best Executive Resume Writer. 
Rewrite this resume to be a high-converting, ATS-proof masterpiece.

STYLE GUIDE: {template.upper()}
Original Resume: {resume_text}
Target Job: {jd_text}

STRUCTURE:
1. Executive Header (Name, Contact, Links)
2. Professional Summary (Punchy, result-oriented)
3. Core Competencies (Keyword optimized)
4. Professional Experience (Action verbs: Spearheaded, Engineered, Orchestrated)
5. Technical Projects (Impact focused)
6. Education & Certifications

Return ONLY the rewritten resume text. No intro, no outro, no filler."""

    try:
        # IMPORTANT: json_mode=False to get plain text output
        response_text = call_llm_api([
            {'role': 'system', 'content': 'You are a professional resume writer. Return ONLY the rewritten text.'},
            {'role': 'user', 'content': prompt}
        ], json_mode=False)
        return jsonify({'rewrittenResume': response_text})
    except Exception as e:
        print(f"Rewrite endpoint error: {e}")
        if _is_provider_config_error(e):
            return jsonify({
                "error": str(e),
                "hint": "Configure OPENAI_API_KEY or NVIDIA_API_KEY or GROQ_API_KEY in backend/.env and restart backend."
            }), 503
        return jsonify({'rewrittenResume': fallback_rewrite(resume_text, jd_text, template)})

@app.route('/api/health', methods=['GET'])
def health():
    provider = "none"
    configured = False
    if OPENAI_API_KEY and OPENAI_API_KEY.startswith('sk-'):
        provider = "openai"
        configured = True
    elif NVIDIA_API_KEY and NVIDIA_API_KEY.startswith('nvapi-'):
        provider = "nvidia"
        configured = True
    elif GROQ_API_KEY:
        provider = "groq"
        configured = True
    return jsonify({
        "ok": True,
        "providerConfigured": configured,
        "provider": provider
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
