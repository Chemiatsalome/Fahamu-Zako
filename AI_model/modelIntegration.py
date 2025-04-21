from together import Together
from flask import Flask, render_template, jsonify, request, send_file, send_from_directory, current_app
import os
import PyPDF2
import pyttsx3  # For text-to-speech functionality
# Example import for video generation (use any video generation library or API)
import moviepy.editor as mp  # For generating a basic video using text-to-speech
os.environ["IMAGEMAGICK_BINARY"] = r"C:\Program Files\ImageMagick-7.1.1-Q16-HDRI\magick.exe"

from flask import Blueprint, render_template, request, redirect, url_for, session,flash

# from models.user import User
# from app import db

chat_bp = Blueprint("chat", __name__)

# Define paths
VIDEO_DIRECTORY = r"C:\Users\Salome\Desktop\Fahamu Haki Zako\static\video"
AUDIO_DIRECTORY = r"C:\Users\Salome\Desktop\Fahamu Haki Zako\static\video"

@chat_bp.route('/video/<filename>')
def serve_video(filename):
    return send_from_directory(VIDEO_DIRECTORY, filename)

# Initialize the client with API key
client = Together(api_key="e3ab4476326269947afb85e9c0b0ed5fe9ae2949e27ed3a38ee4913d8f807b3e")

# Define delivery methods
def get_summary_persona(delivery_method, pdf_text):
    personas = {
        "text": "You are a helpful assistant who explains legal documents in simple terms. Summarize the following document, organizing the summary into easy-to-understand sections with clear headings, and highlighting the main points and any important terms. Replace the asterics with html tags for headings",
        "visual": "You are a helpful assistant who explains legal documents in simple terms. Summarize the following document by organizing the content into easy-to-understand sections with clear headings, and suggest visuals that could help clarify the concepts.",
        "audio": "You are a helpful assistant who explains legal documents in simple terms. Summarize the following document clearly, focusing on the main ideas and using straightforward language to ensure it's suitable for an audio presentation.",
        "video": "You are a helpful assistant who explains legal documents in simple terms. Summarize the following document, organizing it into well-defined sections with headings, and ensuring the summary is suitable for video presentation."
    }


    prompt = personas.get(delivery_method, "Please select a valid delivery method.")

    # Handle text, visual, and audio requests as before
    if delivery_method in ["text", "visual"]:
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.2-11B-Vision-Instruct-Turbo",
            messages=[
                {
                    "role": "system",
                    "content": prompt
                },
                {
                    "role": "user",
                    "content": f"Summarize the following document:\n{pdf_text}"
                }
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
        summary = f"Audio Summary of the Document:\n{pdf_text[:200]}..."  # First 200 characters for audio
        return summary
    elif delivery_method == "video":
        summary = f"Video Summary of the Document:\n{pdf_text[:200]}..."  # First 200 characters for video
        return summary
    else:
        return "Invalid delivery method selected."


def generate_video(summary_text):
    # Generate a basic video using moviepy or any other video generation tool
    tts_engine = pyttsx3.init()
    audio_file = "summary_audio.mp3"
    video_file = "summary_video.mp4"

    # Create audio from text using pyttsx3
    tts_engine.save_to_file(summary_text, audio_file)
    tts_engine.runAndWait()

    # Generate a video (simple video with text and audio)
    # You can customize this section for more sophisticated video generation
    video_clip = mp.TextClip(summary_text, fontsize=24, color='white', bg_color='black', size=(1280, 720))
    video_clip = video_clip.set_duration(10)
    video_clip = video_clip.set_audio(mp.AudioFileClip(audio_file))

    # Save the video
    video_clip.write_videofile(video_file, fps=24)
    
    return video_file



def format_summary_for_html(summary):
    # Split the summary into sections based on headings
    sections = summary.split("\n")
    formatted_summary = ""

    for section in sections:
        if section.strip():  # Ensure the section is not empty
            # Check if the section is a heading (this can be adjusted for your specific headings)
            if section.strip().upper() in ["OVERVIEW", "KEY OBJECTIVES", "KEY PROVISIONS", "KEY PRINCIPLES"]:
                formatted_summary += f"<strong>{section.strip()}</strong><br>"  # Bold heading
            else:
                # If it's not a heading, treat it as a bullet point
                formatted_summary += f"<li>{section.strip()}</li>"

    # Wrap bullet points in an unordered list
    formatted_summary = "<ul>" + formatted_summary + "</ul>"
    
    return formatted_summary


@chat_bp.route("/summarize", methods=["POST"])
def summarize_pdf():
    data = request.get_json()
    document_name = data.get("document_name")
    delivery_method = data.get("delivery_method", "text")

    if not document_name:
        return jsonify({"error": "No document specified."}), 400

    # Construct the file path dynamically based on the selected document
    pdf_file_path = os.path.join(current_app.root_path, "static", "legal_documents", document_name)


    print(f"Checking for PDF file: {pdf_file_path}")

    if os.path.exists(pdf_file_path):
        print("PDF file found. Reading content...")

        # Read PDF content
        pdf_reader = PyPDF2.PdfReader(pdf_file_path)
        pdf_text = ''
        for page_num, page in enumerate(pdf_reader.pages):
            page_text = page.extract_text()
            if page_text:
                pdf_text += page_text + '\n'
            else:
                print(f"Failed to extract text from page {page_num}")

        if not pdf_text.strip():
            return jsonify({"error": "No text found in the PDF."}), 400

        # Generate summary
        summary = get_summary_persona(delivery_method, pdf_text)
        
        if summary:
            print("Summary generated successfully.")
            formatted_summary = format_summary_for_html(summary)

            if delivery_method == "audio":
                engine = pyttsx3.init()
                engine.save_to_file(summary, os.path.join(AUDIO_DIRECTORY, "summary_audio.mp3"))
                engine.runAndWait()

            if delivery_method == "video":
                video_file_path = generate_video(summary)
                video_url = f"/video/{os.path.basename(video_file_path)}"
                return jsonify({"video_url": video_url}), 200

            return jsonify({"summary": summary}), 200
        else:
            return jsonify({"error": "No summary generated."}), 500
    else:
        return jsonify({"error": "PDF file not found."}), 404


from langdetect import detect, DetectorFactory

DetectorFactory.seed = 0  # Ensure consistent language detection

@chat_bp.route('/chat', methods=['POST'])
def chat():
    # Get the user's message from the request
    user_message = request.json.get('message')

    if not user_message:
        return jsonify({"error": "No message provided."}), 400

    # Detect language
    try:
        user_language = detect(user_message)
    except:
        user_language = "en"  # Default to English if detection fails

    # Set language-specific instructions
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


    # AI Model Request
    response = client.chat.completions.create(
        model="meta-llama/Llama-3.2-11B-Vision-Instruct-Turbo",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        max_tokens=512,
        temperature=0.7
    )

    # Process AI response
    if response and response.choices:
        bot_reply = response.choices[0].message.content
        return jsonify({"reply": bot_reply}), 200

    return jsonify({"reply": "I'm sorry, I couldn't process that. Could you rephrase?"}), 500
