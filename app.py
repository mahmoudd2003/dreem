# -*- coding: utf-8 -*-
import streamlit as st
import requests
from bs4 import BeautifulSoup
import openai
import pandas as pd
from docx import Document
import json, re, math

st.set_page_config(page_title="Dream Article Diagnostic & SEO Enhancer", page_icon="🌙", layout="wide")

# ===== CONFIG =====
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    st.warning("⚠️ أضف OPENAI_API_KEY في Secrets قبل التشغيل.")
openai.api_key = OPENAI_API_KEY

@st.cache_data
def load_text(path):
    return open(path, "r", encoding="utf-8").read()

def load_json(path):
    return json.loads(load_text(path))

RULES = load_json("rules.json")
PROMPTS = load_json("prompts.json")

# ===== Helpers =====
def chat(model, messages, temperature=0.4):
    resp = openai.chat.completions.create(model=model, messages=messages, temperature=temperature)
    return resp.choices[0].message.content

def fetch_competitor_text(url):
    try:
        r = requests.get(url, timeout=12)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        core = "\n".join([p for p in paragraphs if len(p.split()) > 4])
        return core[:15000]
    except Exception as e:
        return f"خطأ في جلب النص: {e}"

def count_words(txt):
    return len(re.findall(r"\w+", txt, flags=re.UNICODE))

def keyword_density(text, keyword):
    if not keyword:
        return 0.0, 0, count_words(text)
    wc = count_words(text)
    k_count = len(re.findall(re.escape(keyword), text, flags=re.IGNORECASE))
    density = (k_count / max(wc,1)) * 100.0
    return round(density,2), k_count, wc

def rule_engine_precheck(text, focus, lsi_list, length_choice):
    res = {"checks": {}, "metrics": {}}
    wc = count_words(text)
    target = RULES["length_map"][length_choice]
    lo, hi = math.floor(target*0.9), math.ceil(target*1.1)
    res["metrics"]["word_count"] = wc
    res["metrics"]["target_range"] = [lo, hi]
    res["checks"]["length_ok"] = (lo <= wc <= hi)

    dens, kcount, _ = keyword_density(text, focus)
    res["metrics"]["focus_density_pct"] = dens
    res["metrics"]["focus_count"] = kcount
    lo_d, hi_d = RULES["focus_density_min_pct"], RULES["focus_density_max_pct"]
    res["checks"]["focus_density_ok"] = (dens >= lo_d and dens <= hi_d)

    lsi_report, lsi_ok = {}, True
    for k in lsi_list:
        c = len(re.findall(re.escape(k), text, flags=re.IGNORECASE))
        lsi_report[k] = c
        if c > RULES["lsi_max_occurrence"]:
            lsi_ok = False
    res["metrics"]["lsi_counts"] = lsi_report
    res["checks"]["lsi_ok"] = lsi_ok

    banned_hits = []
    for pat in RULES["banned_regex"]:
        if re.search(pat, text):
            banned_hits.append(pat)
    res["metrics"]["banned_hits"] = banned_hits
    res["checks"]["no_banned"] = (len(banned_hits) == 0)

    return res

def safe_json_loads(s):
    try:
        return json.loads(s)
    except Exception:
        m = re.search(r"(\{.*\})", s, flags=re.DOTALL)
        if m:
            try: return json.loads(m.group(1))
            except Exception: return {"raw": s, "error": "failed_json_parse"}
        return {"raw": s, "error": "no_json_found"}

def llm_diagnostic(article, competitors, focus, lsi_list):
    comp_block = "\n\n".join([f"[المنافس {i+1}]\n{c}" for i, c in enumerate(competitors)])
    prompt = PROMPTS["diagnostic"].format(ARTICLE=article, COMPETITORS=comp_block, FOCUS=focus, LSI=", ".join(lsi_list))
    out = chat(PROMPTS["model"], [{"role":"user","content":prompt}], temperature=0.2)
    data = safe_json_loads(out)
    return data

