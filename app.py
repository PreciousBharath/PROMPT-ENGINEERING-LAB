"""PromptCraft Lab - Build, score and compare prompts with proven techniques.
Run:  streamlit run app.py
"""
import os

import plotly.graph_objects as go
import requests
import streamlit as st

from prompt_lab import TECHNIQUES, PromptSpec, analyse, build_prompt

st.set_page_config(page_title="PromptCraft Lab", page_icon="✨", layout="wide")
st.markdown("<h1 style='margin-bottom:0'>✨ PromptCraft Lab</h1>"
            "<p style='color:#888'>Prompt engineering workbench — build with proven techniques, score quality, compare A/B, run on any LLM</p>",
            unsafe_allow_html=True)

with st.sidebar:
    st.header("📘 Techniques")
    tech = st.radio("Prompting technique", list(TECHNIQUES), index=1)
    st.info(TECHNIQUES[tech])
    st.header("🤖 Run on LLM (optional)")
    key = st.text_input("OpenAI-compatible API key", type="password")
    base = st.text_input("Base URL", "https://api.openai.com/v1")
    model = st.text_input("Model", "gpt-4o-mini")
    price = st.number_input("Input price ($ per 1M tokens)", 0.0, 50.0, 0.15)


POLAR = dict(bgcolor="rgba(0,0,0,0)", radialaxis=dict(range=[0, 10], gridcolor="#444", linecolor="#444"),
             angularaxis=dict(gridcolor="#444", linecolor="#555"))


def radar(scores, name, color):
    cats = list(scores) + [list(scores)[0]]
    vals = list(scores.values()) + [list(scores.values())[0]]
    return go.Scatterpolar(r=vals, theta=cats, fill="toself", name=name, line=dict(color=color), opacity=.7)


tab1, tab2 = st.tabs(["🛠️ Prompt builder", "⚖️ A/B compare"])
with tab1:
    c1, c2 = st.columns([1, 1])
    with c1:
        role = st.text_input("Role / persona", "a senior customer-experience analyst")
        task = st.text_area("Task", "Classify the sentiment of each customer review and extract the main complaint.", height=70)
        context = st.text_area("Context", "Reviews come from an Indian e-commerce app. Results feed a weekly product-quality dashboard for managers.", height=70)
        constraints = st.text_area("Constraints (one per line)", "Use only: Positive, Negative, Neutral\nKeep each complaint under 10 words\nDo not invent details not present in the review", height=90)
        fmt = st.text_input("Output format", "A markdown table with columns: Review #, Sentiment, Main complaint")
        examples = []
        if tech == "Few-shot":
            e1 = st.text_input("Example input", "Delivery took 9 days and the box was damaged.")
            e2 = st.text_input("Example output", "| 1 | Negative | Late delivery, damaged packaging |")
            examples = [(e1, e2)]
    spec = PromptSpec(tech, role, task, context, constraints.splitlines(), fmt, examples)
    prompt = build_prompt(spec)
    res = analyse(prompt)
    with c2:
        st.markdown("**🧾 Generated prompt**")
        st.code(prompt, language="markdown")
        m = st.columns(4)
        m[0].metric("Quality / 100", res["overall"])
        m[1].metric("Tokens (est.)", res["tokens"])
        m[2].metric("Words", res["words"])
        m[3].metric("$ / 1k calls", f"{res['tokens'] * 1000 * price / 1e6:.3f}")

    c1, c2 = st.columns([1, 1])
    with c1:
        fig = go.Figure(radar(res["scores"], "Prompt", "#8E2DE2"))
        fig.update_layout(polar=POLAR, height=330, title="Prompt quality radar",
                          margin=dict(t=50, b=10), showlegend=False)
        st.plotly_chart(fig, width="stretch")
    with c2:
        st.markdown("**💡 Improvement tips**")
        if res["tips"]:
            for t in res["tips"]:
                st.warning(t)
        else:
            st.success("Excellent — this prompt covers role, task, context, constraints, format and examples.")
        if st.button("▶️ Run prompt on LLM", disabled=not key):
            url = base.rstrip("/") + "/chat/completions"
            r = requests.post(url, headers={"Authorization": f"Bearer {key}"}, timeout=60,
                              json={"model": model, "messages": [{"role": "user", "content": prompt}]})
            st.markdown(r.json()["choices"][0]["message"]["content"] if r.ok else f"Error {r.status_code}: {r.text[:300]}")
        elif not key:
            st.caption("Add an API key in the sidebar to execute prompts.")

with tab2:
    c1, c2 = st.columns(2)
    a = c1.text_area("Prompt A (naive)", "Tell me something about these reviews.", height=200)
    b = c2.text_area("Prompt B (engineered)", prompt, height=200)
    ra, rb = analyse(a), analyse(b)
    fig = go.Figure([radar(ra["scores"], f"A · {ra['overall']}/100", "#FF416C"), radar(rb["scores"], f"B · {rb['overall']}/100", "#00C9FF")])
    fig.update_layout(polar=POLAR, height=380, title="A vs B quality profile")
    st.plotly_chart(fig, width="stretch")
    st.metric("Improvement", f"+{rb['overall'] - ra['overall']} points", delta=f"{rb['overall'] - ra['overall']}")
