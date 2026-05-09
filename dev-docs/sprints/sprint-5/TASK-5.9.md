# TASK-5.9: PDF Export of Projection

**Status:** TODO
**Sprint:** 5
**Priority:** P2 (medium — practical utility, not core calculation)
**Est. effort:** 2 hr
**Dependencies:** TASK-4.5

## Context

Users need to share their projection with a partner, banker, or accountant. A clean PDF export transforms Horizon from a personal toy into a professional planning tool. It's also a trust signal — if the tool can produce a document worth sharing, the calculations must be serious.

## Requirements

### Backend: PDF Generation

1. **Create endpoint** `GET /api/projection/export?scale=moderate&format=pdf`:
   - Generates a multi-page PDF with the user's projection summary
   - Uses a Python PDF library (weasyprint, reportlab, or fpdf2)
   - Returns the PDF as a downloadable file

2. **PDF Content — 3 pages:**

   **Page 1: Executive Summary**
   - Header: "HORIZON — Projection Patrimoniale" + user name + generation date
   - Profile snapshot: age, status, CA, growth rate, target retirement age
   - Key metrics in large type: patrimoine at retirement, passive income, readiness score (if TASK-5.5 is done)
   - Mini wealth trajectory chart (inline SVG → rasterized, or a simple matplotlib chart)

   **Page 2: Detailed Projection Table**
   - The full projection table (every 5 years + final year)
   - Same columns as the Runway page table
   - Color coding translated to PDF-safe colors
   - Footer: scale used (optimiste/modéré/pessimiste), inflation rate

   **Page 3: Configuration Summary**
   - Savings allocation breakdown (vehicle, balance, monthly contribution)
   - Expense summary (total monthly, annual)
   - Life entities summary (kids, pets, cars with cost ranges)
   - Projects summary (investments with yield, events with year/cost)
   - Top 3 insights (if TASK-5.4 is done)

3. **PDF Styling:**
   - Clean, professional layout — not a screenshot of the dark UI
   - White background, dark text, teal accent color for headers and highlights
   - Inter for text, JetBrains Mono for numbers
   - Footer on each page: "Généré par Horizon — horizonapp.fr — Simulation, ne constitue pas un conseil financier"

### Frontend

4. **Export button** on the Runway page:
   - Icon: download icon
   - Position: top-right of the Runway page, near the scale selector
   - Label: "Exporter PDF"
   - On click: show brief loading state ("Génération en cours…"), then trigger browser download
   - File name: `horizon-projection-{date}.pdf`

5. **Loading state:** PDF generation may take 2–3 seconds. Show a spinner or progress indicator.

### Technical Approach

6. **Recommended library: `fpdf2`** (lightweight, pure Python, no system dependencies):
   ```python
   from fpdf import FPDF
   
   class HorizonPDF(FPDF):
       def header(self):
           self.set_font("Helvetica", "B", 16)
           self.cell(0, 10, "HORIZON — Projection Patrimoniale", ln=True)
       
       def footer(self):
           self.set_y(-15)
           self.set_font("Helvetica", "I", 8)
           self.cell(0, 10, "Simulation — ne constitue pas un conseil financier", align="C")
   ```

7. **Chart in PDF:** For the wealth trajectory chart:
   - Option A: Use matplotlib to generate a PNG, embed in PDF (adds a dependency but clean output)
   - Option B: Draw the chart directly with fpdf2's drawing primitives (no dependency but more code)
   - Option C: Skip the chart in V1, just show the table (fastest to ship)
   
   Recommendation: Option C for V1, Option A for V2.

## Acceptance Criteria

- [ ] PDF generates successfully with all 3 pages
- [ ] Profile data, projection table, and configuration summary are accurate
- [ ] PDF is readable and professionally styled
- [ ] Download triggers correctly from the frontend
- [ ] File name includes the generation date
- [ ] Disclaimer footer appears on every page
- [ ] PDF file size < 2MB
- [ ] Works for users with minimal data (empty sections show "Non renseigné")
- [ ] LEARNINGS.md updated

## Notes

- The PDF disclaimer is important — "Simulation, ne constitue pas un conseil financier, fiscal ou juridique." This matches the in-app disclaimer.
- Consider adding a "share link" feature in a future sprint (generates a read-only URL with the projection snapshot). This is more modern than PDF but PDF is expected by bankers and accountants.
- Font embedding: fpdf2 supports TTF embedding. Include Inter and JetBrains Mono in the backend's static assets. If font embedding is too complex for V1, use Helvetica (built-in) and Courier (for monospace).
- The PDF should be generated server-side, not client-side. This ensures consistent output regardless of browser/device.
