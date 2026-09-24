"""Streamlit chat, fictional student profiles, and advisor knowledge."""

from collections.abc import Callable
from functools import partial
from typing import Any
from uuid import UUID

import streamlit as st

from academic_advisor.agent.chat import ChatService
from academic_advisor.agent.errors import ProviderError
from academic_advisor.agent.providers import (
    NoProviderAvailable,
    ProviderClient,
    config_token,
    create_client,
    select_provider,
)
from academic_advisor.config import Settings
from academic_advisor.domain.documents import Answer, Document, Message, Upload
from academic_advisor.domain.profiles import SAM_ID
from academic_advisor.knowledge.extraction import UploadError
from academic_advisor.knowledge.service import DocumentService
from academic_advisor.profiles.service import ProfileService
from academic_advisor.storage.knowledge import KnowledgeStore
from academic_advisor.storage.postgres import Database, DatabaseError
from academic_advisor.storage.profiles import ProfileStore
from academic_advisor.ui.components import STYLE, show_sources, show_trace
from academic_advisor.ui.profiles import profile_screen, show_profile
from academic_advisor.ui.prompts import prompt_editor

SUPPORTED = ["pdf", "txt", "docx", "md", "markdown"]


def _services(settings: Settings) -> KnowledgeStore:
    database = Database(settings)
    database.migrate()
    signature = settings.signature(_active(settings))
    return KnowledgeStore(database, signature)


def _active(settings: Settings) -> str:
    return str(st.session_state.get("active_provider", settings.default_provider()))


def _client(settings: Settings) -> ProviderClient:
    return create_client(settings, _active(settings))


def _provider_changed() -> None:
    st.session_state.active_provider = st.session_state.preferred_provider
    for key in ("provider_checked", "provider_notice", "provider_failed", "provider_error", "pending_question", "pending_chat"):
        st.session_state.pop(key, None)


def _ensure_provider(settings: Settings, *, exclude: set[str] | None = None, rerun: bool = True) -> None:
    active = _active(settings)
    token = (config_token(settings), active)
    if not exclude and st.session_state.get("provider_checked") == token:
        return
    fingerprint = config_token(settings)
    if st.session_state.get("provider_config") != fingerprint:
        st.session_state.provider_failed = set()
        st.session_state.provider_config = fingerprint
    excluded = set(st.session_state.get("provider_failed", set())) | (exclude or set())
    try:
        selected, notice, failed = select_provider(settings, active, exclude=excluded)
    except NoProviderAvailable as error:
        st.session_state.pop("provider_checked", None)
        st.session_state.provider_error = str(error)
        raise
    st.session_state.pop("provider_error", None)
    st.session_state.provider_failed = failed
    st.session_state.active_provider = selected
    st.session_state.provider_checked = (config_token(settings), selected)
    if selected != active:
        reason = notice or st.session_state.get("provider_notice", "The preferred provider failed.")
        st.session_state.provider_notice = f"Using {'OpenAI' if selected == 'openai' else 'Gemini'} for chat and embeddings. " + reason
        if rerun:
            st.rerun()


def _run_document_action(settings: Settings, store: KnowledgeStore, operation: Callable[[DocumentService], str | None]) -> str | None:
    """Retry one failed embedding operation with a complete alternate provider."""
    attempted: set[str] = set()
    for _ in range(2):
        _ensure_provider(settings, exclude=attempted or None, rerun=False)
        provider = _active(settings)
        attempted.add(provider)
        active_store = KnowledgeStore(store.database, settings.signature(provider))
        try:
            service = _document_service(settings, active_store)
            return operation(service)
        except ProviderError as error:
            st.session_state.provider_notice = str(error)
            st.session_state.pop("provider_checked", None)
            st.session_state.provider_failed = set(st.session_state.get("provider_failed", set())) | {provider}
            if len(attempted) == 2:
                raise
    raise ProviderError("No working provider is available.")


