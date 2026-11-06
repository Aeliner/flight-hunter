"""Buquebus ferry fares over plain HTTP (the site's own /api/edea_login + /api/priceAvailability).

usage: python buquebus.py ORIGIN DEST YYYY-MM-DD [adults] [--currency UYU|USD]
ports: MVD Montevideo, COL Colonia, PDE Punta del Este, BUE Buenos Aires (see /api/ports)
Prints JSON: one row per sailing and seat class, total price for all adults, cheapest first.
Learned 2026-11-03 from a real search in Chrome; stdlib only.
"""
import copy
import json
import sys
import urllib.request

BASE = "https://www.buquebus.com"
HEADERS = {
    "content-type": "application/json",
    "accept": "application/json",
    "origin": BASE,
    "referer": BASE + "/uy",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
}
# (seat code, label, tariff types) as the site's own search sends them
CLASSES = [
    ("ESEAT", "Economica", ["ECONOMICA"]),
    ("TSEAT", "Turista", ["PROGRAMADA", "FLEXIBLE"]),
    ("BSEAT", "Business", ["PROGRAMADA", "FLEXIBLE"]),
    ("PRSEAT", "Premium", ["PROGRAMADA", "FLEXIBLE"]),
]


def post(path, body=None):
    data = json.dumps(body).encode() if body is not None else b""
    req = urllib.request.Request(BASE + path, data=data, headers=HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def request_body(origin, dest, yymmdd, adults, seat, tariffs, currency):
    leg = {"m_LEGJ_LegOrSectorOfJourney": "1"}
    pax = [{"m_U257_PassengerTypeCode": "ADL", "m_U258_NumberOfPassengers": adults}]
    return {
        "m_AGT_AgencyIdentity": {
            "m_AGAC_AgentsAccountNumber": {"m_AGAC_AgentAccountNumber": "7252"},
            "c_CURR_CurrencyForTransaction": {"m_6345_CurrencyCoded": currency, "c_U428_DecimalPrecision": "2"},
            "c_CMPNY_Company": {"m_C045_TradingUnitName": "PAX", "m_C046_CompanyName": "BUQUEBUS",
                                "m_C047_GeographycalLocationName": "South America", "m_C048_DivisionName": "BQB"},
            "c_SCHN_SalesChannel": {"m_C056_SalesChannel": "WEB"},
        },
        "m_RDQ_RouteDateTimeRequest": [{
            "index": "0", "m_LEGJ_LegOrSectorOfJourney": leg,
            "m_ROUT_TravelRoute": {
                "m_U271_ServiceAgreementDeparturePort": origin, "m_U272_ServiceAgreementDestinationPort": dest,
                "c_C276_SailingCode": "", "c_C040_ServiceAgreementCode": "", "c_C041_ServiceAgreementValidationCode": "",
                "c_C144_ServiceAgreementGroupType": "", "m_C001_ServiceAgreementOfferCode": "",
                "c_C039_ServiceAgreementOfferValidationCode": "", "c_C257_applyReturnFare": False,
                "c_399_SearchVesselTransfer": "false", "c_400_vesselTransferTime": 0,
            },
            "m_DPDT_DepartureDateTime": {"m_U247_StandardDepartureDate": yymmdd, "m_U248_StandardDepartureTime": "0000"},
            "c_DPDT_DepartureDateTimeTo": {"m_U247_StandardDepartureDate": yymmdd, "m_U248_StandardDepartureTime": "2359"},
        }],
        "c_PAQ_PassengerDetailRequest": [{"index": "0", "m_LEGJ_LegOrSectorOfJourney": leg,
                                          "m_PAXS_PassengerSet": [{"passengerIndex": "0", **pax[0]}]}],
        "c_ACQ_AccomodationDetailsRequest": [{
            "m_LEGJ_LegOrSectorOfJourney": leg,
            "m_ACPL_AccomodationPlaces": {"m_U228_QuantityOfUnits": adults, "m_U229_ModeOfOccupancy": "C"},
            "m_ACDT_AccomodationDetails": {"m_U220_ServiceAgreementDefinedAccomodationCode": seat, "i_U221_AccomodationType": "CHAIR"},
            "m_PAXT_PassengerType": copy.deepcopy(pax),
        }],
        "c_VEQ_VehicleRequest": [],
        "c_MTT_MultipleTariffTypeRequest": [{
            "m_LEGJ_LegOrSectorOfJourney": leg,
            "m_TARF_TariffCodeTypeDescription": [{"c_U282_TariffType": t, "c_C113_PriceDetailRequested": "true"} for t in tariffs],
        }],
    }


def hhmm(s):
    return f"{s[:2]}:{s[2:]}" if s and len(s) == 4 else s


def search(origin, dest, date, adults=1, currency="UYU"):
    yymmdd = date[2:4] + date[5:7] + date[8:10]
    token = post("/api/edea_login")["token"]
    rows = []
    for seat, label, tariffs in CLASSES:
        resp = post("/api/priceAvailability", {"token": token, "request": request_body(origin, dest, yymmdd, adults, seat, tariffs, currency)})
        for s in resp.get("sailingprice") or []:
            rd = s["c_RDR_RouteDateTimeResponse"]
            legs = rd.get("m_LEG_SailingLegs", {}).get("m_LEG_SailingLeg", [])
            for t in s.get("c_TCT_TariffChargesTotals") or []:
                amount = t["c_QLP_ChargesTotal"]["m_CHTO_ChargeTotals"].get("m_U618_TotalAmount")
                if not amount or amount == "N/A":
                    continue
                rows.append({
                    "depart": hhmm(rd["m_DPDT_DepartureDateAndTime"]["m_U248_StandardDepartureTime"]),
                    "arrive": hhmm(rd["c_ARDT_ArrivalDateAndTime"]["c_U239_NominalArrivalTime"]),
                    "minutes": rd["m_ROUT_TravelRoute"].get("c_C277_SailingDuration"),
                    "via": "+".join(f'{l["m_C278_DeparturePort"]}>{l["m_C279_ArrivalPort"]}' for l in legs) or f"{origin}>{dest} direct",
                    "ship": rd["c_SHNM_ShipName"]["m_SHNM_ShipName"],
                    "class": label,
                    "tariff": t["c_QOR_QuotationBasisResponse"]["m_TARF_TariffCodeTypeDescription"].get("c_U282_TariffType"),
                    "total": int(amount) / 100,
                    "currency": currency,
                    "adults": adults,
                    "sailingCode": rd["m_ROUT_TravelRoute"].get("c_C276_SailingCode"),
                })
    rows.sort(key=lambda r: r["total"])
    return rows


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    currency = "USD" if "--currency" in sys.argv and sys.argv[sys.argv.index("--currency") + 1] == "USD" else "UYU"
    if len(args) < 3:
        sys.exit(__doc__)
    print(json.dumps(search(args[0], args[1], args[2], int(args[3]) if len(args) > 3 else 1, currency), ensure_ascii=False))
