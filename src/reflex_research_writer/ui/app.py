import os
import re
import ast
import json
import asyncio
import gradio as gr

from dotenv import load_dotenv
from typing import Tuple, Dict, List, Literal, cast, AsyncIterator

from reflex_research_writer.agent.factory import create_reflexion_agent
from reflex_research_writer.agent.models import StatusMessage, FinalMessage
from reflex_research_writer.agent.reflexion_agent import ReflexionAgent
from reflex_research_writer.search.factory import make_search_engine
from reflex_research_writer.ui.css import get_gradio_css
from reflex_research_writer.ui.export import convert_md_to_pdf

#from reflex_research_writer.ui.helper import MessageTranslator, load_yaml_file
from reflex_research_writer.locales.localizers import MessageLocalizer, UIStringLocalizer


def extract_code_and_message(exc):
    code = getattr(exc, "status_code", None) or getattr(exc, "code", None) or "N/A"
    text = str(exc)
    # try to find a JSON/dict payload in the exception text
    m = re.search(r"(\{.*\})", text, re.S)
    payload = None
    if m:
        s = m.group(1)
        try:
            payload = json.loads(s)
        except Exception:
            try:
                payload = ast.literal_eval(s)
            except Exception:
                payload = None

    message = None
    if isinstance(payload, dict):
        err = payload.get("error", payload)
        if isinstance(err, dict):
            code = code or err.get("code") or err.get("status") or err.get("status_code")
            message = err.get("message") or err.get("msg")
        else:
            message = str(err)

    if not message:
        message = re.sub(r"\{.*\}", "", text, flags=re.S).strip() or text.strip()

    return code, message





