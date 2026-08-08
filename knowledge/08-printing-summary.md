# Printing Summary

## Purpose

This document provides a high-level overview of the printing architecture, standards, workflows, and requirements used throughout the LPG Agency Management Platform.

It serves as the primary reference for developers and AI coding agents when implementing or modifying any printing-related functionality.

For detailed specifications, refer to:

- docs/architecture/09-printing-architecture.md
- docs/ui/
- docs/business/business-rules.md
- docs/data/15-reporting-data-model.md

---

# Printing Philosophy

Printing is a core business capability.

Every printable document should be:

- Consistent
- Configurable
- Professional
- Readable
- Accessible
- Reusable
- Printer Independent

Printing logic should never be tightly coupled with UI components.

---

# Printing Objectives

The printing system should support:

- Customer Receipts
- Invoices
- Delivery Receipts
- Payment Receipts
- Cash Receipts
- Customer Ledger
- Inventory Reports
- Driver Reports
- Daily Sales Reports
- GST Reports
- Administrative Reports

All printable documents should support preview before printing.

---

# Supported Output Formats

The platform supports:

## Thermal Printing

Supported widths:

- 58 mm
- 80 mm

Used for:

- Delivery Receipt
- Payment Receipt
- Cash Receipt

---

## Standard Printing

Supported paper sizes:

- A4 Portrait
- A4 Landscape

Used for:

- Invoices
- Reports
- Ledgers
- GST Documents

---

## PDF Export

All printable documents should support:

- Download
- Share
- Email
- Archive

Generated PDFs should preserve formatting across devices.

---

# Printable Documents

## Customer Documents

- Customer Registration Form
- Customer Profile
- Customer Ledger
- Booking Receipt
- Invoice
- Payment Receipt

---

## Delivery Documents

- Delivery Receipt
- Delivery Manifest
- Driver Route Sheet
- Vehicle Load Sheet
- Proof of Delivery

---

## Inventory Documents

- Stock Report
- Stock Adjustment Report
- Warehouse Report
- Vehicle Inventory Report
- Reconciliation Report

---

## Accounting Documents

- Tax Invoice
- Cash Receipt
- Credit Note
- Outstanding Report
- GST Report
- Collection Report

---

## Administrative Documents

- Audit Report
- User Report
- Activity Report
- Configuration Report

---

# Printing Workflow

Every print operation follows:

```
Business Data
        │
        ▼
Data Transformation
        │
        ▼
Print Template
        │
        ▼
Preview
        │
        ▼
PDF / Browser Print
        │
        ▼
Printer
```

Printing should always use prepared view models instead of raw database entities.

---

# Print Templates

Every document should use reusable templates.

Examples:

- Receipt Template
- Invoice Template
- Report Template
- Ledger Template
- Certificate Template

Templates should be configurable without changing application code.

---

# Template Components

Reusable print components include:

- Header
- Footer
- Company Information
- Customer Information
- Item Table
- Summary Section
- QR Code
- Barcode
- Signature Area
- Terms & Conditions

Avoid duplicating layout logic.

---

# Company Branding

Printable documents should support tenant branding.

Branding includes:

- Company Logo
- Company Name
- Address
- GST Number
- Contact Information
- Footer Message

Branding should be configurable per tenant.

---

# Barcode & QR Code

Supported barcode formats:

- Code 128
- QR Code

Used for:

- Invoice Number
- Booking Number
- Delivery Number
- Customer ID

Barcode generation should be reusable.

---

# Print Preview

Every printable document should support preview.

Preview features:

- Zoom
- Page Navigation
- Download PDF
- Print
- Share (future)

Preview should match the printed output.

---

# Browser Printing

Use browser-native printing where possible.

Requirements:

- Print-specific CSS
- Hidden navigation
- Hidden controls
- Proper page breaks
- Print margins

Print styles should not affect screen layouts.

---

# Print Styling

Use Design Tokens for:

- Typography
- Spacing
- Borders
- Colors (where applicable)

Print layouts should remain readable in grayscale.

Avoid unnecessary backgrounds.

---

# Thermal Printer Guidelines

Thermal receipts should:

- Minimize width
- Avoid unnecessary graphics
- Use optimized fonts
- Support automatic paper cutting
- Fit both 58 mm and 80 mm printers

Receipts should remain readable even on low-quality printers.

---

# A4 Printing Guidelines

A4 documents should include:

- Company Header
- Document Title
- Content
- Summary
- Signature Area
- Footer

Reports should automatically paginate.

---

# PDF Generation

PDF exports should:

- Preserve layout
- Embed fonts where appropriate
- Support page numbering
- Preserve tables
- Support digital archiving

Generated PDFs should match printed output.

---

# Print Performance

Printing should be optimized for:

- Large reports
- Thousands of rows
- Multiple pages
- Bulk printing

Long-running print jobs should execute asynchronously where appropriate.

---

# Accessibility

Printable documents should:

- Use readable typography
- Maintain sufficient contrast
- Preserve logical reading order
- Support screen readers for PDF where possible

Accessibility applies to exported documents as well.

---

# Internationalization

Printing should support:

- Multiple languages
- Currency formatting
- Date formatting
- Number formatting
- Regional tax formats

Locale settings should be tenant configurable.

---

# Security

Printing must respect:

- Authentication
- Authorization
- Tenant Isolation
- Data Privacy

Users may only print documents they are authorized to access.

Sensitive information should not appear unless permitted.

---

# Audit Logging

The following actions should be logged:

- Document Printed
- PDF Exported
- Bulk Printing
- Report Generated

Audit logs should include:

- User
- Tenant
- Document Type
- Timestamp

---

# AI Development Guidelines

Before implementing a printing feature:

1. Review the relevant business module.
2. Reuse existing print templates.
3. Use print view models instead of domain entities.
4. Support Print Preview.
5. Follow Design Tokens.
6. Support PDF export.
7. Support browser printing.
8. Respect tenant branding.
9. Preserve accessibility.
10. Add automated tests where appropriate.

Never:

- Duplicate print templates.
- Hardcode company branding.
- Couple printing logic with UI components.
- Expose unauthorized data.
- Ignore printer compatibility.

---

# Future Enhancements

Planned improvements include:

- Batch Printing
- Scheduled Report Generation
- Email PDF Automatically
- Digital Signatures
- Watermarks
- Custom Tenant Templates
- Label Printing
- Bluetooth Thermal Printer Support
- Cloud Print Integration

---

# Related Documentation

Refer to:

- docs/architecture/09-printing-architecture.md
- docs/data/15-reporting-data-model.md
- docs/business/business-rules.md
- docs/ui/
- docs/ui/08-design-system.md