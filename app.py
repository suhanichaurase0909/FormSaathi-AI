import streamlit as st
from pypdf import PdfReader
from google import genai
from datetime import datetime
import re
import time

# ==================================================
# PAGE SETTINGS
# ==================================================

st.set_page_config(
    page_title="FormSaathi AI",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

MODEL_NAME = "gemini-3.5-flash-lite"


# ==================================================
# SESSION STATE
# ==================================================

DEFAULTS = {
    "form_text": "",
    "uploaded_name": "",
    "profile": {},
    "chat_history": [],
    "summary": "",
    "documents_ai": "",
    "deadlines_ai": "",
    "steps_ai": "",
    "eligibility_ai": "",
    "warnings_ai": "",
    "doc_checks": {},
    "ready_checks": {}
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ==================================================
# DESIGN
# ==================================================

st.markdown("""
<style>
.stApp {
    background-color: #F4F6FC;
    color: #172554;
}

.main .block-container {
    max-width: 1250px;
    padding: 2rem 2.5rem;
}

header[data-testid="stHeader"] {
    background: #F4F6FC;
}

h1, h2, h3, h4 {
    color: #172554 !important;
    font-weight: 800 !important;
}

p, li, label {
    color: #334155;
}

section[data-testid="stSidebar"] {
    background: #E9EEFF;
}

section[data-testid="stSidebar"] * {
    color: #172554;
}

.stButton > button,
.stFormSubmitButton > button {
    background: linear-gradient(110deg, #4F46E5, #0F766E);
    color: white !important;
    border: none;
    border-radius: 10px;
    min-height: 42px;
    font-weight: 700;
}

.stButton > button p,
.stFormSubmitButton > button p {
    color: white !important;
}

.stTextInput input,
.stNumberInput input,
.stTextArea textarea {
    background: white !important;
    color: #172554 !important;
    border: 1px solid #C7D2FE !important;
    border-radius: 9px;
}

[data-testid="stFileUploader"] {
    background: white;
    border: 2px dashed #818CF8;
    border-radius: 14px;
    padding: 15px;
}

[data-testid="stFileUploaderDropzone"] {
    background: #EEF2FF;
}

[data-testid="stFileUploaderDropzone"] * {
    color: #172554 !important;
}

div[data-testid="stMetric"] {
    background: white;
    border: 1px solid #DDE3F5;
    border-radius: 14px;
    padding: 18px;
}

div[data-testid="stMetricValue"] {
    color: #4F46E5 !important;
    font-weight: 800;
}

div[data-testid="stExpander"] {
    background: white;
    border: 1px solid #DDE3F5;
    border-radius: 12px;
}

[data-testid="stChatMessage"] {
    background: white;
    border: 1px solid #DDE3F5;
    border-radius: 12px;
}

button[data-baseweb="tab"] {
    color: #334155 !important;
    font-weight: 700;
}

.stProgress > div > div > div > div {
    background: linear-gradient(90deg, #4F46E5, #0F766E);
}
</style>
""", unsafe_allow_html=True)


# ==================================================
# GEMINI CONNECTION
# ==================================================

def get_client():

    api_key = st.secrets.get("GEMINI_API_KEY", "")

    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY nahi mili. secrets.toml check karo."
        )

    return genai.Client(api_key=api_key)


def ask_ai(prompt):

    client = get_client()
    last_error = None

    for attempt in range(3):

        try:

            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt
            )

            if response.text:
                return response.text.strip()

            raise ValueError("AI ne empty response diya.")

        except Exception as error:

            last_error = error
            message = str(error).upper()

            temporary = any(
                code in message
                for code in [
                    "503",
                    "429",
                    "UNAVAILABLE",
                    "RESOURCE_EXHAUSTED"
                ]
            )

            if temporary and attempt < 2:
                time.sleep(2 * (attempt + 1))
            else:
                break

    raise last_error


# ==================================================
# PDF EXTRACTION
# ==================================================

def extract_pdf(uploaded_file):

    reader = PdfReader(uploaded_file)

    pages = []

    for page in reader.pages:
        pages.append(page.extract_text() or "")

    return "\n".join(pages).strip()


# ==================================================
# DOCUMENT FINDER
# ==================================================

