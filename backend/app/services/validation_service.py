from collections import defaultdict
import re
import unicodedata
from typing import Dict, List

from rapidfuzz import fuzz
from app.models import Document

DEFAULT_RULES = [
    {"field": "consignee", "rule": "fuzzy_equal", "threshold": 88, "severity": "ERROR"},
    {"field": "packages", "rule": "must_be_equal", "severity": "ERROR"},
    {"field": "gross_weight", "rule": "must_be_equal", "tolerance": 5, "severity": "ERROR"},
    {"field": "commercial_weight", "rule": "must_be_equal", "tolerance": 5, "severity": "ERROR"},
    {"field": "transport_unit_number", "rule": "must_be_equal", "severity": "ERROR"},
    {"field": "incoterm", "rule": "must_be_equal", "severity": "ERROR"},
    {"field": "destination", "rule": "fuzzy_equal", "threshold": 90, "severity": "ERROR"},
    {"field": "transport_type", "rule": "must_be_equal", "severity": "ERROR"},
]

REQUIRED_FIELDS_BY_DOC_TYPE = {
    "CC": ["consignee", "packages", "gross_weight", "destination"],
    "INVOICE": ["consignee", "commercial_weight", "destination"],
    "BC": ["consignee", "packages", "destination"],
    "PHYTO": ["consignee", "destination", "transport_type"],
}


