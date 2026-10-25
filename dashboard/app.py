"""SentinelAI Streamlit dashboard. Talks only to the FastAPI backend."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st
from components.api_client import SentinelAPI
from components.theme import THEME_CSS

SAMPLE_PATH = Path(__file__).resolve().parents[1] / "sample_app" / "sample_incident.json"


def load_sample() -> dict:
    if SAMPLE_PATH.exists():
        return json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    return {
        "title": "Sample: add() returns the wrong result",
        "error_message": "AssertionError: assert add(2, 3) == 5  (got -1)",
        "stack_trace": 'File "test_buggy_app.py", line 5, in test_add\n    assert add(2, 3) == 5',
        "repository_path": "sample_app",
    }


def api() -> SentinelAPI:
    return SentinelAPI(st.session_state.get("backend_url"))


def show_error(exc: Exception) -> None:
    st.error(str(exc))


def render_overview(incidents: list[dict]) -> None:
    counts: dict[str, int] = {}
    for item in incidents:
        status = item.get("status", "UNKNOWN")
        counts[status] = counts.get(status, 0) + 1
    cols = st.columns(4)
    cols[0].markdown(
        f"<div class='metric-card'><div class='sentinel-kicker'>Total</div><h3>{len(incidents)}</h3></div>",
        unsafe_allow_html=True,
    )
    for column, status in zip(cols[1:], ["RECEIVED", "VALIDATED", "APPROVED"], strict=False):
        column.markdown(
            (
                "<div class='metric-card'>"
                f"<div class='sentinel-kicker'>{status}</div>"
                f"<h3>{counts.get(status, 0)}</h3></div>"
            ),
            unsafe_allow_html=True,
        )
    if counts:
        st.caption("Other statuses: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))


def main() -> None:
    st.set_page_config(page_title="SentinelAI", page_icon="🛡️", layout="wide")
    st.markdown(THEME_CSS, unsafe_allow_html=True)
    if "backend_url" not in st.session_state:
        st.session_state.backend_url = SentinelAPI().base_url
    if "selected_id" not in st.session_state:
        st.session_state.selected_id = None

    st.markdown(
        """
        <div class="sentinel-hero">
            <div class="sentinel-kicker">Team TriNova</div>
            <h1>SentinelAI</h1>
            <p>AI-assisted incident response. Analyze, patch, validate, then wait for a human.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.subheader("Connection")
        st.session_state.backend_url = st.text_input("Backend URL", st.session_state.backend_url)
        if st.button("Refresh"):
            st.rerun()
        st.subheader("Demo shop")
        if st.button("Simulate incident"):
            try:
                created = api().simulate()
                st.session_state.selected_id = created["id"]
                st.rerun()
            except Exception as exc:
                show_error(exc)
        if st.button("Break checkout (outage)"):
            try:
                created = api().break_checkout("payments_outage")
                st.session_state.selected_id = created["id"]
                st.rerun()
            except Exception as exc:
                show_error(exc)
        if st.button("Break checkout (code bug)"):
            try:
                created = api().break_checkout("code_bug")
                st.session_state.selected_id = created["id"]
                st.rerun()
            except Exception as exc:
                show_error(exc)
        try:
            health = api().health()
            db_state = "ready" if health.get("database_ready") else "missing"
            st.success(
                f"{health.get('app')} · provider={health.get('ai_provider')} · db={db_state}"
            )
            st.caption("Gemini key is never shown here. Local prototype is not production-hardened.")
        except Exception as exc:
            show_error(exc)

    try:
        incidents = api().list_incidents()
    except Exception as exc:
        show_error(exc)
        incidents = []

    render_overview(incidents)

    left, right = st.columns([0.9, 1.4])
    with left:
        st.subheader("Submit incident")
        sample = load_sample()
        if st.button("Load sample incident into form"):
            st.session_state.form_title = sample["title"]
            st.session_state.form_error = sample["error_message"]
            st.session_state.form_stack = sample["stack_trace"]
            st.session_state.form_repo = sample.get("repository_path") or "sample_app"

        title = st.text_input("Title", key="form_title", value=sample["title"])
        error_message = st.text_area("Error message", key="form_error", value=sample["error_message"])
        stack_trace = st.text_area("Stack trace", key="form_stack", value=sample["stack_trace"], height=120)
        repository_path = st.text_input(
            "Repository path",
            key="form_repo",
            value=sample.get("repository_path") or "sample_app",
        )
        if st.button("Submit incident", type="primary"):
            try:
                created = api().create_incident(
                    {
                        "title": title,
                        "error_message": error_message,
                        "stack_trace": stack_trace,
                        "repository_path": repository_path or None,
                    }
                )
                st.session_state.selected_id = created["id"]
                st.success(f"Created incident {created['id']}")
                st.rerun()
            except Exception as exc:
                show_error(exc)

        st.subheader("Incidents")
        if not incidents:
            st.info("No incidents yet.")
        for item in incidents:
            label = f"{item['status']} · {item['title']}"
            if st.button(label, key=f"select-{item['id']}"):
                st.session_state.selected_id = item["id"]
                st.rerun()

    with right:
        st.subheader("Incident detail")
        selected_id = st.session_state.selected_id
        if not selected_id:
            st.caption("Select an incident to inspect analysis, patch, and validation.")
            return
        try:
            incident = api().get_incident(selected_id)
        except Exception as exc:
            show_error(exc)
            return

        st.markdown(
            f"<div class='panel'><span class='status-pill'>{incident['status']}</span>"
            f"<p><strong>{incident['title']}</strong></p>"
            f"<p>{incident['error_message']}</p></div>",
            unsafe_allow_html=True,
        )
        with st.expander("Stack trace"):
            st.code(incident.get("stack_trace") or "(empty)")

        verdict = incident.get("verdict")
        if verdict:
            st.markdown(
                f"**Triage:** `{verdict.get('category')}` · track `{verdict.get('recommended_track')}` · "
                f"confidence {verdict.get('confidence')}"
            )
            for line in verdict.get("evidence") or []:
                st.caption(f"• {line}")
        replay = incident.get("replay")
        if replay:
            before = "OK" if replay.get("before_ok") else "FAIL"
            after = "OK" if replay.get("after_ok") else "FAIL"
            st.markdown(f"**Replay:** before {before} → after {after}")
        if incident.get("mitigation"):
            mit = incident["mitigation"]
            st.caption(
                f"Simulated mitigation `{mit.get('action')}` · {mit.get('status')} · {mit.get('detail')}"
            )

        actions = st.columns(4)
        if actions[0].button("Analyze"):
            try:
                incident = api().analyze(selected_id)
                st.rerun()
            except Exception as exc:
                show_error(exc)
        if actions[1].button("Generate patch"):
            try:
                incident = api().generate_patch(selected_id)
                st.rerun()
            except Exception as exc:
                show_error(exc)
        if actions[2].button("Validate"):
            try:
                incident = api().validate(selected_id)
                st.rerun()
            except Exception as exc:
                show_error(exc)
        if actions[3].button("Reload"):
            st.rerun()
        extra = st.columns(4)
        if extra[0].button("Triage"):
            try:
                api().triage(selected_id)
                st.rerun()
            except Exception as exc:
                show_error(exc)
        if extra[1].button("Replay"):
            try:
                api().replay(selected_id)
                st.rerun()
            except Exception as exc:
                show_error(exc)
        if extra[2].button("Post-mortem"):
            try:
                api().postmortem(selected_id)
                st.rerun()
            except Exception as exc:
                show_error(exc)

        analysis = incident.get("root_cause_analysis")
        st.markdown("#### Root-cause analysis")
        if analysis:
            st.markdown(
                f"<div class='panel'><p>{analysis.get('hypothesis')}</p>"
                f"<p>Suspected: <code>{analysis.get('suspected_file')}</code> / "
                f"<code>{analysis.get('suspected_function')}</code> · "
                f"confidence={analysis.get('confidence')} · provider={analysis.get('provider')}</p>"
                f"<p><em>{analysis.get('disclaimer')}</em></p></div>",
                unsafe_allow_html=True,
            )
            steps = analysis.get("recommended_next_steps") or []
            if steps:
                st.markdown("\n".join(f"- {step}" for step in steps))
        else:
            st.caption("No analysis yet.")

        st.markdown("#### Proposed patch")
        patch = incident.get("proposed_patch")
        if patch:
            st.code(patch, language="diff")
        else:
            st.caption("No patch yet. The original repository is never modified automatically.")

        st.markdown("#### Validation")
        validation = incident.get("validation_results")
        if validation:
            overall = "passed" if validation.get("overall_passed") else "failed"
            st.markdown(f"**Overall: {overall}**")
            st.caption(validation.get("disclaimer", ""))
            for check in validation.get("checks") or []:
                st.markdown(
                    f"- `{check.get('name')}`: **{check.get('status')}** — {check.get('detail')}"
                )
                if check.get("stdout"):
                    with st.expander(f"{check.get('name')} stdout"):
                        st.code(check.get("stdout"))
                if check.get("stderr"):
                    with st.expander(f"{check.get('name')} stderr"):
                        st.code(check.get("stderr"))
        else:
            st.caption("No validation results yet.")

        can_approve = incident["status"] == "VALIDATED" and bool(
            (incident.get("validation_results") or {}).get("overall_passed")
        )
        st.markdown("#### Human decision")
        approve_col, reject_col = st.columns(2)
        with approve_col:
            if st.button("Approve", disabled=not can_approve):
                try:
                    api().approve(selected_id)
                    st.rerun()
                except Exception as exc:
                    show_error(exc)
            if not can_approve:
                st.caption("Approval stays disabled until validation passes.")
        with reject_col:
            reason = st.text_input("Rejection reason")
            if st.button("Reject"):
                if not reason.strip():
                    st.warning("Provide a rejection reason.")
                else:
                    try:
                        api().reject(selected_id, reason)
                        st.rerun()
                    except Exception as exc:
                        show_error(exc)

        approval = incident.get("approval")
        if approval:
            st.info(
                f"Decision: {approval.get('decision')} by {approval.get('actor')}. "
                f"{approval.get('reason') or ''}"
            )

        with st.expander("History"):
            for event in incident.get("history") or []:
                st.write(
                    f"{event.get('timestamp')} · {event.get('event')} · "
                    f"{event.get('from_status')} → {event.get('to_status')}"
                )


if __name__ == "__main__":
    main()
else:
    main()
