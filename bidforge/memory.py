import streamlit as st


def get_memory():
    """Return notes saved in the current Streamlit browser session."""
    return st.session_state.get("bidforge_memory", [])


def add_to_memory(note: str) -> None:
    notes = get_memory()
    notes.append(note)
    st.session_state.bidforge_memory = notes[-30:]


def reset_memory() -> None:
    st.session_state.bidforge_memory = []