def find_documents(text):

    text = text.lower()

    options = [
        ("Passport-size photograph",
         ["passport-size photograph", "passport size photograph"]),
        ("Previous examination marksheet",
         ["marksheet", "mark sheet"]),
        ("College ID card",
         ["college id", "student id"]),
        ("Bonafide certificate",
         ["bonafide"]),
        ("Family income certificate",
         ["income certificate", "family income"]),
        ("Bank passbook",
         ["bank passbook", "passbook"]),
        ("Identity proof",
         ["identity proof", "aadhaar", "aadhar"]),
        ("Caste certificate",
         ["caste certificate"]),
        ("Domicile certificate",
         ["domicile certificate"]),
        ("Fee receipt",
         ["fee receipt", "tuition fee receipt"])
    ]

    found = []

    for label, keywords in options:

        if any(word in text for word in keywords):
            found.append(label)

    return found


# ==================================================
# DATE FINDER
# ==================================================

def find_dates(text):

    pattern = (
        r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"
        r"|\b\d{1,2}\s+[A-Za-z]+\s+\d{4}\b"
        r"|\b[A-Za-z]+\s+\d{1,2},?\s+\d{4}\b"
    )

    dates = []

    for line in text.splitlines():

        if re.search(pattern, line):

            line = line.strip()

            if line and line not in dates:
                dates.append(line)

    return dates[:20]


# ==================================================
# STUDENT PROFILE TEXT
# ==================================================

def get_profile_text():

    profile = st.session_state.profile

    if not profile:
        return "Student profile not provided."

    return "\n".join(
        f"{key}: {value}"
        for key, value in profile.items()
    )


# ==================================================
# AI TASK HELPER
# ==================================================

def run_analysis(session_key, prompt, spinner_text):

    with st.spinner(spinner_text):

        try:

            st.session_state[session_key] = ask_ai(prompt)

            st.success("Analysis completed successfully!")

        except Exception as error:

            st.error(f"AI Error: {error}")


# ==================================================
# HEADER
# ==================================================

st.title("🎓 FormSaathi AI")

st.subheader(
    "Your Smart Scholarship & Application Preparation Partner"
)

st.write(
    "Understand Requirements • Check Eligibility • "
    "Organize Documents • Prepare Confidently"
)

st.info(
    "Your AI-powered assistant for scholarship, internship "
    "and college application preparation."
)

st.divider()


# ==================================================
# SIDEBAR
# ==================================================

with st.sidebar:

    st.title("🎓 FormSaathi AI")

    st.write("Your personal application assistant.")

    st.divider()

    st.subheader("📌 How to use")

    st.write("1. Upload application PDF.")
    st.write("2. Explore AI analysis.")
    st.write("3. Enter student profile.")
    st.write("4. Check eligibility.")
    st.write("5. Prepare documents.")
    st.write("6. Ask questions to AI.")

    st.divider()

    st.subheader("💬 Chat Controls")

    if st.button("🧹 Clear Chat History",
                 use_container_width=True):

        st.session_state.chat_history = []
        st.rerun()

    if st.button("🔄 Reset Application",
                 use_container_width=True):

        for key, value in DEFAULTS.items():
            st.session_state[key] = value

        st.rerun()

    st.divider()

    st.caption(
        "🔒 Never share OTP, passwords or bank PINs."
    )


# ==================================================
# PDF UPLOAD
# ==================================================

st.header("📄 1. Upload Application Guidelines")

st.write(
    "Upload a scholarship, internship or college application PDF."
)

uploaded_file = st.file_uploader(
    "Choose your PDF file",
    type=["pdf"],
    help="Only PDF files are supported."
)

if uploaded_file is not None:

    try:

        extracted_text = extract_pdf(uploaded_file)

        if not extracted_text:

            st.warning(
                "PDF se readable text nahi mila. "
                "Ho sakta hai ye scanned PDF ho."
            )

        else:

            if uploaded_file.name != st.session_state.uploaded_name:

                for key in [
                    "summary",
                    "documents_ai",
                    "deadlines_ai",
                    "steps_ai",
                    "eligibility_ai",
                    "warnings_ai"
                ]:
                    st.session_state[key] = ""

                st.session_state.chat_history = []
                st.session_state.profile = {}
                st.session_state.doc_checks = {}
                st.session_state.ready_checks = {}

            st.session_state.form_text = extracted_text
            st.session_state.uploaded_name = uploaded_file.name

            st.success(
                f"✅ PDF uploaded: {uploaded_file.name}"
            )

    except Exception as error:

        st.error(f"PDF Error: {error}")


# ==================================================
# MAIN APPLICATION
# ==================================================

