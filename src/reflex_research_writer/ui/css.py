import warnings
from typing import Optional
from importlib import resources
import reflex_research_writer.ui.assets as assets


def get_gradio_css(css_file_name: str, font_file_name: Optional[str] = None) -> str:
    # Construct the resource path within the project package
    css_path = resources.files(assets).joinpath(css_file_name)

    # Check if the CSS file exists before trying to read it
    if not css_path.is_file():
        raise FileNotFoundError(f"CSS file '{css_file_name}' not found in assets directory.")

    custom_css = css_path.read_text(encoding="utf-8")

    if font_file_name:
        # Construct the resource path for the font file
        font_path = resources.files(assets).joinpath(font_file_name)

        # Check if the font file actually exists
        if not font_path.is_file():
            warnings.warn(
                f"Font file '{font_file_name}' not found in assets directory. "
                "Skipping font-face CSS.",
                RuntimeWarning,
                stacklevel=2
                )
        else:
            # File exists, safe to append the font CSS
            custom_css += f"""
            @font-face {{
              font-family: 'Noto Flags';
              src: url('/gradio_api/file=assets/{font_file_name}') format('truetype');
              /* Critical: Only apply this font to Regional Indicator Symbols (Flags) */
              unicode-range: U+1F1E6-1F1FF;
              font-display: swap;
            }}

            /* Apply to the whole app; flags will use 'Noto Flags', others use system defaults */
            body, .gradio-container, .prose, * {{
                font-family: 'Noto Flags', 'Segoe UI Emoji', system-ui, sans-serif !important;
            }}
            """

    return custom_css