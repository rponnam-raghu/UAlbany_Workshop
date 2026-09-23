"""Profile presentation and explicit form editing for the local fictional demo."""

from typing import Any
from uuid import UUID, uuid4

import streamlit as st

from academic_advisor.domain.profiles import GRADES, AcademicTerm, StudentProfile
from academic_advisor.profiles.service import ProfileService
from academic_advisor.storage.postgres import DatabaseError


def show_profile(profile: StudentProfile, *, compact: bool = False) -> None:
    st.write(f"**{profile.name}** · {profile.program} · {profile.status.title()}")
    st.caption(f"Intake: {profile.intake or 'Unknown'} · Current academic term: {profile.current_term or 'Unknown'}")
    if compact:
        return
    st.markdown("**Completed course records**")
    if profile.completed:
        st.dataframe([{"Course": course.code, "Grade": course.grade or "Unknown"} for course in profile.completed], hide_index=True, width="stretch")
    else:
        st.caption("No completed courses recorded.")
    st.markdown("**Courses in progress**")
    if profile.in_progress:
        st.dataframe([{"Course": course.code} for course in profile.in_progress], hide_index=True, width="stretch")
    else:
        st.caption("No courses in progress recorded.")
    st.markdown("**Interests or goals**")
    st.write(profile.goals or "Not provided.")
    st.caption(f"Profile revision {profile.revision} · updated {profile.updated_at:%Y-%m-%d %H:%M UTC}")


def _course_rows(rows: list[dict[str, Any]], *, graded: bool) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        code = str(row.get("Course") or "").strip()
        grade = (row.get("Grade") or None) if graded else None
        if not code and not grade:
            continue
        result.append({"code": code, "grade": grade})
    return result


def _edit(service: ProfileService, snapshot: StudentProfile, token: str) -> None:
    prefix = f"profile_edit_{token}"
    with st.form(prefix):
        name = st.text_input("Name", value=snapshot.name, max_chars=100)
        program = st.text_input("Program", value=snapshot.program, max_chars=200)
        intake = st.text_input("Intake / start term", value=str(snapshot.intake) if snapshot.intake else "", help="For example, Fall 2025. Leave blank if unknown.")
        current = st.text_input("Current academic term", value=str(snapshot.current_term) if snapshot.current_term else "", help="This can differ from the intake term.")
        status = st.selectbox("Status", ["applicant", "enrolled"], index=0 if snapshot.status == "applicant" else 1)
        st.caption("Edit course rows below. Blank grades remain unknown; in-progress courses have no final grade.")
        completed = st.data_editor(
            [{"Course": c.code, "Grade": c.grade or ""} for c in snapshot.completed] or [{"Course": "", "Grade": ""}],
            key=f"{prefix}_completed", num_rows="dynamic", hide_index=True,
            column_config={"Course": st.column_config.TextColumn("Course"), "Grade": st.column_config.SelectboxColumn("Grade", options=["", *GRADES])},
        )
        in_progress = st.data_editor(
            [{"Course": c.code} for c in snapshot.in_progress] or [{"Course": ""}],
            key=f"{prefix}_in_progress", num_rows="dynamic", hide_index=True,
            column_config={"Course": st.column_config.TextColumn("Course")},
        )
        goals = st.text_area("Interests or goals", value=snapshot.goals, max_chars=2000)
        save = st.form_submit_button("Save", type="primary")
        cancel = st.form_submit_button("Cancel")
    if cancel:
        st.session_state.pop("profile_edit", None)
        st.rerun()
    if save:
        try:
            intake_term, current_term = AcademicTerm.parse(intake), AcademicTerm.parse(current)
            service.save(snapshot.id, {
                "name": name, "program": program, "intake": intake_term,
                "current_term": current_term, "status": status,
                "completed": _course_rows(completed, graded=True),
                "in_progress": _course_rows(in_progress, graded=False), "goals": goals,
            }, snapshot.revision)
        except (ValueError, DatabaseError) as error:
            st.error(str(error))
        else:
            st.session_state.pop("profile_edit", None)
            st.session_state.profile_saved = str(snapshot.id)
            st.rerun()


def profile_screen(service: ProfileService, profile_id: UUID | None) -> None:
    st.title("Student Profile")
    st.caption("Fictional workshop records, saved in PostgreSQL. Changes here affect future answers.")
    if profile_id is None:
        st.info("Select a student in the sidebar to view their profile.")
        return
    try:
        profile = service.get(profile_id)
    except (ValueError, DatabaseError) as error:
        st.error(str(error))
        return
    if st.session_state.pop("profile_saved", None) == str(profile.id):
        st.success("Profile saved. Your next question will use the updated information.")
    edit = st.session_state.get("profile_edit")
    if edit and edit["snapshot"].id == profile.id:
        _edit(service, edit["snapshot"], edit["token"])
        return
    show_profile(profile)
    if st.button("Edit profile", type="primary"):
        st.session_state.profile_edit = {"snapshot": profile, "token": uuid4().hex}
        st.rerun()