def llm_rewrite(article, competitors, focus, lsi_list, length_choice):
    comp_block = "\n\n".join([f"[المنافس {i+1}]\n{c}" for i, c in enumerate(competitors)])
    length_desc = {
        "قصير (700-900 كلمة)": "حوالي 800 كلمة",
        "متوسط (1000-1300 كلمة)": "حوالي 1200 كلمة",
        "طويل (1500-2000 كلمة)": "حوالي 1700 كلمة"
    }[length_choice]
    prompt = PROMPTS["rewriter"].format(ARTICLE=article, COMPETITORS=comp_block, FOCUS=focus, LSI=", ".join(lsi_list), LENGTH_DESC=length_desc)
    return chat(PROMPTS["model"], [{"role":"user","content":prompt}], temperature=0.6)

def llm_apply_fixes(text, fix_plan_json):
    prompt = PROMPTS["fixer"].format(TEXT=text, FIX_PLAN_JSON=json.dumps(fix_plan_json, ensure_ascii=False, indent=2))
    return chat(PROMPTS["model"], [{"role":"user","content":prompt}], temperature=0.5)

def llm_meta_faq(focus):
    prompt = PROMPTS["meta_faq"].format(FOCUS=focus)
    out = chat(PROMPTS["model"], [{"role":"user","content":prompt}], temperature=0.4)
    return safe_json_loads(out)

def apply_anchors(article, anchors_df):
    new_text = article
    applied, skipped = [], []
    for _, row in anchors_df.iterrows():
        phrase, link = (row.get("النص") or "").strip(), (row.get("الرابط") or "").strip()
        if not phrase or not link: 
            continue
        if phrase in new_text:
            new_text = new_text.replace(phrase, f"[{phrase}]({link})", 1)
            applied.append(phrase)
        else:
            words = phrase.split()
            window = " ".join(words[:6]) if len(words) >= 6 else phrase
            if window in new_text:
                new_text = new_text.replace(window, f"[{window}]({link})", 1)
                applied.append(window + " (جزئي)")
            else:
                skipped.append(phrase)
    return new_text, applied, skipped

def export_docx(text):
    doc = Document()
    for line in text.split("\n"):
        doc.add_paragraph(line)
    doc.save("article.docx")
    with open("article.docx", "rb") as f:
        return f.read()

# ===== UI =====
st.title("🌙 Dream Article Diagnostic & SEO Enhancer (LLM-Guided)")

with st.expander("📥 إدخال المقال والمنافسين", expanded=True):
    article_input = st.text_area("الصق المقال هنا:", height=260, key="article_input")
    focus_kw = st.text_input("🔑 الكلمة المفتاحية الرئيسية (Focus Keyword)", key="focus_kw")
    lsi_raw = st.text_area("📌 الكلمات المرتبطة (افصل بينها بفاصلة)", key="lsi_raw")
    lsi_list = [k.strip() for k in lsi_raw.split(",") if k.strip()]
    length_choice = st.selectbox("📏 طول المقال المطلوب", ["قصير (700-900 كلمة)","متوسط (1000-1300 كلمة)","طويل (1500-2000 كلمة)"])

    c1,c2,c3 = st.columns(3)
    with c1: comp1 = st.text_input("رابط المنافس 1", key="comp1")
    with c2: comp2 = st.text_input("رابط المنافس 2", key="comp2")
    with c3: comp3 = st.text_input("رابط المنافس 3", key="comp3")

competitors_texts = []
for u in [st.session_state.get("comp1"), st.session_state.get("comp2"), st.session_state.get("comp3")]:
    if u: competitors_texts.append(fetch_competitor_text(u))

