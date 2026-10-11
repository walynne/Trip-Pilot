"""Read the approved local DOCX into citation-bearing evidence chunks."""

from hashlib import sha256
from io import BytesIO
from pathlib import Path
import re
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
MAX_DOCUMENT_BYTES = 10_000_000


class PolicyRetrievalError(ValueError):
    """Safe, identifiable B2 failure; never contains document contents."""

    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def _text(node):
    # Preserve paragraph boundaries in cells and spaces between explicit breaks.
    paragraphs = [node] if node.tag == W + "p" else node.findall(".//" + W + "p")
    lines = []
    for paragraph in paragraphs:
        parts = []
        for child in paragraph.iter():
            if child.tag == W + "t":
                parts.append(child.text or "")
            elif child.tag in {W + "tab", W + "br", W + "cr"}:
                parts.append(" ")
        lines.append("".join(parts).strip())
    return "\n".join(line for line in lines if line)


def load_policy(document_path, expected_version="2.0"):
    """Load one local baseline. Citations use 1-based body blocks/table rows.

    This deliberately supports ordinary Word paragraphs and rectangular tables,
    not tracked revisions, merged/nested tables or automatic heading numbering.
    Unsupported structures fail explicitly rather than silently losing evidence.
    """
    if not isinstance(document_path, (str, Path)) or not str(document_path).strip():
        raise PolicyRetrievalError("invalid_source", "A local DOCX path is required.")
    if not isinstance(expected_version, str) or not expected_version.strip():
        raise PolicyRetrievalError("invalid_version", "An expected policy version is required.")
    path = Path(document_path)
    if path.suffix.lower() != ".docx":
        raise PolicyRetrievalError("invalid_source", "The source must be a DOCX document.")
    try:
        if path.stat().st_size > MAX_DOCUMENT_BYTES:
            raise PolicyRetrievalError("invalid_document", "Policy document exceeds the size limit.")
        data = path.read_bytes()
        with ZipFile(BytesIO(data)) as archive:
            info = archive.getinfo("word/document.xml")
            if info.file_size > MAX_DOCUMENT_BYTES:
                raise PolicyRetrievalError("invalid_document", "Policy XML exceeds the size limit.")
            xml = archive.read(info)
        if b"<!DOCTYPE" in xml or b"<!ENTITY" in xml:
            raise PolicyRetrievalError("invalid_document", "XML declarations are unsupported.")
        root = ET.fromstring(xml)
    except FileNotFoundError as exc:
        raise PolicyRetrievalError("source_not_found", "The local policy source is missing.") from exc
    except (OSError, BadZipFile, KeyError, ET.ParseError) as exc:
        raise PolicyRetrievalError("invalid_document", "The policy DOCX could not be read.") from exc

    body = root.find(W + "body")
    if body is None:
        raise PolicyRetrievalError("invalid_document", "The document has no Word body.")
    if any(root.find(".//" + W + tag) is not None
           for tag in ("ins", "del", "moveFrom", "moveTo", "vMerge", "gridSpan", "txbxContent")):
        raise PolicyRetrievalError("unsupported_document", "Revisions, merged cells or text boxes are unsupported.")

    versions = []
    for table in body.findall(W + "tbl"):
        for row in table.findall(W + "tr"):
            cells = [_text(cell) for cell in row.findall(W + "tc")]
            if cells and cells[0].casefold() == "version":
                if len(cells) != 2:
                    raise PolicyRetrievalError("invalid_version", "Policy version metadata is malformed.")
                match = re.match(r"^(\d+\.\d+)(?:\s|$)", cells[1])
                if not match:
                    raise PolicyRetrievalError("invalid_version", "Policy version metadata is malformed.")
                versions.append(match.group(1))
    if versions != [expected_version]:
        raise PolicyRetrievalError("version_mismatch", "Source version does not match the expected baseline.")

    chunks = []
    sections = []
    section_references = []
    pending = []
    table_number = 0

    def emit(text, references, kind):
        if text:
            chunks.append({"chunk_id": f"chunk-{len(chunks) + 1:04d}",
                           "section": " > ".join(sections) or "Document preamble",
                           "section_references": list(section_references),
                           "kind": kind, "text": text, "references": references})

    def flush():
        if pending:
            emit("\n".join(text for text, _ in pending), [ref for _, ref in pending], "paragraphs")
            pending.clear()

    for block, node in enumerate(body, 1):
        if node.tag == W + "p":
            text = _text(node)
            style = node.find(W + "pPr/" + W + "pStyle")
            style_name = style.get(W + "val", "") if style is not None else ""
            heading = re.fullmatch(r"Heading([1-6])", style_name, re.IGNORECASE)
            if heading:
                if node.find(W + "pPr/" + W + "numPr") is not None:
                    raise PolicyRetrievalError("unsupported_document", "Automatically numbered headings are unsupported.")
                flush()
                level = int(heading.group(1))
                sections = sections[:level - 1] + [text]
                section_references = section_references[:level - 1] + [
                    {"body_block": block, "type": "heading"}]
            elif text:
                # The contents list is navigation, not policy evidence.
                if sections == ["Contents"]:
                    continue
                if sum(len(t) for t, _ in pending) + len(text) > 1800:
                    flush()
                pending.append((text, {"body_block": block, "type": "paragraph"}))
        elif node.tag == W + "tbl":
            flush()
            table_number += 1
            if node.find(".//" + W + "tbl") is not None:
                raise PolicyRetrievalError("unsupported_document", "Nested tables are unsupported.")
            rows = node.findall(W + "tr")
            cells = [[_text(cell) for cell in row.findall(W + "tc")] for row in rows]
            if not cells or not cells[0] or any(len(row) != len(cells[0]) for row in cells):
                raise PolicyRetrievalError("invalid_document", "The policy contains an irregular table.")
            # Preamble metadata is a key/value table, not a rule table.
            if not sections:
                emit("\n".join(" | ".join(row) for row in cells),
                     [{"body_block": block, "type": "table", "table": table_number}], "metadata")
                continue
            for row_number, row in enumerate(cells[1:], 2):
                emit("\n".join(f"{header}: {value}" for header, value in zip(cells[0], row)),
                     [{"body_block": block, "type": "table_row", "table": table_number,
                       "row": row_number, "header_row": 1}], "table_row")
        elif node.tag != W + "sectPr":
            raise PolicyRetrievalError("unsupported_document", "Unsupported content in the document body.")
    flush()
    if not chunks:
        raise PolicyRetrievalError("invalid_document", "The document contains no policy evidence.")
    # Attach neighboring prose in the SAME subsection to each table row. It may
    # qualify amounts; do not make a retrieved row look like a complete rule.
    for chunk in chunks:
        chunk["context"] = [
            {"text": other["text"], "references": other["references"]}
            for other in chunks if other["section"] == chunk["section"]
            and other["kind"] == "paragraphs" and other is not chunk
        ] if chunk["kind"] == "table_row" else []
    return {"source": path.name, "policy_version": versions[0],
            "document_sha256": sha256(data).hexdigest(), "chunks": chunks}
