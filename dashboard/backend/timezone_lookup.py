"""Best-guess US timezone from a phone number's area code (NPA).

Used to pre-fill the appointment-booking form's timezone dropdown — the rep
can always override it. Not authoritative (area codes don't perfectly map to
a single timezone, e.g. TX/FL/MI span two each), just a reasonable default so
the rep isn't picking from scratch on every booking.
"""

import re

# Area code -> IANA timezone. Covers the ~7 timezones cold calls land in
# (mainland US + Alaska/Hawaii). Split-timezone states get their most
# populous timezone; the rep overrides for the rest.
_AREA_CODE_TZ = {
    # Eastern
    **{code: "America/New_York" for code in [
        "201","202","203","207","212","215","216","220","223","228","239","240",
        "246","248","251","267","272","276","279","301","302","304","305","321",
        "330","332","334","336","339","341","351","352","354","357","386","401",
        "404","407","410","412","413","419","423","434","440","443","470","475",
        "478","484","508","513","516","518","551","561","570","571","572","585",
        "603","607","609","610","614","616","617","631","646","667","678","680",
        "684","703","704","706","716","717","724","727","732","734","740","754",
        "757","770","772","774","781","786","800","802","803","804","813","814",
        "826","828","839","845","848","850","854","856","857","860","862","863",
        "878","904","906","908","910","912","914","917","919","929","931","934",
        "941","947","954","959","973","978","980","984",
    ]},
    # Central
    **{code: "America/Chicago" for code in [
        "205","209","217","218","224","225","228","251","262","281","305","309",
        "312","314","316","318","319","320","325","331","337","338","346","361",
        "365","369","375","380","406","409","414","417","430","432","447","456",
        "463","469","479","501","504","507","512","515","530","534","563","573",
        "580","608","615","618","620","629","630","636","641","651","662","708",
        "712","713","715","731","737","763","708","806","815","816","817","820",
        "830","832","847","850","870","901","903","915","918","920","931","936",
        "940","952","956","972","979",
    ]},
    # Mountain
    **{code: "America/Denver" for code in [
        "208","303","307","320","385","406","435","505","575","580","719","720",
        "801","970",
    ]},
    # Arizona — no DST
    **{code: "America/Phoenix" for code in ["480", "520", "602", "623", "928"]},
    # Pacific
    **{code: "America/Los_Angeles" for code in [
        "206","209","213","253","310","323","341","360","408","415","424","442",
        "458","469","503","509","510","530","531","541","559","562","619","626",
        "628","650","657","661","669","702","707","714","725","747","753","760",
        "775","805","818","820","831","858","909","916","925","949","951","971",
    ]},
    # Alaska
    **{code: "America/Anchorage" for code in ["907"]},
    # Hawaii
    **{code: "Pacific/Honolulu" for code in ["808"]},
}

DEFAULT_TIMEZONE = "America/New_York"

US_TIMEZONES = [
    {"iana": "America/New_York",    "label": "Eastern"},
    {"iana": "America/Chicago",     "label": "Central"},
    {"iana": "America/Denver",      "label": "Mountain"},
    {"iana": "America/Phoenix",     "label": "Arizona (no DST)"},
    {"iana": "America/Los_Angeles", "label": "Pacific"},
    {"iana": "America/Anchorage",   "label": "Alaska"},
    {"iana": "Pacific/Honolulu",    "label": "Hawaii"},
]


def guess_timezone(phone: str | None) -> str:
    """Best-guess IANA timezone from a US phone number's area code.
    Falls back to DEFAULT_TIMEZONE if the number can't be parsed or the
    area code isn't in the table."""
    if not phone:
        return DEFAULT_TIMEZONE
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        return DEFAULT_TIMEZONE
    area_code = digits[:3]
    return _AREA_CODE_TZ.get(area_code, DEFAULT_TIMEZONE)
