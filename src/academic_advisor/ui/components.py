"""Small presentation helpers for the Chat and Knowledge Base screens."""

from typing import Any

import streamlit as st

from academic_advisor.domain.documents import SourceReference

STYLE = """
<style>
.stApp { background: #f7f7f3; }
[data-testid="stSidebar"] { background: #e7efe8; }
.block-container { max-width: 1120px; padding-top: 2.4rem; }
.eyebrow { color: #2d684e; font-weight: 700; letter-spacing: .16em;
           font-size: .74rem; text-transform: uppercase; }
.intro { color: #52605a; font-size: 1.08rem; max-width: 780px; }
[data-testid="stChatMessage"] { border: 1px solid #dfe6dd; border-radius: 14px; }
.source-card { background: #fff; border: 1px solid #dde5dc; border-radius: 10px;
               padding: .75rem 1rem; margin: .45rem 0; }
.source-label { color: #2d684e; font-weight: 700; font-size: .86rem; }
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
