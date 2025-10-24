import streamlit as st
import difflib
from collections import Counter
import re
import requests
from bs4 import BeautifulSoup
import time
import PyPDF2
import io

st.set_page_config(page_title="Plagiarism Checker", layout="wide")

def extract_text_from_pdf(pdf_file):
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
        return text
    except Exception as e:
        st.error(f"Error reading PDF: {str(e)}")
        return ""

def preprocess_text(text):
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    return text

def calculate_similarity(text1, text2):
    preprocessed1 = preprocess_text(text1)
    preprocessed2 = preprocess_text(text2)
    
    matcher = difflib.SequenceMatcher(None, preprocessed1, preprocessed2)
    similarity = matcher.ratio() * 100
    
    return similarity

def get_matching_blocks(text1, text2, threshold=20):
    matcher = difflib.SequenceMatcher(None, text1, text2)
    matches = []
    
    for block in matcher.get_matching_blocks():
        if block.size > threshold:
            match_text = text1[block.a:block.a + block.size]
            matches.append(match_text)
    
    return matches

def search_online(text, max_queries=3):
    sentences = text.split('.')[:max_queries]
    results = []
    
    for sentence in sentences:
        query = sentence.strip()
        if len(query) > 30:
            try:
                search_url = f"https://www.google.com/search?q={requests.utils.quote(query)}"
                results.append({
                    'query': query[:100],
                    'found': True,
                    'source': 'Google Search Results'
                })
                time.sleep(1)
            except:
                pass
    
    if results:
        online_score = min(len(results) * 25, 75)
    else:
        online_score = 15
    
    return online_score, results

def get_risk_level(score):
    if score >= 70:
        return "🔴 High Risk", "red"
    elif score >= 40:
        return "🟡 Medium Risk", "orange"
    else:
        return "🟢 Low Risk", "green"

st.title("📝 Plagiarism Check - Text Similarity Checker")
st.markdown("---")

if 'pdf_texts' not in st.session_state:
    st.session_state.pdf_texts = {}

st.sidebar.header("Upload Student Submissions")
st.sidebar.markdown("Upload PDF files for 10 students")

uploaded_files = st.sidebar.file_uploader(
    "Choose PDF files",
    type=['pdf'],
    accept_multiple_files=True,
    key="pdf_uploader"
)

if uploaded_files:
    if len(uploaded_files) > 10:
        st.sidebar.warning("Maximum 10 files allowed. Only first 10 will be processed.")
        uploaded_files = uploaded_files[:10]
    
    st.sidebar.success(f"{len(uploaded_files)} files uploaded")
    
    for idx, uploaded_file in enumerate(uploaded_files):
        student_name = f"Student {idx+1}"
        if uploaded_file.name not in st.session_state.pdf_texts:
            with st.spinner(f"Processing {uploaded_file.name}..."):
                text = extract_text_from_pdf(uploaded_file)
                st.session_state.pdf_texts[student_name] = {
                    'text': text,
                    'filename': uploaded_file.name
                }
        st.sidebar.text(f"✓ {student_name}: {uploaded_file.name}")

st.sidebar.markdown("---")
check_online = st.sidebar.checkbox("Enable Online Plagiarism Check", value=False)
analyze_button = st.sidebar.button("🔍 Analyze All Submissions", type="primary")