def _index_missing(settings: Settings, store: KnowledgeStore, *, resume: bool = False) -> bool:
    missing = store.missing_documents()
    if not missing:
        return True
    provider = _active(settings)
    st.warning(f"{len(missing)} document(s) need indexing for {provider.title()} before chatting.")
    label = "Index documents and continue" if resume else f"Index existing documents for {provider.title()}"
    if st.button(label, key=f"index_missing_{provider}"):
        try:
            _ensure_provider(settings)
            progress = st.progress(0, text="Indexing documents…")
            for index, document in enumerate(missing):
                try:
                    _run_document_action(settings, store, partial(DocumentService.index_document, document=document))
                    if _active(settings) != provider:
                        st.rerun()
                except ProviderError as error:
                    st.error(f"{document.filename}: {error}")
                    break
                except (ValueError, DatabaseError) as error:
                    st.error(f"{document.filename}: {error}")
                    continue
                progress.progress((index + 1) / len(missing), text=f"Indexed {document.filename}")
            if not store.missing_documents():
                st.rerun()
        except (ValueError, ProviderError, DatabaseError) as error:
            st.error(str(error))
    return False


def _profile_service(settings: Settings) -> ProfileService:
    return ProfileService(ProfileStore(Database(settings)))


def _document_service(settings: Settings, store: KnowledgeStore) -> DocumentService:
    return DocumentService(store, _client(settings), settings.for_provider(_active(settings)))


def _upload_bytes(uploaded: Any) -> bytes:
    return bytes(uploaded.getvalue())


def _show_answer(answer: Answer) -> None:
    st.markdown(answer.text)
    show_sources(answer.sources)
    if answer.profile_snapshot:
        with st.expander("Student profile used"):
            show_profile(answer.profile_snapshot)
    if answer.trace:
        show_trace(answer.trace)


def _profile_changed() -> None:
    st.session_state.pop("pending_question", None)
    st.session_state.pop("pending_chat", None)
    st.session_state.pop("profile_edit", None)
    st.session_state.pop("profile_saved", None)


def chat_screen(settings: Settings, store: KnowledgeStore, profiles: ProfileService | None = None, profile_id: UUID | None = None) -> None:
    st.markdown('<div class="eyebrow">Intro to AI Agents and Building Chatbots with LLMs</div>', unsafe_allow_html=True)
    st.title("Student Helpdesk")
    st.markdown(
        '<p class="intro">Ask a natural-language question using your selected profile and advisor documents. '
        "This fictional workshop assistant advises; it never approves enrollment or changes records.</p>",
        unsafe_allow_html=True,
    )
    st.info("Fictional workshop information only — not official University at Albany policy or academic advice.")
    prompt_editor()
    if profile_id is not None:
        if profiles is None:
            st.error("Student profiles are unavailable. Please select General chat.")
            return
        try:
            show_profile(profiles.get(profile_id), compact=True)
        except (ValueError, DatabaseError) as error:
            st.error(str(error))
            return
    else:
        st.caption("General chat · Select a student for personalized guidance.")
    if "chat_histories" not in st.session_state:
        # The previous unpersonalized conversation belongs only to general chat.
        st.session_state.chat_histories = {"general": st.session_state.pop("chat_history", [])}
    owner = str(profile_id) if profile_id else "general"
    provider = _active(settings)
    # Existing Gemini histories retain their original keys.
    history_key = owner if provider == "gemini" else f"openai:{owner}"
    messages: list[Message] = st.session_state.chat_histories.setdefault(history_key, [])
    for message in messages:
        with st.chat_message(message.role):
            if message.role == "assistant" and message.answer:
                _show_answer(message.answer)
            else:
                st.markdown(message.text)
    with st.expander("Example questions"):
        st.caption("Examples are optional. Type any question in the message box below.")
        examples = [
            "Based on my courses, what should I consider taking next?",
            "What grades are in my saved profile?",
            "When does the spring intake close?",
            "What documents do I need for the spring intake?",
            "How many days do I have until the deadline?",
            "What does the advising FAQ say about changing a course plan?",
        ]
        for number, example in enumerate(examples):
            if st.button(example, key=f"example_{owner}_{number}", use_container_width=True):
                st.session_state.pending_question = (owner, example)
    typed = st.chat_input("Ask your own question…", key=f"chat_input_{provider}_{owner}")
    pending = st.session_state.pop("pending_question", None)
    question = typed or (pending[1] if isinstance(pending, tuple) and pending[0] == owner else None)
    if question:
        st.session_state.pending_chat = {"owner": owner, "question": question, "tried": []}
    request = st.session_state.get("pending_chat")
    if not request or request["owner"] != owner:
        if not messages:
            st.caption("Ask about your profile or the advisor's documents. Missing information will be explained.")
        return
    question = request["question"]
    st.caption(f"Pending question: {question}")
    if st.button("Cancel pending question"):
        st.session_state.pop("pending_chat", None)
        st.rerun()
    try:
        with st.spinner("Checking provider and reading current knowledge…"):
            _ensure_provider(settings)
            if not _index_missing(settings, store, resume=True):
                return
            client = _client(settings)
            knowledge = DocumentService(store, client, settings.for_provider(provider))
            answer = ChatService(knowledge, client, settings.max_tool_calls, profiles=profiles).ask(
                question, list(messages), profile_id,
                chat_instructions=st.session_state.chat_prompt_active,
                prompt_revision=st.session_state.chat_prompt_revision,
            )
    except NoProviderAvailable as error:
        answer = Answer(f"I couldn't complete that request: {error}")
    except ProviderError as error:
        request["tried"].append(provider)
        st.session_state.pop("provider_checked", None)
        if len(set(request["tried"])) < 2:
            try:
                st.session_state.provider_notice = str(error)
                _ensure_provider(settings, exclude=set(request["tried"]))
            except (ProviderError, ValueError) as fallback_error:
                error = ProviderError(f"{error} {fallback_error}")
        answer = Answer(f"I couldn't complete that request: {error}")
    except (ValueError, DatabaseError) as error:
        answer = Answer(f"I couldn't complete that request: {error}")
    messages.append(Message("user", question, profile_id=profile_id))
    messages.append(Message("assistant", answer.text, answer, profile_id))
    st.session_state.pop("pending_chat", None)
    st.rerun()


