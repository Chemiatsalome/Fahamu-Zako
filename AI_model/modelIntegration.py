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

def get_summary_persona(delivery_method, pdf_text, chunk_size=5000):
    personas = {
        "text": "You are a helpful assistant who explains legal documents in simple terms. Summarize the following document, organizing the summary into easy-to-understand sections with clear headings, and highlighting the main points and any important terms. Replace the asterisks with html tags for headings.",
        "visual": "You are a helpful assistant who explains legal documents in simple terms. Summarize the following document by organizing the content into easy-to-understand sections with clear headings, and suggest visuals that could help clarify the concepts.",
        "audio": "You are a helpful assistant who explains legal documents in simple terms. Summarize the following document clearly, focusing on the main ideas and using straightforward language to ensure it's suitable for an audio presentation.",
        "video": "You are a helpful assistant who explains legal documents in simple terms. Summarize the following document, organizing it into well-defined sections with headings, and ensuring the summary is suitable for video presentation."
    }

    if delivery_method not in personas:
        return "Invalid delivery method selected."

    prompt = personas[delivery_method]

    try:
        if delivery_method in ["text", "visual"]:
            chunks = [pdf_text[i:i+chunk_size] for i in range(0, len(pdf_text), chunk_size)]
            partial_summaries = []

            for idx, chunk in enumerate(chunks):
                response = client.chat.completions.create(
                    model="meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo",
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": f"Summarize this part of the document (part {idx+1}/{len(chunks)}):\n{chunk}"}
                    ],
                    max_tokens=512,
                    temperature=0.7,
                    top_p=0.7,
                )

                if response.choices:
                    # ✅ Fixed: use dict access
                    content = response.choices[0].message["content"]
                    partial_summaries.append(content.strip())

            summary = "\n\n".join(partial_summaries)

        elif delivery_method == "audio":
            summary = f"Audio Summary of the Document:\n{pdf_text[:200]}..."
        elif delivery_method == "video":
            summary = f"Video Summary of the Document:\n{pdf_text[:200]}..."
        else:
            return "Invalid delivery method selected."

        summary += "\n\nIf you have more questions in regard to this document, please use our chatbot."
        return summary

    except Exception as e:
        import traceback
        print("Summarization failed:", traceback.format_exc())  # ✅ log full error
        return f"Error during summarization: {str(e)}\n\nIf you have more questions in regard to this document, please use our chatbot."