def _create_app(agent: ReflexionAgent, concurrency_limit: int) -> gr.Blocks:
    """Receives a pre-configured agent via Dependency Injection."""

    async def generate(ui_language: str, target_language: str, topic: str, max_revisions: int, num_paragraphs: int) -> AsyncIterator[Tuple[str|dict, str|dict, dict, dict, dict]]:
        """
        Generator function for Gradio.
        Yields updates to the status_box and draft_box simultaneously.
        """

        msg = MessageLocalizer(ui_language)
        gui = UIStringLocalizer(ui_language)

        if not topic.strip():
            yield (
                gr.skip(),
                gui.get('error.empty_topic'),
                gr.update(interactive=True),
                gr.update(interactive=False),
                gr.update(interactive=False, value=None)
            )
            return

        status_history = []

        # Immediately yield a disabled button to gray it out visually
        yield (
            "",
            gui.get('draftbox'),
            gr.update(interactive=False),
            gr.update(interactive=True),
            gr.update(interactive=False, value=None)
        )

        try:
            # Run the agent stream
            async for stream_event in agent.run_stream(
                    topic=topic,
                    target_language=gui.target_language_name(target_language),
                    max_revisions=max_revisions,
                    num_paragraphs=num_paragraphs
            ):
                event_type, payload = stream_event  # Unpack the tuple
                match event_type:
                    case "status":
                        status_message: StatusMessage = payload
                        message = msg.get(
                            status_message["key"],
                            status_message["phase"],
                            **status_message["params"],
                        )
                        if status_message["phase"] == "exit":
                            status_history.append(f"\n\n&nbsp;\n\n---\n\n---\n\n{message}\n\n---\n\n---\n\n&nbsp;\n\n")
                        else:
                            status_history.append(message)
                            if status_message["phase"] == "end":
                                #status_history.append("<hr/>")
                                status_history.append("\n\n---\n\n&nbsp;\n\n")

                        # Yielding the exact tuple structure Gradio expects
                        yield (
                            "\n\n".join(status_history),
                            gr.skip(),
                            gr.update(interactive=False),
                            gr.update(interactive=True),
                            gr.update(interactive=False, value=None)
                        )

                    case "final":
                        final_message: FinalMessage = payload
                        final_draft = final_message["draft"]
                        final_evaluation = final_message["evaluation"]
                        final_score = final_message["score"]

                        appendix = f"## {gui.get('evaluation').format(final_score)}\n\n&nbsp;\n\n{final_evaluation}"
                        content = f"{final_draft}\n\n&nbsp;\n\n&nbsp;\n\n---\n\n&nbsp;\n\n{appendix}"
                        pdf_content = [final_draft, appendix]

                        with open("./md_content.txt", "w", encoding="utf-8") as f:
                            f.write(f"{final_draft} \n\n {appendix}")

                        yield (
                            gr.skip(),
                            content,
                            gr.update(interactive=True),
                            gr.update(interactive=False),
                            gr.update(interactive=True, value=convert_md_to_pdf(pdf_content))
                        )

        except asyncio.CancelledError:
            # This triggers when the user clicks the Stop button and confirms with Yes button
            status_history.append(f"\n\n&nbsp;\n\n---\n\n---\n\n{gui.get('error.user_stop')}\n\n---\n\n---\n\n&nbsp;\n\n")

            yield (
                "\n\n".join(status_history),
                gr.skip(),
                gr.update(interactive=True),
                gr.update(interactive=False),
                gr.update(interactive=False, value=None)
            )
            return

        except Exception as exc:
            code, message = extract_code_and_message(exc)
            status_history.append(f"\n\n&nbsp;\n\n---\n\n---\n\n{gui.get('error.error_code')} {code} - {message}\n\n---\n\n---\n\n&nbsp;\n\n")

            yield (
                    "\n\n".join(status_history),
                gr.skip(),
                gr.update(interactive=True),
                gr.update(interactive=False),
                gr.update(interactive=False, value=None)
                )
            return


    """Builds and returns the Gradio UI"""
    # Build UI
    with gr.Blocks(title="AI Reflex-Search-Writer", fill_height=True, fill_width=True) as app:

        # --- Define Components First ---

        with gr.Row():
            title_md = gr.Markdown()

        with gr.Row(equal_height=True):
            with gr.Column(scale=2):
                with gr.Row():
                    subtitle_md = gr.Markdown()

                with gr.Row():
                    instructions_md = gr.Markdown()

                with gr.Row():
                    topic_input = gr.Textbox(
                        scale=5,
                    )

                    target_lang_dd = gr.Dropdown(
                        multiselect=False,
                        scale=1
                    )

            with gr.Column(scale=1, elem_classes="control-col"):
                with gr.Row():
                    max_revs_slider = gr.Slider(
                        minimum=1,
                        maximum=5,
                        value=3,
                        step=1
                    )
                    num_pars_slider = gr.Slider(
                        minimum=5,
                        maximum=15,
                        value=10,
                        step=1
                    )

                with gr.Row(elem_id="control-row"):
                    submit_btn = gr.Button(value="", variant="primary", scale=2)
                    stop_btn = gr.Button(value="", variant="stop", scale=1, interactive=False)
                    download_btn = gr.DownloadButton(label="", variant="secondary", scale=2, interactive=False)

                # CSS-hidden confirmation section (appears only when stop_btn is clicked)
                with gr.Row(elem_id="confirm-row"):
                    with gr.Column(elem_classes="alert-col"):
                        alert_head_md = gr.Markdown(elem_classes="alert-head")
                        with gr.Row():
                            yes_btn = gr.Button(variant="secondary", scale=1, size="sm")
                            no_btn = gr.Button(variant="primary", scale=1, size="sm")


        with gr.Row(equal_height=True):
            with gr.Column(scale=2):
                draft_head_md = gr.Markdown(show_label=False)

            with gr.Column(scale=1):
                status_head_md = gr.Markdown(show_label=False)

        with gr.Row(equal_height=True, elem_classes="output-row"):
            with gr.Column(scale=2, elem_classes="markdown-box-container"):
                 draft_box_md = gr.Markdown(show_label=False, elem_classes="markdown-full") # NOT autoscroll=True

            with gr.Column(scale=1, elem_classes="markdown-box-container"):
                status_box_md = gr.Markdown(show_label=False, elem_classes="markdown-full") # NOT autoscroll=True

        # Use a hidden Textbox instead of gr.State
        ui_lang = gr.Textbox(value="en", visible=False, elem_id="ui_lang_holder")

        # --- Define the UI_MAP (after components creation) ---
        UI_MAP = {
            title_md: {"value": "title", "prefix": "# "},
            subtitle_md: {"value": "subtitle", "prefix": "### "},
            instructions_md: {"value": "instructions"},
            topic_input: {"label": "topinput.label", "placeholder": "topinput.placeholder"},
            target_lang_dd: {"label": "targlang.label"},
            max_revs_slider: {"label": "revslider.label", "info": "revslider.info"},
            num_pars_slider: {"label": "parslider.label", "info": "parslider.info"},
            draft_head_md: {"value": "drafthead", "prefix": "### "},
            draft_box_md: {"value": "draftbox"},
            status_head_md: {"value": "statushead", "prefix": "### "},
            status_box_md: {"value": "statusbox"},
            submit_btn: {"value": "submit.value"},
            stop_btn: {"value": "stop.value"},
            download_btn: {"label": "download.value"},
            alert_head_md: {"value": "alerthead"},
            yes_btn: {"value": "yes.value"},
            no_btn: {"value": "no.value"},
        }

        # --- Define Initialization Function ---
        def init_session(request: gr.Request):
            # Detects the browser language (e.g. "it") with fallback to English
            # with a tiny safety split for headers like "en-US"
            raw_header = request.headers.get("accept-language", "en")
            browser_lang = raw_header.split(",")[0].split("-")[0].split(";")[0].strip().lower()[:2]

            # lang = browser_lang if browser_lang in TRANSLATIONS else "en"
            # lang_dict = TRANSLATIONS[lang]

            gui = UIStringLocalizer(browser_lang)

            # B. Genera automaticamente tutti i gr.update() necessari per la UI
            updates = []
            for component, config in UI_MAP.items():
                props = {}
                for prop_name, translation_key in config.items():
                    if prop_name == "prefix":  # Salta le proprietà di formattazione interna
                        continue

                    # Prende la stringa tradotta se esiste...
                    # text = lang_dict.get(translation_key, translation_key)
                    text = gui.get(translation_key)

                    # Se è presente un prefisso (es. per Markdown), lo applica
                    if "prefix" in config:
                        text = f"{config['prefix']}{text}"

                    props[prop_name] = text

                # FIX: If it's the target_lang_dd, also set its current value and localized choices
                if component == target_lang_dd:
                    props["value"] = gui.current_language #lang
                    props["choices"] = gui.languages_list() # _languages_list(lang)
                    props["interactive"] = True

                updates.append(gr.update(**props))

            # Append the detected language to the end of the updates list
            updates.append(gui.current_language)   # lang)

            return updates

        # --- Link Events ---
        # On load: init_session returns updates for everything in UI_MAP + the target_lang_dd
        app.load(
            fn=init_session,
            inputs=None,
            outputs=list(UI_MAP.keys()) + [ui_lang]
        )

        generate_event = submit_btn.click(
            fn=generate,
            inputs=[ui_lang, target_lang_dd, topic_input, max_revs_slider, num_pars_slider],
            outputs=[status_box_md, draft_box_md, submit_btn, stop_btn, download_btn],
            concurrency_limit=concurrency_limit
        )

        show_confirm_js = "() => { document.getElementById('control-row').style.display = 'none'; document.getElementById('confirm-row').style.display = 'flex'; }"
        hide_confirm_js = "() => { document.getElementById('control-row').style.display = 'flex'; document.getElementById('confirm-row').style.display = 'none'; }"

        stop_btn.click(fn=None, js=show_confirm_js)

        no_btn.click(fn=None, js=hide_confirm_js)

        yes_btn.click(fn=None, js=hide_confirm_js, cancels=[generate_event])

    return app


