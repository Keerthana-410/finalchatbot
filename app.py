import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore, auth
from googletrans import Translator, LANGUAGES
from gtts import gTTS
import tempfile
import json
import time
from PyPDF2 import PdfReader
from docx import Document
import pytesseract
from PIL import Image

# =================== FIREBASE CONFIGURATION =================== #

# Initialize Firebase Admin SDK for Firestore (Using service account credentials)
if not firebase_admin._apps:
    cred = credentials.Certificate("path/to/your/serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

# =================== USER AUTHENTICATION =================== #

st.set_page_config(page_title="🌍 Language Translation Chatbot", layout="wide")

st.title("🌍 Language Translation Chatbot")

# Check if user is already logged in
if "user" not in st.session_state:
    st.subheader("🔑 Login / Signup")

    choice = st.radio("Select an option:", ["Login", "Signup"])

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    # Handle Signup
    if choice == "Signup":
        if st.button("Create Account"):
            try:
                user = auth.create_user_with_email_and_password(email, password)
                st.success("Account created successfully! Please log in.")
            except Exception as e:
                st.error(f"Error: {e}")

    # Handle Login
    if choice == "Login":
        if st.button("Login"):
            try:
                user = auth.sign_in_with_email_and_password(email, password)
                st.session_state["user"] = user
                st.success("Logged in successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

else:
    st.sidebar.subheader(f"Welcome, {st.session_state['user']['email']}")
    if st.sidebar.button("Logout"):
        del st.session_state["user"]
        st.success("Logged out successfully!")
        st.rerun()

    # =================== CHATBOT & TRANSLATION =================== #

    # Sidebar Settings
    with st.sidebar:
        st.header("⚙️ Settings")
        theme = st.radio("Select Theme:", ["Light", "Dark"], key="theme_select")
        if theme == "Dark":
            st.markdown("<style>body { background-color: #1e1e1e; color: white; }</style>", unsafe_allow_html=True)
        
        # Target Languages Selection
        st.header("📌 Select target languages")
        dest_languages = st.multiselect("Choose languages:", options=list(LANGUAGES.values()))
        
        # Feedback Section in Sidebar
        st.header("📝 Submit Feedback / Report Issue")
        feedback_type = st.selectbox("Select Feedback Type:", ["Translation Issue", "Usability Feedback", "Feature Request"])
        feedback_text = st.text_area("Describe your issue or suggestion:")
        if st.button("Submit Feedback"):
            feedback_data = {
                "user": st.session_state["user"]["email"],
                "type": feedback_type,
                "message": feedback_text,
                "timestamp": time.time()
            }
            db.collection("feedback").add(feedback_data)
            st.success("Thank you for your feedback! We appreciate your input.")

    # =================== TRANSLATION CHATBOT =================== #

    translator = Translator()

    def text_to_speech(text, lang):
        lang_code = next((code for code, name in LANGUAGES.items() if name.lower() == lang.lower()), "en")
        try:
            tts = gTTS(text=text, lang=lang_code)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmpfile:
                tts.save(tmpfile.name)
                return tmpfile.name
        except Exception as e:
            st.error(f"Error generating speech: {e}")
            return None

    def translate_with_retry(text, dest_lang, retries=2):
        for attempt in range(retries):
            try:
                return translator.translate(text, dest=dest_lang).text
            except Exception as e:
                if "read operation timed out" in str(e) and attempt < retries - 1:
                    time.sleep(1)
                else:
                    return f"Error: {e}"

    def extract_text_from_file(uploaded_file):
        file_type = uploaded_file.type
        if "text" in file_type:
            return uploaded_file.read().decode()
        elif "pdf" in file_type:
            pdf_reader = PdfReader(uploaded_file)
            return "\n".join([page.extract_text() for page in pdf_reader.pages if page.extract_text()])
        elif "docx" in file_type:
            doc = Document(uploaded_file)
            return "\n".join([paragraph.text for paragraph in doc.paragraphs])
        elif "image" in file_type:
            img = Image.open(uploaded_file)
            return pytesseract.image_to_string(img)
        else:
            return "Unsupported file type"

    # =================== FILE UPLOAD & TRANSLATION =================== #
    
    st.write("## 📂 File Upload & Translation")
    uploaded_file = st.file_uploader("Upload a file (TXT, PDF, DOCX, PNG, JPG)", type=["txt", "pdf", "docx", "png", "jpg", "jpeg"])
    
    if uploaded_file:
        extracted_text = extract_text_from_file(uploaded_file)
        st.write("### Extracted Text:")
        st.write(extracted_text)

        if st.button("Translate File Input"):
            if extracted_text and dest_languages:
                lang_codes = [code for code, name in LANGUAGES.items() if name in dest_languages]
                translations = {lang: translate_with_retry(extracted_text, lang) for lang in lang_codes}
                
                st.write("### 📝 Translated File Input:")
                for lang, trans in translations.items():
                    st.write(f"**{lang}:** {trans}")
                    audio_file = text_to_speech(trans, lang)
                    if audio_file:
                        st.audio(audio_file, format='audio/mp3')
                
                # Download translated file
                translation_text = "\n".join([f"{lang}: {text}" for lang, text in translations.items()])
                st.download_button(
                    label="⬇️ Download Translated File Input (TXT)",
                    data=translation_text,
                    file_name="translated_file.txt",
                    mime="text/plain"
                )
            else:
                st.write("⚠️ Please upload a file and select at least one language to translate.")
    
    # =================== TEXT INPUT SECTION =================== #

    st.write("## ✍️ Enter Text to Translate")
    user_input = st.text_area("Enter text here:")
    if st.button("Translate Text"):
        if user_input and dest_languages:
            lang_codes = [code for code, name in LANGUAGES.items() if name in dest_languages]
            translations = {lang: translate_with_retry(user_input, lang) for lang in lang_codes}
            st.write("### 📝 Translated Text:")
            for lang, trans in translations.items():
                st.write(f"**{lang}:** {trans}")
                audio_file = text_to_speech(trans, lang)
                if audio_file:
                    st.audio(audio_file, format='audio/mp3')
        else:
            st.write("⚠️ Please enter text and select at least one language to translate.")
