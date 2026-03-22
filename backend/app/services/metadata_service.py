from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

from ebooklib import epub
from pypdf import PdfReader


@dataclass
class ExtractedMetadata:
    title: str | None = None
    author: str | None = None
    series: str | None = None


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).strip().split())
    return normalized or None


def _from_epub(path: Path) -> ExtractedMetadata:
    book = epub.read_epub(str(path))

    title = None
    title_meta = book.get_metadata("DC", "title") or []
    if title_meta:
        title = _clean(title_meta[0][0])

    author = None
    author_meta = book.get_metadata("DC", "creator") or []
    if author_meta:
        author = _clean(author_meta[0][0])

    series = None
    opf_meta = book.get_metadata("OPF", "meta") or []
    for entry in opf_meta:
        attrs = entry[1] if len(entry) > 1 and isinstance(entry[1], dict) else {}
        name = str(attrs.get("name", "")).lower()
        if name in {"calibre:series", "belongs-to-collection"}:
            series = _clean(attrs.get("content") or attrs.get("title"))
            if series:
                break

    return ExtractedMetadata(title=title, author=author, series=series)


def _from_fb2(path: Path) -> ExtractedMetadata:
    tree = ET.parse(path)
    root = tree.getroot()
    ns = {"fb2": "http://www.gribuser.ru/xml/fictionbook/2.0"}

    title_node = root.find(".//fb2:description/fb2:title-info/fb2:book-title", ns)
    title = _clean(title_node.text if title_node is not None else None)

    author_node = root.find(".//fb2:description/fb2:title-info/fb2:author", ns)
    author = None
    if author_node is not None:
        first = _clean((author_node.findtext("fb2:first-name", default="", namespaces=ns) or "").strip())
        middle = _clean((author_node.findtext("fb2:middle-name", default="", namespaces=ns) or "").strip())
        last = _clean((author_node.findtext("fb2:last-name", default="", namespaces=ns) or "").strip())
        nickname = _clean((author_node.findtext("fb2:nickname", default="", namespaces=ns) or "").strip())
        parts = [x for x in [first, middle, last] if x]
        author = _clean(" ".join(parts)) or nickname

    seq_node = root.find(".//fb2:description/fb2:title-info/fb2:sequence", ns)
    series = _clean(seq_node.attrib.get("name") if seq_node is not None else None)

    return ExtractedMetadata(title=title, author=author, series=series)


def _from_pdf(path: Path) -> ExtractedMetadata:
    reader = PdfReader(str(path))
    meta = reader.metadata or {}
    title = _clean(getattr(meta, "title", None) or meta.get("/Title"))
    author = _clean(getattr(meta, "author", None) or meta.get("/Author"))
    return ExtractedMetadata(title=title, author=author, series=None)


def extract_metadata(path: Path, file_type: str) -> ExtractedMetadata:
    try:
        if file_type == "epub":
            return _from_epub(path)
        if file_type == "fb2":
            return _from_fb2(path)
        if file_type == "pdf":
            return _from_pdf(path)
    except Exception:
        return ExtractedMetadata()
    return ExtractedMetadata()
