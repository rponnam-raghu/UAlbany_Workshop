"""Small presentation helpers for the Chat and Knowledge Base screens."""

from typing import Any

import streamlit as st

from academic_advisor.domain.documents import SourceReference

STYLE = """
<style>
.stApp, [data-testid="stHeader"], [data-testid="stBottom"] {
    background: #FFFCF7; color: #171717;
}
[data-testid="stSidebar"] { background: #F5F0E8; }
.block-container { max-width: 1120px; padding-top: 2.4rem; }
.eyebrow { color: #525252; font-weight: 700; letter-spacing: .16em;
           font-size: .74rem; text-transform: uppercase; }
.workshop-heading { color: #171717; font-size: clamp(1.2rem, 2vw, 1.5rem);
                    font-weight: 600; line-height: 1.35; margin-bottom: .15rem; }
.workshop-subtitle { color: #525252; font-size: clamp(1.05rem, 1.5vw, 1.2rem);
                     font-weight: 500; line-height: 1.5; margin: 0 0 .35rem; }
.intro { color: #525252; font-size: 1.08rem; max-width: 780px; }
[data-testid="stCaptionContainer"], input::placeholder, textarea::placeholder {
    color: #525252; opacity: 1;
}
[data-testid="stChatMessage"] {
    background: #FFFFFF; border: 1px solid #DED8CE; border-radius: 14px;
}
[data-testid="stVerticalBlockBorderWrapper"] > div,
[data-testid="stForm"], [data-testid="stExpander"] details {
    background: #FFFFFF; border-color: #DED8CE;
}
[data-testid="stChatInput"], [data-baseweb="input"], [data-baseweb="textarea"],
[data-baseweb="select"] > div, [data-testid="stFileUploaderDropzone"] {
    background: #FFFFFF; border-color: #DED8CE;
}
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"] {
    background: #171717; color: #FFFFFF; border-color: #171717;
}
[data-testid="stBaseButton-primary"]:hover:not(:disabled),
[data-testid="stBaseButton-primaryFormSubmit"]:hover:not(:disabled) {
    background: #EEE7DC; color: #171717; border-color: #171717;
}
[data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-secondaryFormSubmit"] {
    background: #FFFFFF; color: #171717; border-color: #DED8CE;
}
[data-testid="stBaseButton-secondary"]:hover:not(:disabled),
[data-testid="stBaseButton-secondaryFormSubmit"]:hover:not(:disabled),
[data-testid="stExpander"] summary:hover, [role="option"]:hover {
    background: #EEE7DC; color: #171717;
}
.source-card { background: #FFFFFF; color: #171717; border: 1px solid #DED8CE;
               border-radius: 10px; padding: .75rem 1rem; margin: .45rem 0; }
.source-label { color: #171717; font-weight: 700; font-size: .86rem; }
</style>
"""


def show_trace(trace: list[dict[str, Any]]) -> None:
    with st.expander("How this answer was produced"):
        for index, item in enumerate(trace, 1):
            result = item.get("result", {})
            st.markdown(f"**{index}. {item.get('tool', 'step')}** · {result.get('status', 'ok')}")
            st.json({"arguments": item.get("arguments", {}), "result": result})


def show_sources(sources: list[SourceReference]) -> None:
    if not sources:
        return
    with st.expander(f"Sources ({len(sources)})"):
        for source in sources:
            location = f" · page {source.page}" if source.page else f" · {source.location}"
            st.markdown(
                f'<div class="source-card"><div class="source-label">[{source.citation}] '
                f'{source.filename}{location}</div><div>{source.text}</div></div>',
                unsafe_allow_html=True,
            )