def _preview(uploaded: Any) -> Upload | None:
    try:
        return DocumentService.preview(uploaded.name, _upload_bytes(uploaded))
    except UploadError as error:
        st.error(f"{uploaded.name}: {error}")
        return None


def _index_upload(settings: Settings, store: KnowledgeStore, upload: Upload, label: str, replace: Document | None = None) -> None:
    try:
        progress = st.progress(0, text=f"Indexing {label}…")
        def update(value: float) -> None:
            progress.progress(value, text=f"Indexing {label}… {value:.0%}")

        message = _run_document_action(settings, store, lambda service: service.add(upload, replace=replace, progress=update))
        progress.progress(1.0, text="Indexing complete")
        st.success(message)
    except (ValueError, ProviderError, DatabaseError) as error:
        st.session_state.document_error = f"{label}: {error}"
        st.error(st.session_state.document_error)


def knowledge_screen(settings: Settings, store: KnowledgeStore) -> None:
    st.markdown('<div class="eyebrow">Advisor workspace</div>', unsafe_allow_html=True)
    st.title("Knowledge Base")
    st.write("Upload the information students should be able to ask about. Files are stored locally in PostgreSQL and indexed only when you add or replace them.")
    st.caption("Supported: PDF, TXT, Word .docx, and Markdown. Maximum 10 MB per file. Google Docs can be exported as .docx or PDF before upload.")
    st.info("Documents are reference material. Instructions inside an upload cannot grant permissions or change records.")

    if error := st.session_state.pop("document_error", None):
        st.error(error)
    _index_missing(settings, store)
    if st.button("Load fictional sample pack", type="secondary"):
        try:
            _ensure_provider(settings, rerun=False)
        except (ValueError, ProviderError) as error:
            st.error(str(error))
            return
        sample_dir = settings.sample_dir
        if not sample_dir.exists():
            st.error("The fictional sample pack is missing from data/samples.")
        else:
            loaded, errors = 0, 0
            for path in sorted(sample_dir.iterdir()):
                if path.suffix.lower().lstrip(".") not in SUPPORTED:
                    continue
                try:
                    upload = DocumentService.preview(path.name, path.read_bytes())
                    _run_document_action(settings, store, partial(DocumentService.add, upload=upload))
                    loaded += 1
                except (OSError, UploadError, ValueError, ProviderError, DatabaseError) as error:
                    errors += 1
                    st.error(f"{path.name}: {error}")
            if loaded:
                st.success(f"Loaded {loaded} fictional sample document(s).")
            if not errors:
                st.rerun()

    st.subheader("Add documents")
    uploads = st.file_uploader("Choose one or more files", type=SUPPORTED, accept_multiple_files=True, key="new_uploads")
    previews: list[Upload] = []
    if uploads:
        for uploaded in uploads:
            with st.expander(f"Preview · {uploaded.name}", expanded=True):
                preview = _preview(uploaded)
                if preview:
                    previews.append(preview)
                    st.caption(f"{preview.media_type} · {len(preview.original):,} bytes · {len(preview.sections)} source sections")
                    st.text_area("Extracted text", "\n\n".join(f"[{s.location}]\n{s.text}" for s in preview.sections), height=180, key=f"preview_{preview.content_hash}")
        if previews and st.button("Add selected documents to knowledge base", type="primary"):
            for upload in previews:
                _index_upload(settings, store, upload, upload.filename)
            st.rerun()

    st.subheader("Indexed documents")
    try:
        documents = store.documents()
    except DatabaseError as error:
        st.error(str(error))
        return
    if not documents:
        st.caption("No documents are indexed yet. Add your own files or load the fictional sample pack.")
    for document in documents:
        with st.container(border=True):
            st.markdown(f"**{document.filename}**")
            st.caption(f"{document.media_type} · {document.size_bytes:,} bytes · {document.passage_count} passages · indexed {document.indexed_at:%Y-%m-%d %H:%M UTC}")
            replacement = st.file_uploader("Choose a replacement", type=SUPPORTED, key=f"replace_file_{document.id}")
            left, right = st.columns(2)
            with left:
                if replacement and st.button("Replace document", key=f"replace_{document.id}"):
                    preview = _preview(replacement)
                    if preview:
                        _index_upload(settings, store, preview, preview.filename, document)
                        st.rerun()
            with right:
                if st.button("Remove", key=f"remove_{document.id}"):
                    try:
                        store.remove(document)
                        st.success("Document removed.")
                        st.rerun()
                    except (ValueError, DatabaseError) as error:
                        st.error(str(error))


