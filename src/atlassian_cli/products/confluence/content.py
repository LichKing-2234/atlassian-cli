import tempfile
from pathlib import Path
from urllib.parse import urlparse

from md2conf.converter import (
    ConfluencePageCollection,
    ConfluenceStorageFormatConverter,
    ConfluenceUserCollection,
    ConverterOptions,
    elements_from_strings,
    elements_to_string,
    markdown_to_html,
)
from md2conf.metadata import ConfluenceSiteMetadata


def markdown_to_storage(
    content: str, *, base_url: str, enable_heading_anchors: bool = False
) -> str:
    with tempfile.TemporaryDirectory() as temp_dir:
        root_dir = Path(temp_dir)
        path = root_dir / "content.md"
        path.write_text(content, encoding="utf-8")
        root = elements_from_strings([markdown_to_html(content)])
        parsed_url = urlparse(base_url)
        base_path = parsed_url.path or "/"
        if not base_path.endswith("/"):
            base_path += "/"
        converter = ConfluenceStorageFormatConverter(
            options=ConverterOptions(
                force_valid_url=False,
                heading_anchors=enable_heading_anchors,
                render_mermaid=False,
            ),
            path=path,
            root_dir=root_dir,
            site_metadata=ConfluenceSiteMetadata(
                domain=parsed_url.netloc,
                base_path=base_path,
                space_key=None,
            ),
            page_metadata=ConfluencePageCollection(),
            user_metadata=ConfluenceUserCollection(),
        )
        converter.visit(root)
        return str(elements_to_string(root))
