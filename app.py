import streamlit as st
import requests
from bs4 import BeautifulSoup
import openai
import pandas as pd
from docx import Document
import json

# ----------------- الإعدادات العامة -----------------
st.set_page_config(page_title="Dream SEO Enhancer", page_icon="🌙", layout="wide")
openai.api_key = st.secrets["OPENAI_API_KEY"]

# ----------------- دوال مساعدة -----------------
def fetch_competitor_text(url):
    """جلب نص من رابط منافس"""
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        return "\n".join(paragraphs[:40])
    except Exception as e:
        return f"خطأ في جلب النص: {e}"

def analyze_article(article, competitors, keyword, related_keywords):
    """تحليل المقال الأصلي والمنافسين"""
    competitor_texts = "\n\n".join([f"[المنافس {i+1}]\n{txt}" for i, txt in enumerate(competitors)])
    prompt = f"""
أنت خبير SEO في مقالات تفسير الأحلام.
المطلوب:
1- حلّل المقال التالي واكشف مشاكله حسب Google Helpful Content و E-E-A-T.
2- حلّل النصوص المأخوذة من المنافسين.
3- استخرج لماذا يتصدرون في جوجل (نقاط القوة).
4- استخرج أهم مشاكلهم.
5- اقترح كيف يمكن تحسين المقال الأصلي.
6- افحص كثافة الكلمة المفتاحية "{keyword}" وهل استخدمت بشكل صحيح.
7- راقب الكلمات المرتبطة: {", ".join(related_keywords)}.

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

def rewrite_article(article, competitors, keyword, related_keywords, length_choice):
    """إعادة كتابة المقال"""
    competitor_texts = "\n\n".join([f"[المنافس {i+1}]\n{txt}" for i, txt in enumerate(competitors)])

    length_map = {
        "قصير (700-900 كلمة)": "حوالي 800 كلمة",
        "متوسط (1000-1300 كلمة)": "حوالي 1200 كلمة",
        "طويل (1500-2000 كلمة)": "حوالي 1700 كلمة"
    }

    prompt = f"""
أعد كتابة المقال التالي عن تفسير الأحلام بحيث:
- يستخدم الكلمة المفتاحية الرئيسية: "{keyword}" 3-5 مرات بشكل طبيعي.
- يدمج الكلمات المرتبطة: {", ".join(related_keywords)} في النص بشكل منطقي.
- يكون الطول {length_map[length_choice]}.
- يحتوي على خبرة مباشرة ومنهجية واضحة.
- يضيف أمثلة واقعية وحسّية.
- يقارن بين مدارس التفسير (ابن سيرين، النابلسي، ابن شاهين...).
- يبرز الشفافية (هذا اجتهاد لا حتمي).
- يقدم نصائح عملية للقارئ.
- يتفادى التكرار والحشو.
- منظم بعناوين فرعية واضحة.
- يحتوي على فقرة ختامية تحفيزية.
- يقترح قسم FAQ في النهاية.
- يقترح قسم "📚 المصادر" في النهاية.

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
    """إضافة روابط داخلية على جمل أو عبارات"""
    new_article = article
    for _, row in links_df.iterrows():
        phrase, link = row["النص"], row["الرابط"]
        if phrase and link:
            new_article = new_article.replace(phrase, f"[{phrase}]({link})", 1)
    return new_article

def export_docx(text, filename="article.docx"):
    doc = Document()
    for line in text.split("\n"):
        doc.add_paragraph(line)
    doc.save(filename)
    return filename

# ----------------- واجهة Streamlit -----------------
st.title("🌙 نظام تحسين مقالات تفسير الأحلام (SEO + E-E-A-T)")

with st.expander("📥 إدخال بيانات المقال"):
    article_input = st.text_area("الصق المقال هنا:", height=300)
    keyword = st.text_input("🔑 الكلمة المفتاحية الرئيسية")
    related_keywords = st.text_area("📌 الكلمات المرتبطة (افصل بينها بفاصلة)")
    related_list = [k.strip() for k in related_keywords.split(",") if k.strip()]

    length_choice = st.selectbox(
        "📏 اختر طول المقال المطلوب",
        ["قصير (700-900 كلمة)", "متوسط (1000-1300 كلمة)", "طويل (1500-2000 كلمة)"]
    )

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

# ---- التحليل ----
if st.button("🔎 تحليل المقال والمنافسين"):
    if article_input and keyword:
        with st.spinner("جاري التحليل..."):
            report = analyze_article(article_input, competitors_texts, keyword, related_list)
        st.subheader("📊 تقرير التحليل")
        st.write(report)
    else:
        st.warning("الرجاء إدخال المقال والكلمة المفتاحية.")

# ---- إعادة الكتابة ----
if st.button("✍️ إعادة كتابة المقال"):
    if article_input and keyword:
        with st.spinner("جاري إعادة الكتابة..."):
            rewritten = rewrite_article(article_input, competitors_texts, keyword, related_list, length_choice)
        st.subheader("📝 المقال بعد التحسين")
        st.session_state["rewritten_article"] = rewritten
        st.write(rewritten)

        # عداد الكلمات
        word_count = len(rewritten.split())
        st.info(f"عدد كلمات المقال: {word_count}")
    else:
        st.warning("الرجاء إدخال المقال والكلمة المفتاحية.")

# ---- الروابط الداخلية ----
if "rewritten_article" in st.session_state:
    st.subheader("🔗 أضف الروابط الداخلية (Anchors)")
    links_df = st.data_editor(
        pd.DataFrame([{"النص": "", "الرابط": ""}]),
        num_rows="dynamic",
        use_container_width=True
    )
    if st.button("تطبيق الروابط الداخلية"):
        updated_article = apply_internal_links(st.session_state["rewritten_article"], links_df)
        st.subheader("📄 المقال النهائي مع الروابط الداخلية")
        st.write(updated_article)
        st.session_state["final_article"] = updated_article

# ---- التصدير ----
if "final_article" in st.session_state:
    st.subheader("💾 تنزيل المقال")
    final_text = st.session_state["final_article"]

    st.download_button("تحميل DOCX", data=final_text.encode("utf-8"), file_name="article.docx")
    st.download_button("تحميل Markdown", data=final_text.encode("utf-8"), file_name="article.md")
    json_data = json.dumps({"article": final_text}, ensure_ascii=False, indent=2)
    st.download_button("تحميل JSON", data=json_data.encode("utf-8"), file_name="article.json")
