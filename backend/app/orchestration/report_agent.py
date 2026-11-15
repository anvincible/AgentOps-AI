"""Build downloadable NovaMart business reports from trusted orchestration results."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from io import BytesIO
import math
import re
import textwrap
import unicodedata
from typing import Any, Callable
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile


AnswerFunction = Callable[[str], dict[str, Any]]


class ReportAgent:
    """Generate fixed-scope reports using existing SQL/RAG orchestration results."""

    REPORTS = {
        "business_performance": "NovaMart Business Performance Report",
        "sales_analysis": "NovaMart Sales Analysis Report",
        "campaign_performance": "NovaMart Campaign Performance Report",
    }
    MEDIA_TYPES = {
        "pdf": "application/pdf",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }

    def generate(
        self,
        report_type: str,
        file_format: str,
        answer_question: AnswerFunction,
    ) -> tuple[bytes, str, str]:
        if report_type not in self.REPORTS:
            raise ValueError("Unsupported report type.")
        if file_format not in self.MEDIA_TYPES:
            raise ValueError("Unsupported report format.")

        generated_at = datetime.now(timezone.utc)
        document = self._build_document(report_type, answer_question, generated_at)
        content = self._render_pdf(document) if file_format == "pdf" else self._render_xlsx(document)
        slug = report_type.replace("_", "-")
        filename = f"novamart-{slug}-{generated_at:%Y%m%d}.{file_format}"
        return content, filename, self.MEDIA_TYPES[file_format]

    def _build_document(
        self,
        report_type: str,
        answer_question: AnswerFunction,
        generated_at: datetime,
    ) -> dict[str, Any]:
        document: dict[str, Any] = {
            "title": self.REPORTS[report_type],
            "generated_at": generated_at.isoformat(timespec="seconds"),
            "executive_summary": [],
            "sections": [],
            "sources": [],
            "verification": [],
            "limitations": [],
        }

        if report_type == "business_performance":
            self._business_performance(document, answer_question)
        elif report_type == "sales_analysis":
            self._sales_analysis(document, answer_question)
        else:
            self._campaign_performance(document, answer_question)

        if not document["executive_summary"]:
            document["executive_summary"].append(
                "No validated structured results were available for this report."
            )
        if not document["sections"]:
            document["sections"].append({
                "title": "Available Data",
                "headers": ["Status"],
                "rows": [["No validated data rows were returned."]],
            })
        if not document["sources"]:
            document["sources"].append({
                "type": "source",
                "reference": "No validated data source was returned.",
                "status": "unavailable",
            })
        document["sections"].append({
            "title": "Sources and Verification",
            "headers": ["Type", "Reference", "Validation / verification"],
            "rows": [
                [item.get("type"), item.get("reference"), item.get("status")]
                for item in document["sources"]
            ] + [
                ["Verification", item.get("scope"), item.get("status")]
                for item in document["verification"]
            ],
        })
        document["sections"].append({
            "title": "Limitations and Unavailable Information",
            "headers": ["Limitation"],
            "rows": [[item] for item in dict.fromkeys(document["limitations"])]
            or [["No additional limitations were reported by the analysis pipeline."]],
        })
        return document

    def _business_performance(
        self, document: dict[str, Any], answer_question: AnswerFunction
    ) -> None:
        question = "Summarize NovaMart's business performance."
        response = self._ask(document, answer_question, question)
        if response is None:
            return
        analysis = response.get("analysis") or {}
        analysis_evidence = analysis.get("evidence") or {}
        area_results = {
            item.get("area"): item
            for item in analysis_evidence.get("results", [])
            if isinstance(item, dict) and item.get("validated") is True
        }
        components = analysis_evidence.get("components") or []
        component_by_area = {
            item.get("area"): item for item in components if isinstance(item, dict)
        }
        rows = []
        for area in ("Sales", "Customers", "Returns", "Campaigns"):
            component = component_by_area.get(area, {})
            area_result = area_results.get(area, {})
            values = area_result.get("values") or {}
            if values:
                for metric, value in values.items():
                    rows.append([area, metric.replace("_", " ").title(), value, component.get("status", "unavailable")])
            else:
                rows.append([area, "KPI data", "Unavailable", component.get("status", "unavailable")])
            intent = component.get("query_intent")
            if intent and component.get("sql_validated") is True:
                document["sources"].append({
                    "type": "SQL",
                    "reference": f"NovaMart PostgreSQL · {intent}",
                    "status": "validated" if component.get("result_nonempty") else "empty result",
                })
            if component.get("status") != "validated":
                document["limitations"].append(
                    f"{area} KPI component is {component.get('status', 'unavailable')}; it was not treated as a successful result."
                )

        document["sections"].append({
            "title": "Business KPI Summary",
            "headers": ["Business area", "Metric", "Returned value", "Component status"],
            "rows": rows,
        })
        if analysis.get("summary"):
            document["executive_summary"].append(analysis["summary"])
        summary_verification = (response.get("verification") or {}).get("business_summary") or {}
        self._append_insights(
            document,
            analysis.get("insights") or [],
            summary_verification.get("verified") is True,
        )
        document["limitations"].extend(analysis.get("limitations") or [])

        document["verification"].append({
            "scope": "All four business-summary SQL components and combined-analysis coverage metadata",
            "status": (
                "complete and consistent" if summary_verification.get("verified") is True
                else f"not fully verified; coverage={summary_verification.get('coverage_status', 'unknown')}; "
                     f"consistency checked={summary_verification.get('analysis_consistent', False)}"
            ),
        })
        for issue in summary_verification.get("issues") or []:
            document["limitations"].append(issue)
        document["limitations"].extend(
            f"{item.get('area')}: {item.get('status')}"
            for item in components
            if isinstance(item, dict) and item.get("status") != "validated"
        )

    def _sales_analysis(
        self, document: dict[str, Any], answer_question: AnswerFunction
    ) -> None:
        question = "Show the monthly revenue trend."
        response = self._ask(document, answer_question, question)
        if response is None:
            return
        sql_result = self._validated_sql(response)
        if sql_result:
            columns = sql_result["result"]["columns"]
            data_rows = list(sql_result["result"]["rows"])
            month_index = next((i for i, name in enumerate(columns) if str(name) in {"sales_month", "month"}), None)
            if month_index is not None:
                data_rows.sort(key=lambda row: str(row[month_index]))
            document["sections"].append({
                "title": "Monthly Sales Results",
                "headers": list(columns),
                "rows": [list(row) for row in data_rows],
            })
            self._add_sql_source(document, response, sql_result)
        analysis = response.get("analysis") or {}
        self._append_insights(
            document, analysis.get("insights") or [],
            (response.get("verification") or {}).get("verified") is True,
        )
        document["limitations"].extend(analysis.get("limitations") or [])
        self._add_answer_verification(document, response, "Monthly revenue SQL result and analysis")

    def _campaign_performance(
        self, document: dict[str, Any], answer_question: AnswerFunction
    ) -> None:
        queries = (
            ("Show campaign performance.", "Aggregate Campaign Overview"),
            ("Rank campaigns by ROI.", "Top Campaigns by ROI (returned ranking rows)"),
        )
        for question, section_title in queries:
            response = self._ask(document, answer_question, question)
            if response is None:
                continue
            sql_result = self._validated_sql(response)
            if sql_result:
                result = sql_result["result"]
                document["sections"].append({
                    "title": section_title,
                    "headers": list(result["columns"]),
                    "rows": [list(row) for row in result["rows"]],
                })
                self._add_sql_source(document, response, sql_result)
            analysis = response.get("analysis") or {}
            self._append_insights(
                document, analysis.get("insights") or [],
                (response.get("verification") or {}).get("verified") is True,
            )
            document["limitations"].extend(analysis.get("limitations") or [])
            self._add_answer_verification(document, response, section_title)

    def _ask(
        self,
        document: dict[str, Any],
        answer_question: AnswerFunction,
        question: str,
    ) -> dict[str, Any] | None:
        try:
            response = answer_question(question)
        except Exception:
            document["limitations"].append(
                f"The report could not retrieve results for the predefined query: {question}"
            )
            document["verification"].append({
                "scope": question,
                "status": "query failed; no results included",
            })
            return None
        if response.get("route") != "SQL":
            document["limitations"].append(
                f"The predefined report query did not return a structured SQL route ({response.get('route', 'unknown')})."
            )
        elif self._validated_sql(response) is None and not response.get("analysis"):
            document["limitations"].append(
                f"No nonempty SQL result passed validation for the predefined report query: {question}"
            )
        return response

    @staticmethod
    def _append_insights(
        document: dict[str, Any], insights: list[str], verified: bool
    ) -> None:
        if verified:
            document["executive_summary"].extend(insights)
        else:
            document["executive_summary"].extend(
                f"Not fully verified: {insight}" for insight in insights
            )

    @staticmethod
    def _validated_sql(response: dict[str, Any]) -> dict[str, Any] | None:
        result = response.get("sql")
        if not isinstance(result, dict):
            return None
        validation = result.get("validation")
        data = result.get("result")
        if (
            not isinstance(validation, dict)
            or validation.get("valid") is not True
            or not isinstance(data, dict)
            or not data.get("columns")
            or not data.get("rows")
        ):
            return None
        return result

    @staticmethod
    def _add_sql_source(
        document: dict[str, Any],
        response: dict[str, Any],
        sql_result: dict[str, Any],
    ) -> None:
        intent = (sql_result.get("query_plan") or {}).get("intent", "unknown intent")
        document["sources"].append({
            "type": "SQL",
            "reference": f"NovaMart PostgreSQL · {intent}",
            "status": "SQL validated; answer verified" if (response.get("verification") or {}).get("verified") is True
            else "SQL validated; final answer verification incomplete",
        })

    @staticmethod
    def _add_answer_verification(
        document: dict[str, Any], response: dict[str, Any], scope: str
    ) -> None:
        verification = response.get("verification") or {}
        document["verification"].append({
            "scope": scope,
            "status": "verified" if verification.get("verified") is True else "not verified",
        })
        if verification.get("verified") is not True:
            document["limitations"].extend(verification.get("issues") or [
                f"Verification was incomplete for {scope}."
            ])

    @staticmethod
    def _table_text(section: dict[str, Any]) -> list[tuple[str, bool, int]]:
        lines: list[tuple[str, bool, int]] = []
        title = str(section.get("title", "Data"))
        lines.append((title, True, 13))
        headers = [str(value) for value in section.get("headers") or []]
        if headers:
            lines.append((" | ".join(headers), True, 9))
            lines.append(("-" * min(105, max(24, len(" | ".join(headers)))), False, 8))
        for row in section.get("rows") or []:
            values = [ReportAgent._display_value(value) for value in row]
            lines.append((" | ".join(values), False, 8))
        lines.append(("", False, 8))
        return lines

    @staticmethod
    def _display_value(value: Any) -> str:
        if value is None:
            return "Unavailable"
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return format(value, "f")
        return str(value)

    def _render_pdf(self, document: dict[str, Any]) -> bytes:
        lines: list[tuple[str, bool, int]] = [
            (document["title"], True, 18),
            (f"Generated: {document['generated_at']} UTC", False, 9),
            ("", False, 9),
            ("Executive Summary", True, 13),
        ]
        for summary in document["executive_summary"]:
            lines.extend((line, False, 10) for line in self._wrap(summary, 92))
        lines.append(("", False, 9))
        for section in document["sections"]:
            for text, bold, size in self._table_text(section):
                lines.extend((line, bold, size) for line in self._wrap(text, 92))

        pages: list[bytes] = []
        per_page = 48
        chunks = [lines[index:index + per_page] for index in range(0, len(lines), per_page)] or [[]]
        for page_number, page_lines in enumerate(chunks, start=1):
            commands = []
            y = 752
            for text, bold, size in page_lines:
                if y < 40:
                    break
                clean = self._pdf_safe_text(text)
                encoded = clean.encode("ascii", "replace").hex().upper()
                font = "F2" if bold else "F1"
                commands.append(f"BT /{font} {size} Tf 48 {y} Td <{encoded}> Tj ET")
                y -= 14 if size < 14 else 20
            footer = f"Page {page_number} of {len(chunks)}"
            commands.append(f"BT /F1 8 Tf 500 24 Td <{footer.encode('ascii').hex().upper()}> Tj ET")
            pages.append("\n".join(commands).encode("ascii"))
        return self._assemble_pdf(pages)

    @classmethod
    def _assemble_pdf(cls, page_contents: list[bytes]) -> bytes:
        objects: list[bytes] = [b""]
        objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
        page_ids = [5 + index * 2 for index in range(len(page_contents))]
        kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
        objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode("ascii"))
        objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
        objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
        for index, content in enumerate(page_contents):
            page_id = 5 + index * 2
            content_id = page_id + 1
            objects.append(
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {content_id} 0 R >>".encode("ascii")
            )
            objects.append(
                f"<< /Length {len(content)} >>\nstream\n".encode("ascii")
                + content + b"\nendstream"
            )
        output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for index, body in enumerate(objects[1:], start=1):
            offsets.append(len(output))
            output.extend(f"{index} 0 obj\n".encode("ascii"))
            output.extend(body)
            output.extend(b"\nendobj\n")
        xref_offset = len(output)
        output.extend(f"xref\n0 {len(objects)}\n0000000000 65535 f \n".encode("ascii"))
        for offset in offsets[1:]:
            output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
        output.extend(
            f"trailer\n<< /Size {len(objects)} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
        )
        return bytes(output)

    def _render_xlsx(self, document: dict[str, Any]) -> bytes:
        sheets: list[tuple[str, list[list[Any]]]] = []
        summary_rows: list[list[Any]] = [
            [document["title"]],
            ["Generated (UTC)", document["generated_at"]],
            ["Executive Summary"],
        ]
        summary_rows.extend([[item] for item in document["executive_summary"]])
        sheets.append(("Executive Summary", summary_rows))
        used_names = {"Executive Summary"}
        for section in document["sections"]:
            title = str(section.get("title", "Data"))
            sheet_name = self._sheet_name(title, used_names)
            used_names.add(sheet_name)
            rows = [[title], list(section.get("headers") or [])]
            rows.extend([list(row) for row in section.get("rows") or []])
            sheets.append((sheet_name, rows))
        return self._assemble_xlsx(sheets)

    @staticmethod
    def _sheet_name(title: str, used_names: set[str]) -> str:
        base = re.sub(r"[\\/*?:\[\]]", " ", title).strip()[:31] or "Data"
        candidate = base
        suffix = 2
        while candidate.casefold() in {name.casefold() for name in used_names}:
            tail = f" {suffix}"
            candidate = base[:31 - len(tail)] + tail
            suffix += 1
        return candidate

    @classmethod
    def _assemble_xlsx(cls, sheets: list[tuple[str, list[list[Any]]]]) -> bytes:
        main_ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
        rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
        package_rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
        content_ns = "http://schemas.openxmlformats.org/package/2006/content-types"
        ET.register_namespace("", main_ns)
        ET.register_namespace("r", rel_ns)

        content_types = ET.Element(f"{{{content_ns}}}Types")
        ET.SubElement(content_types, f"{{{content_ns}}}Default", Extension="rels", ContentType="application/vnd.openxmlformats-package.relationships+xml")
        ET.SubElement(content_types, f"{{{content_ns}}}Default", Extension="xml", ContentType="application/xml")
        ET.SubElement(content_types, f"{{{content_ns}}}Override", PartName="/xl/workbook.xml", ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml")
        ET.SubElement(content_types, f"{{{content_ns}}}Override", PartName="/xl/styles.xml", ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml")
        for index in range(len(sheets)):
            ET.SubElement(content_types, f"{{{content_ns}}}Override", PartName=f"/xl/worksheets/sheet{index + 1}.xml", ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml")

        package_rels = ET.Element(f"{{{package_rel_ns}}}Relationships")
        ET.SubElement(package_rels, f"{{{package_rel_ns}}}Relationship", Id="rId1", Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument", Target="xl/workbook.xml")

        workbook = ET.Element(f"{{{main_ns}}}workbook")
        book_sheets = ET.SubElement(workbook, f"{{{main_ns}}}sheets")
        workbook_rels = ET.Element(f"{{{package_rel_ns}}}Relationships")
        for index, (name, _) in enumerate(sheets, start=1):
            ET.SubElement(book_sheets, f"{{{main_ns}}}sheet", {
                "name": name, "sheetId": str(index), f"{{{rel_ns}}}id": f"rId{index}",
            })
            ET.SubElement(workbook_rels, f"{{{package_rel_ns}}}Relationship", {
                "Id": f"rId{index}",
                "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet",
                "Target": f"worksheets/sheet{index}.xml",
            })
        ET.SubElement(workbook_rels, f"{{{package_rel_ns}}}Relationship", {
            "Id": f"rId{len(sheets) + 1}",
            "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles",
            "Target": "styles.xml",
        })

        styles = cls._xlsx_styles(main_ns)
        output = BytesIO()
        with ZipFile(output, "w", ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml", ET.tostring(content_types, encoding="utf-8", xml_declaration=True))
            archive.writestr("_rels/.rels", ET.tostring(package_rels, encoding="utf-8", xml_declaration=True))
            archive.writestr("xl/workbook.xml", ET.tostring(workbook, encoding="utf-8", xml_declaration=True))
            archive.writestr("xl/_rels/workbook.xml.rels", ET.tostring(workbook_rels, encoding="utf-8", xml_declaration=True))
            archive.writestr("xl/styles.xml", ET.tostring(styles, encoding="utf-8", xml_declaration=True))
            for index, (_, rows) in enumerate(sheets, start=1):
                worksheet = cls._worksheet_xml(rows, main_ns)
                archive.writestr(f"xl/worksheets/sheet{index}.xml", ET.tostring(worksheet, encoding="utf-8", xml_declaration=True))
        return output.getvalue()

    @staticmethod
    def _xlsx_styles(namespace: str) -> ET.Element:
        root = ET.Element(f"{{{namespace}}}styleSheet")
        fonts = ET.SubElement(root, f"{{{namespace}}}fonts", count="2")
        for bold in (False, True):
            font = ET.SubElement(fonts, f"{{{namespace}}}font")
            if bold:
                ET.SubElement(font, f"{{{namespace}}}b")
            ET.SubElement(font, f"{{{namespace}}}sz", val="11")
            ET.SubElement(font, f"{{{namespace}}}name", val="Calibri")
        fills = ET.SubElement(root, f"{{{namespace}}}fills", count="2")
        ET.SubElement(ET.SubElement(fills, f"{{{namespace}}}fill"), f"{{{namespace}}}patternFill", patternType="none")
        ET.SubElement(ET.SubElement(fills, f"{{{namespace}}}fill"), f"{{{namespace}}}patternFill", patternType="gray125")
        borders = ET.SubElement(root, f"{{{namespace}}}borders", count="1")
        border = ET.SubElement(borders, f"{{{namespace}}}border")
        for edge in ("left", "right", "top", "bottom", "diagonal"):
            ET.SubElement(border, f"{{{namespace}}}{edge}")
        cell_style_xfs = ET.SubElement(root, f"{{{namespace}}}cellStyleXfs", count="1")
        ET.SubElement(cell_style_xfs, f"{{{namespace}}}xf", numFmtId="0", fontId="0", fillId="0", borderId="0")
        cell_xfs = ET.SubElement(root, f"{{{namespace}}}cellXfs", count="2")
        ET.SubElement(cell_xfs, f"{{{namespace}}}xf", numFmtId="0", fontId="0", fillId="0", borderId="0", xfId="0")
        ET.SubElement(cell_xfs, f"{{{namespace}}}xf", numFmtId="0", fontId="1", fillId="0", borderId="0", xfId="0", applyFont="1")
        cell_styles = ET.SubElement(root, f"{{{namespace}}}cellStyles", count="1")
        ET.SubElement(cell_styles, f"{{{namespace}}}cellStyle", name="Normal", xfId="0", builtinId="0")
        return root

    @classmethod
    def _worksheet_xml(cls, rows: list[list[Any]], namespace: str) -> ET.Element:
        root = ET.Element(f"{{{namespace}}}worksheet")
        sheet_data = ET.SubElement(root, f"{{{namespace}}}sheetData")
        for row_number, values in enumerate(rows, start=1):
            row_node = ET.SubElement(sheet_data, f"{{{namespace}}}row", r=str(row_number))
            for column_number, value in enumerate(values, start=1):
                if value is None:
                    continue
                reference = f"{cls._column_name(column_number)}{row_number}"
                cell = ET.SubElement(row_node, f"{{{namespace}}}c", r=reference)
                if row_number <= 2:
                    cell.set("s", "1")
                value = cls._excel_value(value)
                if isinstance(value, bool):
                    cell.set("t", "b")
                    ET.SubElement(cell, f"{{{namespace}}}v").text = "1" if value else "0"
                elif isinstance(value, (int, float)) and not isinstance(value, bool):
                    ET.SubElement(cell, f"{{{namespace}}}v").text = str(value)
                else:
                    cell.set("t", "inlineStr")
                    inline = ET.SubElement(cell, f"{{{namespace}}}is")
                    text_node = ET.SubElement(inline, f"{{{namespace}}}t")
                    text_node.text = str(value)
                    if text_node.text.startswith(" ") or text_node.text.endswith(" "):
                        text_node.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        return root

    @staticmethod
    def _excel_value(value: Any) -> Any:
        if isinstance(value, Decimal):
            number = float(value)
            return number if math.isfinite(number) else str(value)
        if isinstance(value, float) and not math.isfinite(value):
            return str(value)
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        return value

    @staticmethod
    def _column_name(number: int) -> str:
        result = ""
        while number:
            number, remainder = divmod(number - 1, 26)
            result = chr(65 + remainder) + result
        return result

    @staticmethod
    def _wrap(text: str, width: int) -> list[str]:
        if not text:
            return [""]
        return textwrap.wrap(text, width=width, break_long_words=True, break_on_hyphens=False) or [""]

    @staticmethod
    def _pdf_safe_text(value: str) -> str:
        text = str(value).replace("₹", "INR ").replace("—", "-").replace("–", "-").replace("·", "-")
        text = unicodedata.normalize("NFKD", text)
        return text.encode("ascii", "replace").decode("ascii")