# Predefined summaries for fallback
FALLBACK_SUMMARIES = {
    "2010-making-the-kampala-convention-work-thematic-en.pdf": (
        "This report provides an in-depth discussion on the implementation of the Kampala Convention, "
        "with a particular focus on thematic areas such as displacement caused by armed conflict, natural "
        "disasters, and human rights abuses. It emphasizes the unique vulnerabilities faced by internally "
        "displaced persons (IDPs), including loss of homes, separation from families, and lack of access to "
        "basic services like education and healthcare. The document carefully examines how African states "
        "can translate the Convention’s legal obligations into practical measures at the national level, "
        "including developing domestic laws, strengthening institutional frameworks, and ensuring coordination "
        "with humanitarian actors. Case studies and practical examples are provided to illustrate both "
        "successes and persistent gaps. In addition, the report puts forward recommendations to the African Union, "
        "civil society organizations, and governments, calling for stronger accountability, improved data collection, "
        "and more resources dedicated to the protection and long-term reintegration of displaced populations."
    ),

    "African_Charter_Human_Peoples_Rights.pdf": (
        "The African Charter on Human and Peoples’ Rights (also called the Banjul Charter) is one of the most "
        "foundational human rights instruments in Africa. It provides a comprehensive framework that protects "
        "both individual rights and collective or ‘peoples’ rights.’ Individual rights include core civil and political "
        "freedoms such as the right to life, personal liberty, fair trial, freedom of expression, freedom from torture, "
        "and freedom of association. At the same time, the Charter highlights economic, social, and cultural rights, "
        "including the right to work, health, education, and full participation in cultural life. A unique aspect of the "
        "Charter is its emphasis on duties: it states that individuals also have responsibilities toward their families, "
        "society, and the state. Peoples’ rights outlined in the document include the right to self-determination, the "
        "right to development, and the right to a satisfactory environment. Member states are required to align their "
        "domestic laws with these principles and ensure enforcement through both national mechanisms and the African "
        "Commission on Human and Peoples’ Rights."
    ),

    "compedium_key_human_rights.pdf": (
        "This compendium serves as a comprehensive reference guide to major human rights treaties and conventions "
        "that are applicable within the African context. It summarizes key international documents such as the Universal "
        "Declaration of Human Rights, the International Covenant on Civil and Political Rights, and the International "
        "Covenant on Economic, Social and Cultural Rights, while also including African-specific instruments like the "
        "African Charter on Human and Peoples’ Rights and the Maputo Protocol. Each summary provides background on "
        "why the treaty was created, the main rights it guarantees, and the obligations it places on states. The compendium "
        "is designed not just as an academic resource, but also as a tool for policymakers, legal practitioners, and civil "
        "society organizations working on human rights advocacy. It also highlights recurring themes such as equality, "
        "non-discrimination, access to justice, and the protection of vulnerable groups, thereby serving as a roadmap for "
        "anyone trying to navigate the complex but important world of human rights law in Africa."
    ),

    "graduate-legislative-fellowship-application-dec2024-fillable.pdf": (
        "This document outlines the application form and detailed guidelines for the Graduate Legislative Fellowship, "
        "a program aimed at equipping young graduates with hands-on experience in legislative and policy-making processes. "
        "The fellowship seeks to build the next generation of leaders by exposing participants to parliamentary procedures, "
        "legislative drafting, research, and policy analysis. The document explains the objectives of the fellowship, the "
        "expected impact on professional growth, and the contributions fellows are expected to make during and after the "
        "program. Eligibility criteria are carefully spelled out, including the academic qualifications required, preferred "
        "areas of study, and personal attributes such as leadership, analytical thinking, and commitment to public service. "
        "The application also details the supporting documents that need to be submitted, deadlines for application, and "
        "the selection process, which includes both a written evaluation and interviews. The instructions are clear, practical, "
        "and designed to guide applicants step-by-step, ensuring that the process is transparent and accessible to all eligible "
        "candidates."
    ),

    "human_rights_strategy_for_africa.pdf": (
        "This strategy document presents a continent-wide vision for advancing human rights in Africa. It identifies "
        "priority areas such as strengthening democratic institutions, ensuring gender equality, protecting vulnerable "
        "groups including children and persons with disabilities, and expanding access to justice systems. The strategy "
        "acknowledges both the progress made and the persistent challenges facing African states, such as limited resources, "
        "weak enforcement of existing laws, and ongoing conflict in some regions. To address these, it sets out clear "
        "action plans for governments, non-governmental organizations, and regional institutions. These include improving "
        "data collection on rights violations, building capacity within national human rights commissions, integrating "
        "human rights education into school curricula, and fostering stronger partnerships between governments and civil "
        "society. The document also emphasizes the importance of accountability, recommending stronger monitoring and "
        "evaluation systems, as well as mechanisms for citizens to seek redress. Overall, it provides a forward-looking, "
        "multi-stakeholder roadmap for strengthening the human rights culture across Africa."
    ),

    "Kampala_Convention.pdf": (
        "The Kampala Convention, officially the African Union Convention for the Protection and Assistance of Internally "
        "Displaced Persons in Africa, represents a historic milestone in global human rights law as it is the first legally "
        "binding regional instrument dedicated to the issue of internal displacement. The Convention covers the entire cycle "
        "of displacement: prevention, protection during displacement, and long-term solutions. It obligates African states to "
        "prevent conditions that lead to displacement, including armed conflict, natural disasters, and human rights abuses. "
        "Once displacement occurs, the Convention requires governments to safeguard the dignity, security, and access to "
        "services for internally displaced persons (IDPs), including food, shelter, healthcare, and education. It also "
        "recognizes the role of non-state actors, including armed groups, and holds them accountable for displacement caused "
        "by their actions. A critical feature of the Convention is its emphasis on durable solutions, urging states to invest "
        "in safe return, local integration, or resettlement programs for IDPs. By setting legal standards and institutional "
        "responsibilities, the Kampala Convention strengthens the humanitarian and human rights response to one of Africa’s "
        "most pressing issues."
    ),

    "Specialised Agencies & Institutions _ African Union.pdf": (
        "This document provides a detailed overview of the specialized agencies and institutions established under the "
        "framework of the African Union (AU). It describes how these bodies are structured, their mandates, and their role "
        "in advancing the AU’s objectives, particularly in the areas of human rights, governance, peace, and development. "
        "Examples of such institutions include the African Commission on Human and Peoples’ Rights, which monitors and "
        "promotes compliance with the African Charter; the Pan-African Parliament, which facilitates citizen participation "
        "in continental governance; and the African Court on Human and Peoples’ Rights, which provides judicial oversight. "
        "Other specialized bodies work in health, agriculture, trade, and economic integration, reflecting the AU’s holistic "
        "approach to development. The document underscores the importance of coordination among these institutions to avoid "
        "duplication and ensure more effective delivery of services and policies. It also explains how these agencies partner "
        "with international organizations, civil society, and national governments to promote sustainable development and "
        "protect human rights across Africa."
    ),
    "compedium_key_human_rights.pdf": (
    "This compendium serves as a comprehensive reference guide to major human rights treaties and conventions "
    "that are applicable within the African context. It summarizes key international documents such as the Universal "
    "Declaration of Human Rights, the International Covenant on Civil and Political Rights, and the International "
    "Covenant on Economic, Social and Cultural Rights, while also including African-specific instruments like the "
    "African Charter on Human and Peoples’ Rights, the Maputo Protocol, and the Kampala Convention. Each section "
    "explains the historical background, the main rights guaranteed, and the obligations that states undertake when "
    "ratifying these treaties. The document is designed as both an educational resource and a practical tool for "
    "advocacy, offering clear insights into how these legal frameworks can be applied to protect individuals and "
    "communities. Themes such as equality, non-discrimination, access to justice, gender equality, and protection of "
    "vulnerable groups are emphasized throughout. Overall, the compendium acts as a roadmap for legal practitioners, "
    "civil society, policymakers, and students seeking to navigate and promote human rights within Africa and beyond."
),

}