if st.session_state.form_text:

    text = st.session_state.form_text

    st.divider()

    # ------------------------------------------------
    # OVERVIEW
    # ------------------------------------------------

    st.header("📊 2. Application Overview")

    col1, col2, col3 = st.columns(3)

    col1.metric("PDF Status", "Uploaded ✅")

    col2.metric(
        "Total Words",
        f"{len(text.split()):,}"
    )

    col3.metric(
        "Chat Messages",
        len(st.session_state.chat_history)
    )

    st.divider()

    # ------------------------------------------------
    # AI ANALYSIS TABS
    # ------------------------------------------------

    st.header("🔍 3. AI Application Analysis")

    tabs = st.tabs([
        "📘 Summary",
        "📂 Documents",
        "📅 Deadlines",
        "📝 Apply Steps",
        "⚠️ Warnings"
    ])

    # SUMMARY

    with tabs[0]:

        st.subheader("✨ AI Application Summary")

        st.write(
            "Understand the application guidelines in simple language."
        )

        if st.button("Generate AI Summary"):

            prompt = f"""
You are FormSaathi AI.

Analyze the application guideline.

Explain:
1. What is this scheme?
2. Who can apply?
3. Eligibility conditions.
4. Benefits.
5. Financial assistance if mentioned.
6. Application process.
7. Important instructions.

Use simple language.
Never invent information.

DOCUMENT:
{text[:18000]}
"""

            run_analysis(
                "summary",
                prompt,
                "AI is reading your PDF..."
            )

        if st.session_state.summary:

            st.markdown(st.session_state.summary)

            st.download_button(
                "⬇️ Download Summary",
                data=st.session_state.summary,
                file_name="FormSaathi_Summary.txt",
                mime="text/plain"
            )

    # DOCUMENTS

    with tabs[1]:

        st.subheader("📂 Required Documents Finder")

        documents = find_documents(text)

        if documents:

            completed = 0

            for i, document in enumerate(documents):

                checked = st.checkbox(
                    document,
                    key=f"document_{i}"
                )

                if checked:
                    completed += 1

            st.progress(completed / len(documents))

            st.info(
                f"{completed} out of {len(documents)} documents ready."
            )

        else:

            st.info(
                "Automatic document detection nahi hua. "
                "AI finder use karo."
            )

        if st.button("🤖 AI Find All Required Documents"):

            prompt = f"""
Identify all required documents.

Separate:
1. Mandatory documents
2. Optional documents
3. Documents required only in special cases

Do not invent documents.
Use only the PDF.

DOCUMENT:
{text[:18000]}
"""

            run_analysis(
                "documents_ai",
                prompt,
                "Finding required documents..."
            )

        if st.session_state.documents_ai:
            st.markdown(st.session_state.documents_ai)

    # DEADLINES

    with tabs[2]:

        st.subheader("📅 Important Dates & Deadlines")

        dates = find_dates(text)

        if dates:

            for date in dates:
                st.info("📌 " + date)

        else:

            st.info("No dates detected automatically.")

        if st.button("🤖 AI Analyze Important Dates"):

            prompt = f"""
Find important dates in this application.

Identify:
1. Opening date
2. Last date to apply
3. Verification date
4. Correction window
5. Result date
6. Other important dates

Never guess dates.
If missing, say not mentioned.

DOCUMENT:
{text[:18000]}
"""

            run_analysis(
                "deadlines_ai",
                prompt,
                "Analyzing important dates..."
            )

        if st.session_state.deadlines_ai:
            st.markdown(st.session_state.deadlines_ai)

        st.warning(
            "Verify every deadline on the official portal."
        )

    # APPLICATION STEPS

    with tabs[3]:

        st.subheader("📝 Step-by-Step Application Guide")

        if st.button("Generate Application Steps"):

            prompt = f"""
Explain the application process step by step.

Include:
1. Registration
2. Login
3. Form filling
4. Document upload
5. Review
6. Final submission
7. Confirmation

Only include steps supported by the document.
Clearly label general suggestions.

DOCUMENT:
{text[:18000]}
"""

            run_analysis(
                "steps_ai",
                prompt,
                "Preparing application steps..."
            )

        if st.session_state.steps_ai:
            st.markdown(st.session_state.steps_ai)

    # WARNINGS

    with tabs[4]:

        st.subheader("⚠️ Important Warnings")

        if st.button("Check Application Warnings"):

            prompt = f"""
Review this application guideline.

Identify:
1. Important restrictions
2. Missing or unclear information
3. Confusing conditions
4. Common mistakes students should avoid
5. Details requiring official verification

Do not invent warnings.

DOCUMENT:
{text[:18000]}
"""

            run_analysis(
                "warnings_ai",
                prompt,
                "Checking important instructions..."
            )

        if st.session_state.warnings_ai:
            st.markdown(st.session_state.warnings_ai)

    st.divider()

    # ------------------------------------------------
    # STUDENT PROFILE
    # ------------------------------------------------

    st.header("👩‍🎓 4. Student Profile")

    st.write(
        "Enter your details to compare your profile with the application."
    )

    with st.form("student_profile_form"):

        left, right = st.columns(2)

        with left:

            name = st.text_input("Student Name")

            course = st.selectbox(
                "Education Level",
                [
                    "Undergraduate",
                    "Postgraduate",
                    "Diploma",
                    "Other"
                ]
            )

            year = st.selectbox(
                "Current Year",
                [
                    "1st Year",
                    "2nd Year",
                    "3rd Year",
                    "4th Year",
                    "Other"
                ]
            )

            branch = st.text_input("Branch / Stream")

            marks = st.number_input(
                "Previous Marks (%)",
                min_value=0.0,
                max_value=100.0,
                value=75.0
            )

        with right:

            income = st.number_input(
                "Annual Family Income (₹)",
                min_value=0,
                value=200000,
                step=10000
            )

            first_year = st.selectbox(
                "Are you a first-year student?",
                ["Yes", "No"]
            )

            recognized = st.selectbox(
                "Is your institution recognized?",
                ["Yes", "No", "Not sure"]
            )

            category = st.selectbox(
                "Category",
                [
                    "General",
                    "OBC",
                    "SC",
                    "ST",
                    "EWS",
                    "Other",
                    "Prefer not to say"
                ]
            )

        save_profile = st.form_submit_button(
            "💾 Save Student Profile",
            use_container_width=True
        )

    if save_profile:

        st.session_state.profile = {
            "Name": name,
            "Education": course,
            "Current Year": year,
            "Branch": branch,
            "Marks": marks,
            "Annual Family Income": income,
            "First Year": first_year,
            "Institution Recognized": recognized,
            "Category": category
        }

        st.success("Student profile saved successfully!")


    # ------------------------------------------------
    # ELIGIBILITY MATCHING
    # ------------------------------------------------

    st.divider()

    st.header("🎯 5. Smart Eligibility Matching")

    st.write(
        "AI compares your saved profile with uploaded guidelines."
    )

    if st.button("🎯 Analyze My Eligibility"):

        if not st.session_state.profile:

            st.warning("Please save your student profile first.")

        else:

            prompt = f"""
You are an eligibility analysis assistant.

Compare the student profile with the application guideline.

STUDENT PROFILE:
{get_profile_text()}

APPLICATION GUIDELINE:
{text[:18000]}

Provide:
1. Preliminary eligibility assessment.
2. Education condition.
3. Marks condition.
4. Income condition.
5. Category condition if applicable.
6. Institution condition.
7. Conditions that match.
8. Conditions that do not match.
9. Conditions that cannot be verified.
10. Next steps.

Rules:
- Never invent eligibility conditions.
- Never guarantee approval.
- Clearly mention missing information.
- Explain in simple language.
- Do not give an official eligibility decision.
"""

            run_analysis(
                "eligibility_ai",
                prompt,
                "AI is checking your profile..."
            )

    if st.session_state.eligibility_ai:

        st.subheader("📊 Your Eligibility Analysis")

        st.markdown(st.session_state.eligibility_ai)

        st.caption(
            "Preliminary AI assessment only. "
            "Final eligibility is decided by the official authority."
        )

    st.divider()

    # ------------------------------------------------
    # READINESS TRACKER
    # ------------------------------------------------

    st.header("📝 6. Application Readiness Tracker")

    readiness_items = [
        "I have read all eligibility conditions.",
        "I have arranged required documents.",
        "My personal details are correct.",
        "I have checked my income details.",
        "I have checked application deadlines.",
        "I have checked the official portal.",
        "I have reviewed uploaded documents.",
        "I have reviewed the application before submission."
    ]

    completed = 0

    for i, item in enumerate(readiness_items):

        if st.checkbox(item, key=f"readiness_{i}"):
            completed += 1

    percentage = int(
        completed / len(readiness_items) * 100
    )

    st.progress(percentage / 100)

    col1, col2 = st.columns(2)

    col1.metric("Preparation Progress", f"{percentage}%")

    col2.metric(
        "Completed Steps",
        f"{completed}/{len(readiness_items)}"
    )

    if percentage == 100:
        st.success("🎉 All preparation steps completed!")

    else:
        st.info(
            f"{len(readiness_items) - completed} steps remaining."
        )

    st.divider()

    # ------------------------------------------------
    # CHATBOT
    # ------------------------------------------------

    st.header("🤖 7. Ask FormSaathi AI")

    st.write(
        "Ask questions about your uploaded application document."
    )

    with st.expander("💡 Suggested Questions"):

        st.write("• Who can apply?")
        st.write("• Which documents are required?")
        st.write("• Explain eligibility in simple words.")
        st.write("• What is the last date?")
        st.write("• What are the benefits?")
        st.write("• Does my profile match?")
        st.write("• How do I apply?")
        st.write("• What mistakes should I avoid?")

    for message in st.session_state.chat_history:

        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    question = st.chat_input(
        "Ask anything about your application..."
    )

    if question:

        st.session_state.chat_history.append({
            "role": "user",
            "content": question
        })

        with st.chat_message("user"):
            st.markdown(question)

        prompt = f"""
You are FormSaathi AI, a friendly student application assistant.

STUDENT PROFILE:
{get_profile_text()}

UPLOADED APPLICATION:
{text[:18000]}

STUDENT QUESTION:
{question}

Instructions:
1. Use the PDF as the primary source.
2. Never invent facts or dates.
3. If information is missing, say so.
4. Explain in simple English or Hinglish.
5. Use bullet points where useful.
6. Never guarantee approval or selection.
7. Never claim to have checked a live portal.
8. Never ask for OTP, passwords or bank PIN.
9. Give practical steps.
"""

        with st.chat_message("assistant"):

            with st.spinner("🤖 FormSaathi AI is thinking..."):

                try:

                    answer = ask_ai(prompt)

                    st.markdown(answer)

                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": answer
                    })

                except Exception as error:

                    st.error(
                        "AI response nahi aa paya. Please try again."
                    )

                    st.caption(str(error))

    st.divider()

    # ------------------------------------------------
    # DOWNLOAD REPORT
    # ------------------------------------------------

    st.header("📥 8. Download Complete Application Report")

    report = f"""
FORMSAATHI AI - APPLICATION ANALYSIS REPORT
============================================

Generated: {datetime.now().strftime('%d-%m-%Y %H:%M')}

Uploaded PDF:
{st.session_state.uploaded_name}

STUDENT PROFILE
---------------
{get_profile_text()}

AI SUMMARY
----------
{st.session_state.summary or 'Not generated'}

REQUIRED DOCUMENTS
------------------
{st.session_state.documents_ai or 'Not generated'}

IMPORTANT DATES
---------------
{st.session_state.deadlines_ai or 'Not generated'}

APPLICATION STEPS
-----------------
{st.session_state.steps_ai or 'Not generated'}

ELIGIBILITY ANALYSIS
--------------------
{st.session_state.eligibility_ai or 'Not generated'}

IMPORTANT WARNINGS
------------------
{st.session_state.warnings_ai or 'Not generated'}

IMPORTANT:
Verify all details on the official application portal.
"""

    st.download_button(
        "⬇️ Download Complete Report",
        data=report,
        file_name="FormSaathi_Application_Report.txt",
        mime="text/plain",
        use_container_width=True
    )

    with st.expander("📄 View Extracted PDF Text"):

        st.text_area(
            "PDF Content",
            text[:15000],
            height=300
        )