def _normalized(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip().lower()
    if isinstance(value, float):
        return round(value, 3)
    return value


def _fuzzy_consistent(values: list[str], threshold: int) -> bool:
    base = values[0]
    return all(fuzz.ratio(base, value) >= threshold for value in values[1:])


def _normalize_str(value: str) -> str:
    value = (value or "").strip().lower()
    normalized = unicodedata.normalize("NFD", value)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def _parse_critical_values(doc: Document) -> dict[str, str | float | int | None]:
    text = doc.raw_text or ""
    normalized = _normalize_str(text)

    def search(pattern: str) -> str | None:
        m = re.search(pattern, normalized, re.IGNORECASE | re.MULTILINE)
        return m.group(1).strip() if m else None

    def search_int(pattern: str) -> int | None:
        value = search(pattern)
        if not value:
            return None
        digits = re.sub(r"[^0-9]", "", value)
        return int(digits) if digits else None

    def search_float(pattern: str) -> float | None:
        value = search(pattern)
        if not value:
            return None
        cleaned = re.sub(r"[^0-9,\.]", "", value).replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return None

    return {
        "exporter_name": search(r"(?:exporter|shipper|consignor|expediteur)\s*[:\-]?\s*(.+)"),
        "importer_name": search(r"(?:importer|importateur|consignee|notify)\s*[:\-]?\s*(.+)"),
        "container_number": search(r"(?:container\s*(?:number|no)?|transport\s+unit\s+number)\s*[:\-]?\s*([a-z0-9\-/]+)"),
        "packages_checked": doc.packages
        if doc.packages is not None
        else search_int(r"(?:number\s+of\s+packages|packages|nombre\s+de\s+colis|boxes)\s*[:\-]?\s*([0-9\., ]+)"),
        "net_weight_checked": doc.commercial_weight
        if doc.commercial_weight is not None
        else search_float(r"(?:net\s+weight|poids\s+net)\s*[:\-]?\s*([0-9\., ]+)"),
        "gross_weight_checked": doc.gross_weight
        if doc.gross_weight is not None
        else search_float(r"(?:gross\s+weight|poids\s+brut)\s*[:\-]?\s*([0-9\., ]+)"),
        "product_name": search(r"(?:product|commodity|description|goods|produit)\s*[:\-]?\s*(.+)"),
        "botanical_variety": search(r"\b(citrus\s+clementina|nadorcott|mandarines?|clementines?)\b"),
    }


def _compare_critical_field(
    issues: list[dict],
    status: str,
    field: str,
    label: str,
    values_by_doc: dict[str, str],
    threshold: int = 90,
) -> str:
    non_empty = {doc: val for doc, val in values_by_doc.items() if str(val or "").strip()}
    if len(non_empty) < 2:
        if non_empty:
            issues.append(
                {
                    "field": field,
                    "level": "WARNING",
                    "message": f"{label} partiellement extrait",
                    "values": values_by_doc,
                }
            )
            if status == "VALID":
                status = "WARNING"
            return status
        issues.append(
            {
                "field": field,
                "level": "WARNING",
                "message": f"{label} non extrait",
                "values": values_by_doc,
            }
        )
        return "WARNING" if status == "VALID" else status
    values = list(non_empty.values())
    base = values[0]
    if not all(fuzz.ratio(base, candidate) >= threshold for candidate in values[1:]):
        issues.append(
            {
                "field": field,
                "level": "ERROR",
                "message": f"Incoherence detectee sur {label}",
                "values": values_by_doc,
            }
        )
        return "INCONSISTENT"
    issues.append(
        {
            "field": field,
            "level": "OK",
            "message": f"{label} coherent sur les documents",
            "values": values_by_doc,
        }
    )
    return status


def validate_consistency(documents: List[Document], rules: list[dict] | None = None) -> Dict[str, object]:
    issues = []
    status = "VALID"
    rules = rules or DEFAULT_RULES
    checks_by_document: Dict[str, Dict[str, str]] = {}
    checks_by_tc: Dict[str, Dict[str, str]] = {}

    fields_for_transport = [
        "consignee",
        "packages",
        "gross_weight",
        "commercial_weight",
        "transport_unit_number",
        "incoterm",
        "destination",
        "transport_type",
    ]

    # Validation de structure par type de document.
    for doc in documents:
        doc_checks = {}
        has_readable_text = bool((doc.raw_text or "").strip())
        required = REQUIRED_FIELDS_BY_DOC_TYPE.get(doc.doc_type, [])
        for field in required:
            value = getattr(doc, field, None)
            if value in (None, ""):
                doc_checks[field] = "MANQUANT"
                level = "WARNING" if not has_readable_text else "ERROR"
                message = (
                    f"Lecture impossible: champ non extrait dans {doc.doc_type}"
                    if not has_readable_text
                    else f"Structure invalide: champ obligatoire manquant dans {doc.doc_type}"
                )
                issues.append(
                    {
                        "field": field,
                        "level": level,
                        "message": message,
                        "values": {doc.doc_type: ""},
                    }
                )
                if level == "ERROR":
                    status = "INCONSISTENT"
                elif status == "VALID":
                    status = "WARNING"
            else:
                doc_checks[field] = "OK"

        # Verification de forme juridique minimale (presence d'en-tete de type de document).
        text_blob = (doc.raw_text or "").lower()
        legal_markers = {
            "INVOICE": ["invoice", "facture"],
            "CC": ["certificate", "conformity", "certificat"],
            "BC": ["purchase order", "bon de commande", "commande"],
            "PHYTO": ["phytosanitary", "phyto", "phytosanitaire"],
        }
        markers = legal_markers.get(doc.doc_type, [])
        if markers and not any(marker in text_blob for marker in markers):
            doc_checks["document_legal_form"] = "INVALIDE"
            level = "WARNING" if not has_readable_text else "ERROR"
            message = (
                f"Lecture impossible: en-tete {doc.doc_type} non verifiable"
                if not has_readable_text
                else f"Forme juridique invalide: en-tete {doc.doc_type} non detecte"
            )
            issues.append(
                {
                    "field": "document_legal_form",
                    "level": level,
                    "message": message,
                    "values": {doc.doc_type: "header_missing"},
                }
            )
            if level == "ERROR":
                status = "INCONSISTENT"
            elif status == "VALID":
                status = "WARNING"
        else:
            doc_checks["document_legal_form"] = "OK"
        checks_by_document[doc.doc_type] = doc_checks

    critical_values = {doc.doc_type: _parse_critical_values(doc) for doc in documents}
    status = _compare_critical_field(
        issues,
        status,
        "exporter_name",
        "Exportateur",
        {doc_type: str(values.get("exporter_name") or "") for doc_type, values in critical_values.items()},
        threshold=92,
    )
    status = _compare_critical_field(
        issues,
        status,
        "importer_name",
        "Importateur",
        {doc_type: str(values.get("importer_name") or "") for doc_type, values in critical_values.items()},
        threshold=92,
    )
    status = _compare_critical_field(
        issues,
        status,
        "container_number",
        "Numero de conteneur",
        {doc_type: str(values.get("container_number") or "") for doc_type, values in critical_values.items()},
        threshold=100,
    )

    for field_name, label in [
        ("packages_checked", "Nombre de colis"),
        ("net_weight_checked", "Poids net"),
        ("gross_weight_checked", "Poids brut"),
    ]:
        numeric_values = {doc_type: values.get(field_name) for doc_type, values in critical_values.items()}
        available = [float(v) for v in numeric_values.values() if v not in (None, "")]
        if not available:
            issues.append(
                {
                    "field": field_name,
                    "level": "WARNING",
                    "message": f"{label} non extrait",
                    "values": {k: "" if v is None else str(v) for k, v in numeric_values.items()},
                }
            )
            if status == "VALID":
                status = "WARNING"
        elif max(available) - min(available) > 5.0:
            issues.append(
                {
                    "field": field_name,
                    "level": "ERROR",
                    "message": f"Incoherence detectee sur {label}",
                    "values": {k: "" if v is None else str(v) for k, v in numeric_values.items()},
                }
            )
            status = "INCONSISTENT"
        else:
            issues.append(
                {
                    "field": field_name,
                    "level": "OK",
                    "message": f"{label} coherent",
                    "values": {k: "" if v is None else str(v) for k, v in numeric_values.items()},
                }
            )

    phyto_variety = None
    other_varieties = []
    values_map = {}
    for doc in documents:
        variety = str(critical_values.get(doc.doc_type, {}).get("botanical_variety") or "").strip()
        values_map[doc.doc_type] = variety
        if not variety:
            continue
        if doc.doc_type == "PHYTO":
            phyto_variety = _normalize_str(variety)
        else:
            other_varieties.append(_normalize_str(variety))
    if phyto_variety and other_varieties and not all(fuzz.ratio(phyto_variety, v) >= 90 for v in other_varieties):
        issues.append(
            {
                "field": "product_variety",
                "level": "ERROR",
                "message": "Alerte conformite: variete botanique incoherente entre PHYTO et autres documents",
                "values": values_map,
            }
        )
        status = "INCONSISTENT"
    else:
        issues.append(
            {
                "field": "product_variety",
                "level": "OK" if phyto_variety else "WARNING",
                "message": "Variete botanique coherente" if phyto_variety else "Variete botanique non extraite",
                "values": values_map,
            }
        )
        if not phyto_variety and status == "VALID":
            status = "WARNING"

    for rule in rules:
        field = rule["field"]
        seen = defaultdict(list)
        missing_docs = []

        for doc in documents:
            value = getattr(doc, field)
            normalized = _normalized(value)
            if normalized in (None, ""):
                missing_docs.append(doc.doc_type)
            else:
                seen[normalized].append(doc.doc_type)

        if missing_docs:
            issues.append(
                {
                    "field": field,
                    "level": "WARNING",
                    "message": f"Missing field in: {', '.join(sorted(missing_docs))}",
                    "values": {d.doc_type: str(getattr(d, field) or "") for d in documents},
                }
            )
            if status == "VALID":
                status = "WARNING"

        values = [str(k) for k in seen.keys()]
        is_mismatch = len(seen.keys()) > 1
        if rule["rule"] == "must_be_equal" and "tolerance" in rule and values:
            try:
                nums = [float(v) for v in values]
                is_mismatch = (max(nums) - min(nums)) > float(rule["tolerance"])
            except ValueError:
                is_mismatch = len(seen.keys()) > 1
        elif rule["rule"] == "fuzzy_equal" and values:
            is_mismatch = not _fuzzy_consistent(values, int(rule.get("threshold", 90)))

        if is_mismatch:
            issues.append(
                {
                    "field": field,
                    "level": rule.get("severity", "ERROR"),
                    "message": "Different values across documents",
                    "values": {d.doc_type: str(getattr(d, field) or "") for d in documents},
                }
            )
            status = "INCONSISTENT"

    # Group checks by TC (transport unit).
    for doc in documents:
        tc = (doc.transport_unit_number or "").strip() or "TC_INCONNU"
        if tc not in checks_by_tc:
            checks_by_tc[tc] = {}
        for field in fields_for_transport:
            value = getattr(doc, field, None)
            checks_by_tc[tc][f"{doc.doc_type}.{field}"] = "OK" if value not in (None, "") else "MANQUANT"

    return {
        "status": status,
        "issues": issues,
        "checks_by_document": checks_by_document,
        "checks_by_tc": checks_by_tc,
    }