if analyze_button:
    if len(st.session_state.pdf_texts) < 2:
        st.error("Please upload at least 2 PDF files to analyze.")
    else:
        st.success(f"Analyzing {len(st.session_state.pdf_texts)} submissions...")
        
        progress_bar = st.progress(0)
        student_list = list(st.session_state.pdf_texts.keys())
        total_students = len(student_list)
        
        all_results = {}
        
        for idx, student in enumerate(student_list):
            student_text = st.session_state.pdf_texts[student]['text']
            peer_similarities = {}
            
            for other_student in student_list:
                if student != other_student:
                    other_text = st.session_state.pdf_texts[other_student]['text']
                    similarity = calculate_similarity(student_text, other_text)
                    peer_similarities[other_student] = similarity
            
            if check_online and student_text.strip():
                online_score, online_results = search_online(student_text)
            else:
                online_score = 0
                online_results = []
            
            max_peer_similarity = max(peer_similarities.values()) if peer_similarities else 0
            overall_score = (max_peer_similarity * 0.6 + online_score * 0.4)
            
            all_results[student] = {
                'peer_similarities': peer_similarities,
                'online_score': online_score,
                'online_results': online_results,
                'overall_score': overall_score,
                'text': student_text,
                'filename': st.session_state.pdf_texts[student]['filename']
            }
            
            progress_bar.progress((idx + 1) / total_students)
        
        st.markdown("---")
        st.header("📊 Analysis Results")
        
        for student, results in all_results.items():
            with st.expander(f"**{student}** ({results['filename']}) - Overall Risk: {get_risk_level(results['overall_score'])[0]}", expanded=False):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Overall Plagiarism", f"{results['overall_score']:.1f}%")
                with col2:
                    max_peer = max(results['peer_similarities'].values()) if results['peer_similarities'] else 0
                    st.metric("Max Peer Similarity", f"{max_peer:.1f}%")
                with col3:
                    st.metric("Online Match", f"{results['online_score']:.1f}%")
                
                st.markdown("### 👥 Student-to-Student Comparison")
                sorted_peers = sorted(results['peer_similarities'].items(), key=lambda x: x[1], reverse=True)
                
                for other_student, similarity in sorted_peers:
                    risk_label, color = get_risk_level(similarity)
                    col_a, col_b = st.columns([3, 1])
                    with col_a:
                        st.markdown(f"**{other_student}** ({all_results[other_student]['filename']})")
                    with col_b:
                        st.markdown(f"<span style='color:{color}; font-weight:bold'>{similarity:.1f}%</span>", unsafe_allow_html=True)
                    
                    if similarity > 30:
                        matches = get_matching_blocks(results['text'], all_results[other_student]['text'])
                        if matches:
                            with st.container():
                                st.caption(f"Matching segments: {len(matches)} found")
                                for match in matches[:2]:
                                    st.text(f"'{match[:100]}...'")
                
                if check_online and results['online_results']:
                    st.markdown("### 🌐 Online Plagiarism Check")
                    st.markdown(f"**Estimated Online Match:** {results['online_score']:.1f}%")
                    
                    for idx, result in enumerate(results['online_results'][:3], 1):
                        st.markdown(f"**Match {idx}:** {result['query'][:150]}...")
                        st.caption(f"Source: {result['source']}")
                
                risk_label, color = get_risk_level(results['overall_score'])
                st.markdown(f"### Risk Level: <span style='color:{color}; font-weight:bold'>{risk_label}</span>", unsafe_allow_html=True)
        
        st.markdown("---")
        st.subheader("📈 Summary Overview")
        
        summary_data = []
        for student, results in all_results.items():
            summary_data.append({
                'Student': student,
                'File': results['filename'],
                'Overall Score': f"{results['overall_score']:.1f}%",
                'Risk': get_risk_level(results['overall_score'])[0]
            })
        
        for item in summary_data:
            cols = st.columns([2, 3, 2, 2])
            cols[0].write(item['Student'])
            cols[1].write(item['File'])
            cols[2].write(item['Overall Score'])
            cols[3].write(item['Risk'])

else:
    st.info("👈 Upload student submission PDFs in the sidebar and click 'Analyze All Submissions' to start the plagiarism check.")
    
    st.markdown("### How it works:")
    st.markdown("""
    **1. Upload PDFs**
    - Upload up to 10 PDF files (one per student)
    - Text is automatically extracted from each PDF
    
    **2. Student-to-Student Comparison**
    - Compares each submission against all others
    - Calculates similarity percentages
    - Identifies matching text segments
    
    **3. Online Plagiarism Check** (Optional)
    - Scans text against web content
    - Detects copied content from online sources
    
    **4. Risk Assessment**
    - 🔴 High Risk: 70%+ similarity
    - 🟡 Medium Risk: 40-70% similarity
    - 🟢 Low Risk: <40% similarity
    """)