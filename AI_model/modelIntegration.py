from together import Together
from flask import Blueprint, jsonify, request, send_from_directory, current_app
import os
import PyPDF2
import pyttsx3
import moviepy.editor as mp
import time
from langdetect import detect, DetectorFactory

import os
import json

# Use module path instead of current_app at import time
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "cache")

# Set seed for consistent language detection
DetectorFactory.seed = 0

chat_bp = Blueprint("chat", __name__)

# Define directories and ensure they exist
VIDEO_DIRECTORY = r"C:\Users\Salome\Desktop\Fahamu Haki Zako\static\video"
AUDIO_DIRECTORY = r"C:\Users\Salome\Desktop\Fahamu Haki Zako\static\audio"
os.makedirs(VIDEO_DIRECTORY, exist_ok=True)
os.makedirs(AUDIO_DIRECTORY, exist_ok=True)

@chat_bp.route('/audio/<filename>')
def serve_audio(filename):
    return send_from_directory(AUDIO_DIRECTORY, filename)

@chat_bp.route('/video/<filename>')
def serve_video(filename):
    return send_from_directory(VIDEO_DIRECTORY, filename)

# Initialize Together client
client = Together(api_key="e3ab4476326269947afb85e9c0b0ed5fe9ae2949e27ed3a38ee4913d8f807b3e")

def get_summary_persona(delivery_method, pdf_text):
    personas = {
        "text": "You are a helpful assistant who explains legal documents in simple terms. Summarize the following document, organizing the summary into easy-to-understand sections with clear headings, and highlighting the main points and any important terms. Replace the asterics with html tags for headings",
        "visual": "You are a helpful assistant who explains legal documents in simple terms. Summarize the following document by organizing the content into easy-to-understand sections with clear headings, and suggest visuals that could help clarify the concepts.",
        "audio": "You are a helpful assistant who explains legal documents in simple terms. Summarize the following document clearly, focusing on the main ideas and using straightforward language to ensure it's suitable for an audio presentation.",
        "video": "You are a helpful assistant who explains legal documents in simple terms. Summarize the following document, organizing it into well-defined sections with headings, and ensuring the summary is suitable for video presentation."
    }

    prompt = personas.get(delivery_method, "Please select a valid delivery method.")

    if delivery_method in ["text", "visual"]:
        response = client.chat.completions.create(
            model="meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Summarize the following document:\n{pdf_text}"}
            ],
            max_tokens=512,
            temperature=0.7,
            top_p=0.7,
            top_k=50,
            repetition_penalty=1,
            stop=["<|eot_id|>", "<|eom_id|>"],
        )
        if response.choices:
            return response.choices[0].message.content
        else:
            return None
    elif delivery_method == "audio":
        # For audio/video, it's better to summarize the whole text, but here a snippet for testing
        summary = f"Audio Summary of the Document:\n{pdf_text[:200]}..."
        return summary
    elif delivery_method == "video":
        summary = f"Video Summary of the Document:\n{pdf_text[:200]}..."
        return summary
    else:
        return "Invalid delivery method selected."

def generate_audio(text, audio_path):
    os.makedirs(os.path.dirname(audio_path), exist_ok=True)
    engine = pyttsx3.init()
    engine.save_to_file(text, audio_path)
    engine.runAndWait()

    timeout = 10
    waited = 0
    while not os.path.exists(audio_path) and waited < timeout:
        time.sleep(0.5)
        waited += 0.5

    if os.path.exists(audio_path):
        print(f"Audio file created at {audio_path}")
        return True
    else:
        print(f"Failed to create audio file at {audio_path}")
        return False

def generate_video(summary_text):
    audio_file = os.path.join(AUDIO_DIRECTORY, "summary_audio.mp3")
    video_file = os.path.join(VIDEO_DIRECTORY, "summary_video.mp4")

    os.makedirs(AUDIO_DIRECTORY, exist_ok=True)
    os.makedirs(VIDEO_DIRECTORY, exist_ok=True)

    tts_engine = pyttsx3.init()
    tts_engine.save_to_file(summary_text, audio_file)
    tts_engine.runAndWait()

    timeout = 10
    waited = 0
    while not os.path.exists(audio_file) and waited < timeout:
        time.sleep(0.5)
        waited += 0.5

    if not os.path.exists(audio_file):
        raise FileNotFoundError(f"Audio file was not created: {audio_file}")

    video_clip = mp.TextClip(summary_text, fontsize=24, color='white', bg_color='black', size=(1280, 720))
    video_clip = video_clip.set_duration(10)
    audio_clip = mp.AudioFileClip(audio_file)
    video_clip = video_clip.set_audio(audio_clip)

    video_clip.write_videofile(video_file, fps=24, codec="libx264")

    return video_file

def format_summary_for_html(summary):
    sections = summary.split("\n")
    formatted_summary = ""
    for section in sections:
        if section.strip():
            if section.strip().upper() in ["OVERVIEW", "KEY OBJECTIVES", "KEY PROVISIONS", "KEY PRINCIPLES"]:
                formatted_summary += f"<strong>{section.strip()}</strong><br>"
            else:
                formatted_summary += f"<li>{section.strip()}</li>"
    return "<ul>" + formatted_summary + "</ul>"