# ==================================================
# HOME PAGE
# ==================================================

else:

    st.info(
        "👆 Upload a PDF guideline to unlock all FormSaathi AI features."
    )

    st.header("✨ What FormSaathi AI Can Do")

    features = [
        ("📘", "AI Summary",
         "Understand complicated application guidelines."),
        ("🎯", "Eligibility Matching",
         "Compare your profile with application conditions."),
        ("📂", "Document Finder",
         "Identify required application documents."),
        ("📅", "Deadline Finder",
         "Find important application dates."),
        ("📝", "Application Guide",
         "Understand the application process step by step."),
        ("⚠️", "Important Warnings",
         "Find unclear conditions and important instructions."),
        ("🤖", "AI Assistant",
         "Ask questions about your uploaded PDF."),
        ("📊", "Readiness Tracker",
         "Track your application preparation."),
        ("📥", "Download Report",
         "Download your application analysis.")
    ]

    for start in range(0, len(features), 3):

        columns = st.columns(3)

        for column, feature in zip(
            columns,
            features[start:start + 3]
        ):

            with column:

                st.subheader(
                    f"{feature[0]} {feature[1]}"
                )

                st.write(feature[2])


# ==================================================
# FOOTER
# ==================================================

st.divider()

st.markdown("### 🎓 FormSaathi AI")

st.caption(
    "Your Smart Application Preparation Partner | "
    "Always verify eligibility and deadlines on the official portal."
)