# Document Templates

This directory contains default Jinja2 templates for business document generation.

## Template Variables

All templates receive the following standard context:

- `{{ company.name }}` — Tenant company name
- `{{ company.logo_url }}` — Company logo
- `{{ company.address }}` — Company address
- `{{ entity.ref_number }}` — Document reference number
- `{{ entity.date }}` — Document date
- `{{ entity.line_items }}` — List of line items
- `{{ entity.total_amount }}` — Document total

## Template Files

Templates will be added as each flow is built:

- `invoice.html` — Sales invoice (Sell flow)
- `quotation.html` — Sales quotation (Sell flow)
- `purchase_order.html` — Purchase order (Buy flow)
- `delivery_note.html` — Delivery/shipping note (Sell flow)
- `receipt.html` — Payment receipt (Sell/Buy flow)

## Customization

Tenant-specific template overrides are stored in the database
and take precedence over these defaults.
