import streamlit as st
import requests
from bs4 import BeautifulSoup
import openai
import pandas as pd
from docx import Document
import json

# --------------- الإعدادات العامة -----------------
st.set_page_config(page_title="Dream Article Enhancer", page_icon="🌙", layout="wide")
openai.api_key = st.secrets["OPENAI_API_KEY"]

# --------------- دوال مساعدة -----------------
def fetch_competitor_text(url):
    """جلب نص من رابط منافس"""
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        return "\n".join(paragraphs[:40])
    except Exception as e:
        return f"خطأ في جلب النص: {e}"

def analyze_article(article, competitors):
    competitor_texts = "\n\n".join([f"[المنافس {i+1}]\n{txt}" for i, txt in enumerate(competitors)])
    prompt = f"""
أنت خبير في SEO و E-E-A-T لمقالات تفسير الأحلام.
المطلوب: 
1- حلّل المقال التالي واكشف مشاكله حسب معايير Google Helpful Content وE-E-A-T.
2- حلّل النصوص المأخوذة من المنافسين الثلاثة.
3- استخرج لماذا يتصدرون في جوجل (نقاط القوة).
4- استخرج أهم مشاكلهم.
5- اقترح كيف يمكن تحسين المقال الأصلي ليتفوق عليهم.

--- المقال الأصلي ---
{article}

--- المنافسون ---
{competitor_texts}
"""
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
    )
    return response.choices[0].message.content

def rewrite_article(article, competitors):
    competitor_texts = "\n\n".join([f"[المنافس {i+1}]\n{txt}" for i, txt in enumerate(competitors)])
    prompt = f"""
أعد كتابة المقال التالي عن تفسير الأحلام ليكون:
- بعيد عن الأسلوب القالبية والافتتاحيات المكررة.
- يحتوي على خبرة مباشرة ومنهجية واضحة.
- يضيف أمثلة واقعية وحسّية.
- يقارن بين مدارس التفسير (ابن سيرين، النابلسي، ابن شاهين...).
- يبرز الشفافية (هذا اجتهاد لا حتمي).
- يقدم نصائح عملية للرائي.
- يتفادى التكرار والحشو.
- منظم بعناوين فرعية واضحة.
- يحتوي على فقرة ختامية تحفيزية.

--- المقال الأصلي ---
{article}

--- المنافسون (للاستفادة من نقاط قوتهم) ---
{competitor_texts}
"""
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.6,
    )
    return response.choices[0].message.content

def apply_internal_links(article, links_df):
    new_article = article
    for _, row in links_df.iterrows():
        word, link = row["الكلمة"], row["الرابط"]
        if word in new_article:
            new_article = new_article.replace(word, f"[{word}]({link})", 1)
    return new_article

def export_docx(text, filename="article.docx"):
    doc = Document()
    doc.add_paragraph(text)
    doc.save(filename)
    return filename

# --------------- واجهة Streamlit -----------------
st.title("🌙 نظام تحسين مقالات تفسير الأحلام")

with st.expander("📥 أدخل بيانات المقال"):
    article_input = st.text_area("الصق المقال هنا:", height=300)

    col1, col2, col3 = st.columns(3)
    with col1:
        comp1 = st.text_input("رابط المنافس 1")
    with col2:
        comp2 = st.text_input("رابط المنافس 2")
    with col3:
        comp3 = st.text_input("رابط المنافس 3")

competitors_texts = []
if comp1: competitors_texts.append(fetch_competitor_text(comp1))
if comp2: competitors_texts.append(fetch_competitor_text(comp2))
if comp3: competitors_texts.append(fetch_competitor_text(comp3))

if st.button("🔎 تحليل المقال والمنافسين"):
    if article_input and competitors_texts:
        with st.spinner("جاري التحليل..."):
            report = analyze_article(article_input, competitors_texts)
        st.subheader("📊 تقرير التحليل")
        st.write(report)
    else:
        st.warning("الرجاء إدخال المقال وروابط المنافسين.")

if st.button("✍️ إعادة كتابة المقال"):
    if article_input:
        with st.spinner("جاري إعادة الكتابة..."):
            rewritten = rewrite_article(article_input, competitors_texts)
        st.subheader("📝 المقال بعد التحسين")
        st.session_state["rewritten_article"] = rewritten
        st.write(rewritten)
    else:
        st.warning("الرجاء إدخال المقال أولاً.")

if "rewritten_article" in st.session_state:
    st.subheader("🔗 أضف الروابط الداخلية")
    links_df = st.data_editor(
        pd.DataFrame([{"الكلمة": "", "الرابط": ""}]),
        num_rows="dynamic",
        use_container_width=True
    )
    if st.button("تطبيق الروابط الداخلية"):
        updated_article = apply_internal_links(st.session_state["rewritten_article"], links_df)
        st.subheader("📄 المقال النهائي مع الروابط الداخلية")
        st.write(updated_article)
        st.session_state["final_article"] = updated_article

if "final_article" in st.session_state:
    st.subheader("💾 تنزيل المقال")
    final_text = st.session_state["final_article"]
    st.download_button("تحميل DOCX", data=final_text.encode("utf-8"), file_name="article.docx")
    st.download_button("تحميل Markdown", data=final_text.encode("utf-8"), file_name="article.md")
    json_data = json.dumps({"article": final_text}, ensure_ascii=False, indent=2)
    st.download_button("تحميل JSON", data=json_data.encode("utf-8"), file_name="article.json")