def main() -> None:
    st.set_page_config(page_title="Student Helpdesk · Fictional Workshop", page_icon="💬", layout="wide")
    st.markdown(STYLE, unsafe_allow_html=True)
    settings = Settings()
    if "preferred_provider" not in st.session_state:
        st.session_state.preferred_provider = settings.default_provider()
        st.session_state.active_provider = settings.default_provider()
    try:
        store = _services(settings)
        profiles = _profile_service(settings)
        students = profiles.list()
    except DatabaseError as error:
        st.error(str(error))
        st.stop()
    with st.sidebar:
        st.markdown("### Student Helpdesk")
        st.caption("CODING CLUB WORKSHOP · FICTIONAL DATA")
        labels = {str(profile.id): profile.name for profile in students}
        labels["general"] = "General chat (no profile)"
        if "selected_profile" not in st.session_state:
            st.session_state.selected_profile = str(SAM_ID) if str(SAM_ID) in labels else "general"
        if st.session_state.selected_profile not in labels:
            labels[st.session_state.selected_profile] = "Unavailable student — select another"
        selected = st.selectbox("Student", list(labels), format_func=lambda value: labels[value], key="selected_profile", on_change=_profile_changed)
        profile_id = UUID(selected) if selected != "general" else None
        st.selectbox("Preferred AI provider", ["gemini", "openai"], format_func=lambda value: "Gemini" if value == "gemini" else "OpenAI", key="preferred_provider", on_change=_provider_changed)
        active = _active(settings)
        provider_name = "Gemini" if active == "gemini" else "OpenAI"
        verified = st.session_state.get("provider_checked") == (config_token(settings), active)
        if verified:
            st.caption(f"Active provider: {provider_name}")
        else:
            st.caption(f"Selected provider: {provider_name} (not verified)")
        if not settings.configured(active):
            key_name = "GEMINI_API_KEY" if active == "gemini" else "OPENAI_API_KEY"
            st.warning(f"{key_name} is not configured in the running app. Save it in the project .env file, then recreate the app container.")
            st.code("docker compose up -d --force-recreate --no-deps app", language="bash")
        if st.session_state.get("provider_error"):
            st.error("No provider has passed both chat and embedding checks. Check configuration, then retry.")
        if st.session_state.get("provider_notice"):
            st.info(st.session_state.provider_notice)
        if st.button("Retry preferred provider"):
            _provider_changed()
            st.rerun()
        page = st.radio("Workspace", ["Chat", "Student Profile", "Knowledge Base"], label_visibility="collapsed")
        st.divider()
        st.caption(f"Indexed documents: {len(store.documents())}")
        st.caption(f"Model: {settings.openai_model if active == 'openai' else settings.gemini_model}")
        st.caption("Local workshop workflow; no authenticated student or advisor roles.")
    if page == "Chat":
        chat_screen(settings, store, profiles, profile_id)
    elif page == "Student Profile":
        profile_screen(profiles, profile_id)
    else:
        knowledge_screen(settings, store)
