"""Small ISO 20022 builders for bounded FinSpace payment profiles."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping

from ..errors import MissingOptionalDependency

PAIN_NS = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.13"
PACS_NS = "urn:iso:std:iso:20022:tech:xsd:pacs.008.001.14"


@dataclass
class ISO20022PaymentBuilder:
    """Build minimal pain.001 or pacs.008 documents from FinSpace records."""

    creation_time: str = "2026-08-02T13:30:00Z"

    def _lxml(self) -> Any:
        try:
            from lxml import etree
        except ImportError as error:
            raise MissingOptionalDependency("install finspace[iso20022]") from error
        return etree

    @staticmethod
    def _sub(etree: Any, parent: Any, namespace: str, name: str, text: str | None = None, **attrs: str) -> Any:
        child = etree.SubElement(parent, f"{{{namespace}}}{name}", **attrs)
        if text is not None:
            child.text = text
        return child

    def __call__(self, record: Mapping[str, Any]) -> bytes:
        message = str(record["message"])
        if message == "pain.001.001.13":
            return self._pain(record)
        if message == "pacs.008.001.14":
            return self._pacs(record)
        raise ValueError(f"unsupported ISO 20022 message {message!r}")

    def _pain(self, record: Mapping[str, Any]) -> bytes:
        etree = self._lxml()
        ns = PAIN_NS
        root = etree.Element(f"{{{ns}}}Document", nsmap={None: ns})
        initiation = self._sub(etree, root, ns, "CstmrCdtTrfInitn")
        header = self._sub(etree, initiation, ns, "GrpHdr")
        self._sub(etree, header, ns, "MsgId", str(record.get("message_id", "FINSPACE-PAIN")))
        self._sub(etree, header, ns, "CreDtTm", self.creation_time)
        self._sub(etree, header, ns, "NbOfTxs", "1")
        amount = Decimal(str(record["amount"]))
        self._sub(etree, header, ns, "CtrlSum", f"{amount:.2f}")
        initiating = self._sub(etree, header, ns, "InitgPty")
        self._sub(etree, initiating, ns, "Nm", str(record["debtor"]))
        payment = self._sub(etree, initiation, ns, "PmtInf")
        self._sub(etree, payment, ns, "PmtInfId", str(record.get("payment_id", "FINSPACE-PMT")))
        self._sub(etree, payment, ns, "PmtMtd", "TRF")
        self._sub(etree, payment, ns, "BtchBookg", str(record.get("batch_booking", False)).lower())
        self._sub(etree, payment, ns, "NbOfTxs", "1")
        self._sub(etree, payment, ns, "CtrlSum", f"{amount:.2f}")
        requested = self._sub(etree, payment, ns, "ReqdExctnDt")
        self._sub(etree, requested, ns, "Dt", f"2026-08-{int(record['day']):02d}")
        transaction = self._sub(etree, payment, ns, "CdtTrfTxInf")
        identification = self._sub(etree, transaction, ns, "PmtId")
        self._sub(etree, identification, ns, "EndToEndId", str(record.get("end_to_end_id", "FINSPACE-E2E")))
        amount_node = self._sub(etree, transaction, ns, "Amt")
        self._sub(etree, amount_node, ns, "InstdAmt", f"{amount:.2f}", Ccy=str(record["currency"]))
        creditor = self._sub(etree, transaction, ns, "Cdtr")
        self._sub(etree, creditor, ns, "Nm", str(record["creditor"]))
        return etree.tostring(root, xml_declaration=True, encoding="UTF-8")

    def _pacs(self, record: Mapping[str, Any]) -> bytes:
        etree = self._lxml()
        ns = PACS_NS
        root = etree.Element(f"{{{ns}}}Document", nsmap={None: ns})
        transfer = self._sub(etree, root, ns, "FIToFICstmrCdtTrf")
        header = self._sub(etree, transfer, ns, "GrpHdr")
        self._sub(etree, header, ns, "MsgId", str(record.get("message_id", "FINSPACE-PACS")))
        self._sub(etree, header, ns, "CreDtTm", self.creation_time)
        self._sub(etree, header, ns, "NbOfTxs", "1")
        settlement = self._sub(etree, header, ns, "SttlmInf")
        self._sub(etree, settlement, ns, "SttlmMtd", "CLRG")
        transaction = self._sub(etree, transfer, ns, "CdtTrfTxInf")
        identification = self._sub(etree, transaction, ns, "PmtId")
        self._sub(etree, identification, ns, "EndToEndId", str(record.get("end_to_end_id", "FINSPACE-E2E")))
        amount = Decimal(str(record["amount"]))
        self._sub(etree, transaction, ns, "IntrBkSttlmAmt", f"{amount:.2f}", Ccy=str(record["currency"]))
        self._sub(etree, transaction, ns, "IntrBkSttlmDt", f"2026-08-{int(record['day']):02d}")
        self._sub(etree, transaction, ns, "SttlmPrty", str(record.get("priority", "NORM")))
        self._sub(etree, transaction, ns, "ChrgBr", str(record.get("charge_bearer", "SLEV")))
        debtor = self._sub(etree, transaction, ns, "Dbtr")
        self._sub(etree, debtor, ns, "Nm", str(record["debtor"]))
        creditor = self._sub(etree, transaction, ns, "Cdtr")
        self._sub(etree, creditor, ns, "Nm", str(record["creditor"]))
        return etree.tostring(root, xml_declaration=True, encoding="UTF-8")