@chat_bp.route("/summarize", methods=["POST"])
def summarize_pdf():
    data = request.get_json()
    document_name = os.path.basename(data.get("document_name", ""))  # ensure filename only
    delivery_method = data.get("delivery_method", "text")

    if not document_name:
        # Instead of error, return generic fallback
        return jsonify({
            "summary": "Summary not available. Please select a valid document.",
            "fallback_used": True
        }), 200  

    # Always relative to app root
    LEGAL_DOCS_DIR = os.path.join(current_app.root_path, "static", "legal_documents")
    pdf_file_path = os.path.join(LEGAL_DOCS_DIR, document_name)

    if not os.path.exists(pdf_file_path):
        # Instead of 404 error, fallback to predefined or generic
        summary = FALLBACK_SUMMARIES.get(document_name, "Summary not available for this document.")
        return jsonify({"summary": summary, "fallback_used": True}), 200  

    # Try AI summary
    try:
        pdf_text = load_pdf_text_with_cache(document_name, pdf_file_path)
        if not pdf_text.strip():
            raise ValueError("PDF has no text.")

        summary = get_summary_persona(delivery_method, pdf_text)
        if not summary:
            raise ValueError("AI summary not generated.")
        fallback_used = False

    except Exception as e:
        print(f"AI model failed: {str(e)}")  # Log error for debugging
        # Always default to predefined fallback
        summary = FALLBACK_SUMMARIES.get(document_name, "Summary not available for this document.")
        fallback_used = True

    # Handle delivery methods
    if delivery_method == "audio":
        audio_path = os.path.join(AUDIO_DIRECTORY, "summary_audio.mp3")
        generate_audio(summary, audio_path)
        audio_url = "/static/audio/summary_audio.mp3"
        return jsonify({"audio_url": audio_url, "fallback_used": fallback_used}), 200

    elif delivery_method == "video":
        video_path = generate_video(summary)
        video_url = f"/static/video/{os.path.basename(video_path)}"
        return jsonify({"video_url": video_url, "fallback_used": fallback_used}), 200

    else:
        return jsonify({"summary": summary, "fallback_used": fallback_used}), 200



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