def load_pdf_text_with_cache(document_name, pdf_file_path):
    """
    Load PDF text from cache if available; otherwise, extract from PDF and cache it.
    """
    cache_path = os.path.join(CACHE_DIR, document_name + ".json")

    # Return cached text if exists
    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            cached = json.load(f)
            pdf_text = cached.get("text", "")
            if pdf_text:
                print(f"Loaded cached text for {document_name}")
                return pdf_text

    # Extract text from PDF
    pdf_reader = PyPDF2.PdfReader(pdf_file_path)
    pdf_text = ''
    for page in pdf_reader.pages:
        text = page.extract_text()
        if text:
            pdf_text += text + '\n'

    # Ensure the cache directory exists before writing
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)

    # Cache the extracted text
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump({"text": pdf_text}, f)

    print(f"Extracted and cached text for {document_name}")
    return pdf_text
# Predefined summaries for fallback
FALLBACK_SUMMARIES = {
    "2010-making-the-kampala-convention-work-thematic-en.pdf": (
        "This document discusses the implementation of the Kampala Convention, focusing on "
        "thematic areas such as conflict-induced displacement, protection of displaced persons, "
        "and recommendations for African governments and institutions."
    ),
    "African_Charter_Human_Peoples_Rights.pdf": (
        "The African Charter on Human and Peoples' Rights outlines the rights of individuals "
        "and peoples in Africa, including civil, political, economic, social, and cultural rights, "
        "and the obligations of member states."
    ),
    "compedium_key_human_rights.pdf": (
        "A compendium summarizing key human rights frameworks, treaties, and conventions relevant "
        "to Africa, highlighting major principles and protections."
    ),
    "graduate-legislative-fellowship-application-dec2024-fillable.pdf": (
        "This PDF provides instructions and application forms for the Graduate Legislative Fellowship, "
        "detailing eligibility criteria, objectives, and submission guidelines."
    ),
    "human_rights_strategy_for_africa.pdf": (
        "Outlines strategic priorities and action plans for advancing human rights across African states, "
        "with recommendations for governments, NGOs, and institutions."
    ),
    "Kampala_Convention.pdf": (
        "The Kampala Convention is Africa's first legally binding instrument addressing the rights "
        "and protection of internally displaced persons, detailing obligations of states and institutions."
    ),
    "Specialised Agencies & Institutions _ African Union.pdf": (
        "Provides an overview of specialized agencies and institutions within the African Union, "
        "describing their mandates, functions, and how they support human rights and governance."
    ),
}

@chat_bp.route("/summarize", methods=["POST"])
def summarize_pdf():
    data = request.get_json()
    document_name = data.get("document_name")
    delivery_method = data.get("delivery_method", "text")

    if not document_name:
        return jsonify({"error": "No document specified."}), 400

    pdf_file_path = os.path.join(current_app.root_path, "static", "legal_documents", document_name)
    print(f"Checking for PDF file: {pdf_file_path}")

    if not os.path.exists(pdf_file_path):
        return jsonify({"error": "PDF file not found."}), 404

    # Try AI summary
    try:
        pdf_text = load_pdf_text_with_cache(document_name, pdf_file_path)
        if not pdf_text.strip():
            raise ValueError("PDF has no text.")

        summary = get_summary_persona(delivery_method, pdf_text)
        if not summary:
            raise ValueError("AI summary not generated.")

    except Exception as e:
        # Fallback to predefined summaries
        print(f"AI model failed or error occurred: {str(e)}")
        summary = FALLBACK_SUMMARIES.get(document_name, "Summary not available for this document.")

    if delivery_method == "audio":
        audio_path = os.path.join(AUDIO_DIRECTORY, "summary_audio.mp3")
        success = generate_audio(summary, audio_path)
        if not success:
            return jsonify({"error": "Audio generation failed."}), 500
        audio_url = "/static/audio/summary_audio.mp3"
        return jsonify({"audio_url": audio_url, "fallback_used": True}), 200

    elif delivery_method == "video":
        video_path = generate_video(summary)
        video_url = f"/static/video/{os.path.basename(video_path)}"
        return jsonify({"video_url": video_url, "fallback_used": True}), 200

    else:  # text and visual
        return jsonify({"summary": summary, "fallback_used": True}), 200


