from __future__ import annotations

import os

import gradio as gr
from dotenv import load_dotenv

from db import init_db, SessionLocal
from models import Project
from memory_manager import MemoryManager, load_initial_profile
from llm_backends import make_llm

load_dotenv()

USER_ID = os.getenv("USER_ID", "demo-user")
DEFAULT_PROJECT = os.getenv("DEFAULT_PROJECT", "Default Project")

mm: MemoryManager = None
current_project: str = DEFAULT_PROJECT


def init() -> None:
    global mm
    init_db()
    llm = make_llm()
    mm = MemoryManager(llm_callable=llm)
    load_initial_profile(USER_ID)


def get_projects() -> list[str]:
    """Get list of existing projects for the user."""
    db = SessionLocal()
    try:
        projects = db.query(Project).filter_by(owner_id=USER_ID).all()
        return [p.name for p in projects] or [DEFAULT_PROJECT]
    finally:
        db.close()


def ensure_project(name: str) -> str:
    db = SessionLocal()
    try:
        proj = (
            db.query(Project)
            .filter_by(owner_id=USER_ID, name=name)
            .first()
        )
        if not proj:
            proj = Project(owner_id=USER_ID, name=name)
            db.add(proj)
            db.commit()
            db.refresh(proj)
        return proj.id
    finally:
        db.close()


def set_project(name: str):
    global current_project
    current_project = name or DEFAULT_PROJECT
    return name


def chat_fn(message: str, history: list):
    if not message.strip():
        return ""
    project_id = ensure_project(current_project)
    reply = mm.handle_message(USER_ID, project_id, message)
    return reply


def main():
    init()

    css = """
    footer {display: none !important;}
    .gradio-container {max-width: 900px !important;}
    """

    with gr.Blocks(css=css, title="Clara", theme=gr.themes.Soft()) as demo:
        with gr.Row():
            gr.Markdown("## Clara")
            project_dropdown = gr.Dropdown(
                choices=get_projects(),
                value=DEFAULT_PROJECT,
                label="Project",
                allow_custom_value=True,
                interactive=True,
                scale=2,
            )

        project_dropdown.change(set_project, inputs=[project_dropdown])

        gr.ChatInterface(
            fn=chat_fn,
            chatbot=gr.Chatbot(
                height=500,
                show_copy_button=True,
                type="tuples",
            ),
            textbox=gr.Textbox(
                placeholder="Message Clara...",
                container=False,
            ),
        )

    demo.launch()


if __name__ == "__main__":
    main()