def main():
    """CLI Entry point for the Gradio UI."""

    # Load environment variables
    # ChatOpenAI automatically get OPENAI_API_KEY and OPENAI_BASE_URL as environment variables
    load_dotenv()
    openai_model = os.getenv("OPENAI_MODEL")
    tavily_api_key = os.getenv("TAVILY_API_KEY", "")
    serpapi_api_key = os.getenv("SERPAPI_API_KEY", "")
    concurrency = int(os.getenv("CONCURRENCY_LIMIT", 5))

    # Get the string from env amd validate against allowed Literal values
    raw_engine_type = os.getenv("SEARCH_ENGINE", "tavily")  # Default to tavily
    if raw_engine_type not in ["tavily", "duckduckgo", "serpapi"]:
        raise ValueError(f"Invalid SEARCH_ENGINE in .env: {raw_engine_type}")
    # Cast for the type checker
    search_engine_type = cast(Literal["tavily", "duckduckgo", "serpapi"], raw_engine_type)

    search_engine = make_search_engine(engine_type=search_engine_type, tavily_api_key=tavily_api_key, serpapi_api_key=serpapi_api_key)

    # Initialize agent
    agent = create_reflexion_agent(openai_model=openai_model, search_engine=search_engine)

    # Create and launch the app
    app = _create_app(agent=agent, concurrency_limit=concurrency)

    theme = gr.themes.Ocean()

    font_file_name ="NotoColorEmoji-flagsonly.ttf"
    custom_css = get_gradio_css("custom.css", font_file_name)

    # Enable the queue with a higher size limit (two times the concurrency_limit set in submit_btn.click)
    app.queue(max_size=concurrency * 2)

    # share=False for local dev, share=True to get a public URL
    app.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        theme=theme,
        allowed_paths=[f"assets/{font_file_name}"],
        css=custom_css
    )


if __name__ == "__main__":
    main()