@chat_bp.route('/chat', methods=['POST'])
def chat():
    data = request.get_json(silent=True) or {}
    user_message = data.get('message')

    if not isinstance(user_message, str) or not user_message.strip():
        return jsonify({"error": "No message provided. Send JSON { 'message': '...' }."}), 400

    try:
        user_language = detect(user_message)
    except:
        user_language = "en"

    if user_language == 'sw':
        system_prompt = """
        Wewe ni mtaalamu wa haki za binadamu aliyeundwa na timu ya wataalamu wa Kiafrika wakiongozwa na Salome Monthe Chemiat.
        Kazi yako ni kutoa mwongozo wa kisheria unaotegemea nyaraka rasmi za haki za binadamu kutoka Afrika na kimataifa.

        Tegemea nyaraka kama:
        - Mkataba wa Afrika wa Haki za Binadamu na Watu
        - Itifaki mbalimbali za Umoja wa Afrika
        - Mikataba ya Umoja wa Mataifa kuhusu haki za binadamu
        - Katiba na mifumo ya sheria ya kitaifa inapowezekana

        Majukumu yako ni:
        - Kuelezea na kufafanua haki za kisheria
        - Kupendekeza hatua madhubuti kulingana na sheria
        - Endapo kuna uhitaji, toa mawasiliano ya dharura au namba za msaada (hotlines), hasa kwa masuala ya dharura kama unyanyasaji wa nyumbani, ukatili kwa watoto, au usafirishaji haramu wa binadamu
        - Kuelimisha watumiaji kwa njia inayochochea haki, uelewa, na uwezeshaji

        Matamshi yako yawe ya heshima, ya msaada, na ya kuelimisha.
        Tumia HTML kwenye majibu yako kwa kutumia <strong> kusisitiza, <p> kwa uwazi, na <ul> au <ol> kwa kutoa ushauri kwa mpangilio.

        Usiseme “Siwezi kutoa ushauri wa kisheria.”
        Badala yake sema: “Kulingana na mifumo ya haki za binadamu, haya ndiyo mambo muhimu ya kufahamu…”
        """
    else:
        system_prompt = """
        You are a specialized AI developed by a team of African human rights experts and technologists, led by Salome Monthe Chemiat.
        Your role is to provide legal guidance rooted in African and international human rights instruments.

        Rely on authoritative documents such as:
        - The African Charter on Human and Peoples’ Rights
        - Protocols of the African Union
        - UN human rights conventions
        - National constitutions and legal frameworks (where applicable)

        Your task is to:
        - Interpret and explain legal rights
        - Recommend actionable steps grounded in law
        - Where appropriate, include relevant hotlines or emergency contacts, especially for urgent issues such as domestic violence, child abuse, or trafficking
        - Educate users in a way that promotes justice, awareness, and empowerment

        Your tone must be informative, respectful, and supportive.
        Respond using HTML for formatting, using <strong> for emphasis, <p> for clarity, and <ul> or <ol> for structured advice.

        Do not say "I cannot give legal advice."
        Instead, say: "Based on human rights frameworks, here’s what you need to know…"
        """

    try:
        response = client.chat.completions.create(
            model="meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=512,
            temperature=0.7
        )
    except Exception as e:
        return jsonify({"error": "Upstream model error", "details": str(e)}), 502

    if response and response.choices:
        bot_reply = response.choices[0].message.content
        return jsonify({"reply": bot_reply}), 200

    return jsonify({"reply": "I'm sorry, I couldn't process that. Could you rephrase?"}), 500

@chat_bp.route("/upload-summarize", methods=["POST"])
def upload_summarize():
    uploaded_file = request.files.get("file")
    delivery_method = request.form.get("delivery_method", "text")

    if not uploaded_file:
        return jsonify({"error": "No file uploaded."}), 400

    # Handle PDF
    if uploaded_file.filename.endswith(".pdf"):
        pdf_reader = PyPDF2.PdfReader(uploaded_file)
        pdf_text = ''
        for page in pdf_reader.pages:
            text = page.extract_text()
            if text:
                pdf_text += text + '\n'
        if not pdf_text.strip():
            return jsonify({"error": "No text found in the PDF."}), 400
        text_to_summarize = pdf_text

    # You can add DOCX/TXT handling here
    elif uploaded_file.filename.endswith(".docx"):
        from docx import Document
        doc = Document(uploaded_file)
        text_to_summarize = '\n'.join([p.text for p in doc.paragraphs if p.text.strip()])
        if not text_to_summarize.strip():
            return jsonify({"error": "No text found in DOCX."}), 400
    elif uploaded_file.filename.endswith(".txt"):
        text_to_summarize = uploaded_file.read().decode('utf-8')
    else:
        return jsonify({"error": "Unsupported file type."}), 400

    # Generate summary
    summary = get_summary_persona(delivery_method, text_to_summarize)
    if not summary:
        return jsonify({"error": "No summary generated."}), 500

    if delivery_method == "audio":
        audio_path = os.path.join(AUDIO_DIRECTORY, "temp_summary_audio.mp3")
        success = generate_audio(summary, audio_path)
        if not success:
            return jsonify({"error": "Audio generation failed."}), 500
        audio_url = f"/static/audio/temp_summary_audio.mp3"
        return jsonify({"audio_url": audio_url}), 200

    elif delivery_method == "video":
        video_path = generate_video(summary)
        video_url = f"/static/video/{os.path.basename(video_path)}"
        return jsonify({"video_url": video_url}), 200

    else:  # text
        return jsonify({"summary": summary}), 200