colA, colB = st.columns(2)
with colA:
    if st.button("🔎 تشخيص مرشد (LLM Diagnostic)"):
        if not article_input or not focus_kw:
            st.warning("أدخل المقال والكلمة المفتاحية أولاً.")
        else:
            with st.spinner("جاري التشخيص..."):
                diag = llm_diagnostic(article_input, competitors_texts, focus_kw, lsi_list)
            st.session_state["diagnostic"] = diag
            st.subheader("📊 نتائج التشخيص")
            st.json(diag)

with colB:
    if st.button("✍️ إعادة كتابة محسّنة"):
        if not article_input or not focus_kw:
            st.warning("أدخل المقال والكلمة المفتاحية أولاً.")
        else:
            with st.spinner("جاري إعادة الكتابة..."):
                rewritten = llm_rewrite(article_input, competitors_texts, focus_kw, lsi_list, length_choice)
            st.session_state["rewritten"] = rewritten
            st.subheader("📝 المقال بعد التحسين (مسودة أولى)")
            st.write(rewritten)

# Pre-check & Post-fix
if "rewritten" in st.session_state:
    st.markdown("---")
    st.subheader("🧪 فحوصات الجودة (Rule Engine)")
    pre = rule_engine_precheck(st.session_state["rewritten"], focus_kw, lsi_list, length_choice)
    st.json(pre)

    if st.button("🧰 تطبيق خطة الإصلاح (إن وُجدت)"):
        diag = st.session_state.get("diagnostic", {})
        fix_plan = {"fixes": diag.get("fixes", [])} if isinstance(diag, dict) else {"fixes": []}
        if not fix_plan["fixes"]:
            st.info("لا توجد Fixes من التشخيص. سيتم عرض النص كما هو.")
            st.session_state["final_text"] = st.session_state["rewritten"]
        else:
            with st.spinner("تطبيق الإصلاحات على الفقرات المحددة..."):
                fixed = llm_apply_fixes(st.session_state["rewritten"], fix_plan)
            st.session_state["final_text"] = fixed
        st.subheader("📄 المقال بعد تطبيق الإصلاحات")
        st.write(st.session_state["final_text"])

# Meta / FAQ
if st.button("🧷 توليد Meta & FAQ & مصادر"):
    if not focus_kw:
        st.warning("أدخل الكلمة المفتاحية أولاً.")
    else:
        with st.spinner("جاري التوليد..."):
            meta = llm_meta_faq(focus_kw)
    st.session_state["meta_block"] = meta
    st.subheader("📌 SEO Outputs")
    st.json(meta)

# Anchors
if "final_text" in st.session_state or "rewritten" in st.session_state:
    st.markdown("---")
    st.subheader("🔗 الروابط الداخلية (Anchors على جُمل)")
    anchors_df = st.data_editor(pd.DataFrame([{"النص":"", "الرابط":""}]), num_rows="dynamic", use_container_width=True, key="anchors_df")
    if st.button("تطبيق الروابط الداخلية"):
        base_text = st.session_state.get("final_text") or st.session_state.get("rewritten", "")
        updated, applied, skipped = apply_anchors(base_text, anchors_df)
        st.session_state["final_with_anchors"] = updated
        st.success(f"تم تطبيق {len(applied)} رابط. المتعذر: {len(skipped)}")
        if skipped: st.write("تعذر تطبيق على:", skipped)
        st.subheader("📄 المقال النهائي مع الروابط الداخلية")
        st.write(updated)

# Downloads
final_output = st.session_state.get("final_with_anchors") or st.session_state.get("final_text") or st.session_state.get("rewritten")
if final_output:
    st.markdown("---")
    st.subheader("💾 تنزيل")
    md_bytes = final_output.encode("utf-8")
    st.download_button("تحميل Markdown", data=md_bytes, file_name="article.md")
    json_bytes = json.dumps({"article": final_output}, ensure_ascii=False, indent=2).encode("utf-8")
    st.download_button("تحميل JSON", data=json_bytes, file_name="article.json")
    docx_bytes = export_docx(final_output)
    st.download_button("تحميل DOCX", data=docx_bytes, file_name="article.docx")
