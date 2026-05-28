"""
Documents — Service layer.

Handles Jinja2 template rendering to HTML and outlines PDF conversion
for business documents (invoices, POs, quotes, delivery notes).
"""
import os
import logging
from typing import Any, Optional
from jinja2 import Environment, FileSystemLoader, TemplateSyntaxError, TemplateNotFound

logger = logging.getLogger(__name__)


class DocumentService:
    """
    Service for generating business documents from templates.

    Default templates ship in core/core/documents/templates/.
    Tenant-specific templates override defaults and are stored in the database.

    Usage:
        doc_service = DocumentService()
        pdf_bytes = await doc_service.generate_pdf(
            template_name="invoice",
            context={"company": company_data, "entity": invoice_data}
        )
    """

    def __init__(self, templates_dir: Optional[str] = None):
        if templates_dir is None:
            # Resolve default templates dir relative to this file
            templates_dir = os.path.join(os.path.dirname(__file__), "templates")
        self._templates_dir = templates_dir
        
        # Initialize Jinja2 Environment with FileSystemLoader
        if os.path.exists(self._templates_dir):
            self._env = Environment(loader=FileSystemLoader(self._templates_dir))
        else:
            self._env = Environment()  # Fallback inline-only environment

    async def generate_pdf(
        self,
        template_name: str,
        context: dict[str, Any],
        tenant_template_override: Optional[str] = None,
    ) -> bytes:
        """
        Generate a PDF document from a Jinja2 template.

        Args:
            template_name: Name of the template (e.g., 'invoice', 'purchase_order').
            context: Template variables (company info, entity data, line items, etc.).
            tenant_template_override: Optional HTML template string from the database.

        Returns:
            PDF file contents as bytes.

        Raises:
            ImportError: If weasyprint is not installed. See _html_to_pdf for install instructions.
            ValueError:  If the template cannot be found or contains a syntax error.
        """
        html_content = await self.render_html(
            template_name=template_name,
            context=context,
            html_content_override=tenant_template_override,
        )
        return self._html_to_pdf(html_content)

    async def render_html(
        self,
        template_name: str,
        context: dict[str, Any],
        html_content_override: Optional[str] = None,
    ) -> str:
        """
        Render a Jinja2 template to HTML (without PDF conversion).

        Useful for email bodies and print previews.

        Args:
            template_name: Name of the template (e.g., 'invoice').
            context: Template variables (company info, entity data, line items, etc.).
            html_content_override: Raw Jinja2 template string (e.g. from database).

        Returns:
            Rendered HTML string.
        """
        try:
            if html_content_override:
                template = self._env.from_string(html_content_override)
            else:
                # Add suffix if missing
                filename = template_name if template_name.endswith(".html") else f"{template_name}.html"
                template = self._env.get_template(filename)
                
            return template.render(**context)
        except TemplateNotFound as e:
            logger.error(f"Template not found: {template_name} in {self._templates_dir}")
            raise ValueError(f"Template '{template_name}' not found.") from e
        except TemplateSyntaxError as e:
            logger.error(f"Jinja2 syntax error in template {template_name}: {e}")
            raise ValueError(f"Syntax error in template '{template_name}': {e}") from e
        except Exception as e:
            logger.error(f"Failed to render HTML template: {e}")
            raise RuntimeError(f"Failed to render template: {e}") from e

    @staticmethod
    def _html_to_pdf(html_content: str) -> bytes:
        """
        Converts an HTML string to PDF bytes.

        Uses ``weasyprint`` when available. If the library is not installed, raises
        ``ImportError`` with a clear install instruction rather than silently failing.

        To enable PDF generation, add weasyprint to the project dependencies::

            pip install weasyprint

        Args:
            html_content: The rendered HTML document string.

        Returns:
            PDF file contents as bytes.

        Raises:
            ImportError: If weasyprint is not installed.
        """
        try:
            from weasyprint import HTML  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "PDF generation requires 'weasyprint'. "
                "Install it with: pip install weasyprint"
            ) from exc

        return HTML(string=html_content).write_pdf()
