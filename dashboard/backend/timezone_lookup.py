"""Best-guess US timezone for a prospect.

The prospect's own location (the contact card's city + state) wins; the
phone's area code (NPA) is only the fallback when the contact has no
usable state. Area codes travel with people, so a Dallas business owner
with a 305 cell got booked on Miami time — the address is where they
actually are.

Used everywhere the setter reasons about the prospect's clock (offered
slots, bookings, send windows) and to pre-fill the booking form's
timezone dropdown, which the rep can still override.
"""

import re

E, C, M, AZ, P = "America/New_York", "America/Chicago", "America/Denver", "America/Phoenix", "America/Los_Angeles"
AK, HI = "America/Anchorage", "Pacific/Honolulu"

# State -> the timezone most of its population is in.
_STATE_TZ = {
    "AL": C, "AK": AK, "AZ": AZ, "AR": C, "CA": P, "CO": M, "CT": E, "DE": E, "DC": E, "FL": E,
    "GA": E, "HI": HI, "ID": M, "IL": C, "IN": E, "IA": C, "KS": C, "KY": E, "LA": C, "ME": E,
    "MD": E, "MA": E, "MI": E, "MN": C, "MS": C, "MO": C, "MT": M, "NE": C, "NV": P, "NH": E,
    "NJ": E, "NM": M, "NY": E, "NC": E, "ND": C, "OH": E, "OK": C, "OR": P, "PA": E, "RI": E,
    "SC": E, "SD": C, "TN": C, "TX": C, "UT": M, "VT": E, "VA": E, "WA": P, "WV": E, "WI": C,
    "WY": M,
}

_STATE_NAMES = {
    "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR", "CALIFORNIA": "CA",
    "COLORADO": "CO", "CONNECTICUT": "CT", "DELAWARE": "DE", "DISTRICT OF COLUMBIA": "DC",
    "FLORIDA": "FL", "GEORGIA": "GA", "HAWAII": "HI", "IDAHO": "ID", "ILLINOIS": "IL",
    "INDIANA": "IN", "IOWA": "IA", "KANSAS": "KS", "KENTUCKY": "KY", "LOUISIANA": "LA",
    "MAINE": "ME", "MARYLAND": "MD", "MASSACHUSETTS": "MA", "MICHIGAN": "MI", "MINNESOTA": "MN",
    "MISSISSIPPI": "MS", "MISSOURI": "MO", "MONTANA": "MT", "NEBRASKA": "NE", "NEVADA": "NV",
    "NEW HAMPSHIRE": "NH", "NEW JERSEY": "NJ", "NEW MEXICO": "NM", "NEW YORK": "NY",
    "NORTH CAROLINA": "NC", "NORTH DAKOTA": "ND", "OHIO": "OH", "OKLAHOMA": "OK", "OREGON": "OR",
    "PENNSYLVANIA": "PA", "RHODE ISLAND": "RI", "SOUTH CAROLINA": "SC", "SOUTH DAKOTA": "SD",
    "TENNESSEE": "TN", "TEXAS": "TX", "UTAH": "UT", "VERMONT": "VT", "VIRGINIA": "VA",
    "WASHINGTON": "WA", "WEST VIRGINIA": "WV", "WISCONSIN": "WI", "WYOMING": "WY",
}

# Cities in the minority timezone of a split state. Anything not listed
# gets the state's main timezone above.
_CITY_TZ = {
    "TX": (M, ["El Paso", "Horizon City", "Socorro", "Canutillo", "Anthony", "Fabens", "Clint",
               "San Elizario", "Vinton", "Sierra Blanca", "Dell City"]),
    "FL": (C, ["Pensacola", "Panama City", "Panama City Beach", "Fort Walton Beach", "Destin", "Navarre",
               "Crestview", "Niceville", "Milton", "Gulf Breeze", "Pace", "DeFuniak Springs", "Lynn Haven",
               "Callaway", "Marianna", "Chipley", "Santa Rosa Beach", "Miramar Beach", "Mary Esther",
               "Bonifay", "Cantonment", "Valparaiso", "Shalimar", "Freeport", "Wewahitchka", "Mexico Beach"]),
    "TN": (E, ["Knoxville", "Chattanooga", "Johnson City", "Kingsport", "Bristol", "Maryville", "Oak Ridge",
               "Morristown", "Cleveland", "Sevierville", "Pigeon Forge", "Gatlinburg", "Farragut", "Athens",
               "Greeneville", "Elizabethton", "Alcoa", "Lenoir City", "Powell", "Hixson", "Ooltewah",
               "Signal Mountain", "Collegedale", "Red Bank", "East Ridge", "Jefferson City", "Dandridge",
               "Newport", "Loudon", "Kingston", "Harriman", "Clinton", "LaFollette", "Tazewell",
               "Rogersville", "Dayton", "Madisonville", "Sweetwater", "Seymour"]),
    "KY": (C, ["Bowling Green", "Owensboro", "Paducah", "Hopkinsville", "Henderson", "Madisonville",
               "Murray", "Glasgow", "Mayfield", "Franklin", "Russellville", "Princeton", "Central City",
               "Greenville", "Fort Campbell", "Oak Grove", "Benton", "Calvert City", "Morganfield",
               "Scottsville", "Leitchfield", "Tompkinsville", "Cadiz", "Marion", "Dawson Springs"]),
    "IN": (C, ["Gary", "Hammond", "Merrillville", "Valparaiso", "Portage", "Crown Point", "Michigan City",
               "Evansville", "Schererville", "Hobart", "Munster", "Highland", "Mount Vernon", "Newburgh",
               "Boonville", "East Chicago", "Lake Station", "Chesterton", "La Porte", "LaPorte", "Dyer",
               "St. John", "Saint John", "Cedar Lake", "Lowell", "Griffith", "Whiting", "Tell City",
               "Jasper", "Princeton", "Vincennes"]),
    "MI": (C, ["Iron Mountain", "Kingsford", "Menominee", "Ironwood", "Iron River", "Norway", "Bessemer",
               "Wakefield"]),
    "ND": (M, ["Dickinson", "Watford City", "Bowman", "Beach", "Hettinger", "Belfield"]),
    "SD": (M, ["Rapid City", "Spearfish", "Sturgis", "Belle Fourche", "Lead", "Deadwood", "Hot Springs",
               "Custer", "Box Elder", "Hill City", "Summerset", "Wall"]),
    "NE": (M, ["Scottsbluff", "Gering", "Alliance", "Sidney", "Chadron", "Ogallala", "Kimball",
               "Mitchell", "Bridgeport", "Rushville", "Gordon"]),
    "KS": (M, ["Goodland", "Sharon Springs", "Tribune", "Syracuse"]),
    "OR": (M, ["Ontario", "Nyssa", "Vale"]),
    "ID": (P, ["Coeur d'Alene", "Coeur dAlene", "Post Falls", "Lewiston", "Moscow", "Sandpoint", "Hayden",
               "Rathdrum", "Bonners Ferry", "Kellogg", "Grangeville", "Orofino", "Priest River",
               "Spirit Lake", "Dalton Gardens"]),
    "NV": (M, ["West Wendover"]),
}
_CITY_TZ = {st: (tz, {re.sub(r"[^a-z]", "", c.lower()) for c in cities}) for st, (tz, cities) in _CITY_TZ.items()}

# Area code -> timezone, built per state so no code can land in two zones.
_STATE_AREA_CODES = {
    E: ["203", "475", "860", "959",                                                      # CT
        "302", "202", "771",                                                             # DE, DC
        "239", "305", "321", "324", "352", "386", "407", "561", "645", "656", "689",
        "727", "728", "754", "772", "786", "813", "863", "904", "941", "954",            # FL
        "229", "404", "470", "478", "678", "706", "762", "770", "912", "943",            # GA
        "260", "317", "463", "574", "765", "812", "930",                                 # IN
        "502", "606", "859",                                                             # KY (east)
        "207", "227", "240", "301", "410", "443", "667",                                 # ME, MD
        "339", "351", "413", "508", "617", "774", "781", "857", "978",                   # MA
        "231", "248", "269", "313", "517", "586", "616", "679", "734", "810", "906",
        "947", "989",                                                                    # MI
        "603", "201", "551", "609", "640", "732", "848", "856", "862", "908", "973",     # NH, NJ
        "212", "315", "329", "332", "347", "363", "516", "518", "585", "607", "624",
        "631", "646", "680", "716", "718", "838", "845", "914", "917", "929", "934",     # NY
        "252", "336", "472", "704", "743", "828", "910", "919", "980", "984",            # NC
        "216", "220", "234", "283", "326", "330", "380", "419", "436", "440", "513",
        "567", "614", "740", "937",                                                      # OH
        "215", "223", "267", "272", "412", "445", "484", "570", "582", "610", "717",
        "724", "814", "835", "878",                                                      # PA
        "401", "803", "821", "839", "843", "854", "864",                                 # RI, SC
        "423", "865",                                                                    # TN (east)
        "802", "276", "434", "540", "571", "686", "703", "757", "804", "826", "948",     # VT, VA
        "304", "681"],                                                                   # WV
    C: ["205", "251", "256", "334", "483", "659", "938",                                 # AL
        "327", "479", "501", "870",                                                      # AR
        "448", "850",                                                                    # FL panhandle
        "217", "224", "309", "312", "331", "447", "464", "618", "630", "708", "730",
        "773", "779", "815", "847", "861", "872",                                        # IL
        "219",                                                                           # IN (northwest)
        "319", "515", "563", "641", "712",                                               # IA
        "316", "620", "785", "913",                                                      # KS
        "270", "364",                                                                    # KY (west)
        "225", "318", "337", "504", "985",                                               # LA
        "218", "320", "507", "612", "651", "763", "952",                                 # MN
        "228", "601", "662", "769",                                                      # MS
        "314", "417", "557", "573", "636", "660", "816", "975",                          # MO
        "308", "402", "531", "701", "605",                                               # NE, ND, SD
        "405", "539", "572", "580", "918",                                               # OK
        "615", "629", "731", "901", "931",                                               # TN
        "210", "214", "254", "281", "325", "346", "361", "409", "430", "432", "469",
        "512", "682", "713", "726", "737", "806", "817", "830", "832", "903", "936",
        "940", "945", "956", "972", "979",                                               # TX
        "262", "274", "353", "414", "534", "608", "715", "920"],                         # WI
    M: ["303", "719", "720", "970", "983",                                               # CO
        "208", "986", "406", "505", "575",                                               # ID, MT, NM
        "915",                                                                           # TX (El Paso)
        "385", "435", "801", "307"],                                                     # UT, WY
    AZ: ["480", "520", "602", "623", "928"],
    P: ["209", "213", "279", "310", "323", "341", "350", "357", "369", "408", "415", "424",
        "442", "510", "530", "559", "562", "619", "626", "628", "650", "657", "661", "669",
        "707", "714", "738", "747", "760", "805", "818", "820", "831", "840", "858", "909",
        "916", "925", "949", "951",                                                      # CA
        "702", "725", "775",                                                             # NV
        "458", "503", "541", "971",                                                      # OR
        "206", "253", "360", "425", "509", "564"],                                       # WA
    AK: ["907"],
    HI: ["808"],
}
_AREA_CODE_TZ = {code: tz for tz, codes in _STATE_AREA_CODES.items() for code in codes}

DEFAULT_TIMEZONE = E

US_TIMEZONES = [
    {"iana": "America/New_York",    "label": "Eastern"},
    {"iana": "America/Chicago",     "label": "Central"},
    {"iana": "America/Denver",      "label": "Mountain"},
    {"iana": "America/Phoenix",     "label": "Arizona (no DST)"},
    {"iana": "America/Los_Angeles", "label": "Pacific"},
    {"iana": "America/Anchorage",   "label": "Alaska"},
    {"iana": "Pacific/Honolulu",    "label": "Hawaii"},
]


def _state_code(state: str | None) -> str | None:
    """"TX", "tx", "Texas", "TX 75070" -> "TX"; None if it isn't a US state."""
    s = re.sub(r"[^A-Z ]", " ", (state or "").upper())
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return None
    if s in _STATE_NAMES:
        return _STATE_NAMES[s]
    first = s.split(" ")[0]
    return first if first in _STATE_TZ else None


def timezone_from_location(city: str | None, state: str | None) -> str | None:
    """Timezone from the contact card's city + state, or None when there's
    no usable US state to go on."""
    st = _state_code(state)
    if not st:
        return None
    override = _CITY_TZ.get(st)
    if override and re.sub(r"[^a-z]", "", (city or "").lower()) in override[1]:
        return override[0]
    return _STATE_TZ[st]


def timezone_from_phone(phone: str | None) -> str:
    """Best-guess timezone from a US phone number's area code; falls back
    to DEFAULT_TIMEZONE if it can't be parsed or isn't a known code."""
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        return DEFAULT_TIMEZONE
    return _AREA_CODE_TZ.get(digits[:3], DEFAULT_TIMEZONE)


def guess_timezone(phone: str | None, city: str | None = None, state: str | None = None) -> str:
    """The prospect's timezone: their contact card's location when it has a
    state, otherwise the phone's area code."""
    return timezone_from_location(city, state) or timezone_from_phone(phone)


async def prospect_timezone(conn, phone: str | None, contact=None) -> str:
    """guess_timezone for callers that only have a phone: pass the contact
    row if it's already loaded (anything with city/state keys), otherwise
    the contact is looked up by the phone's last 10 digits."""
    if contact is None:
        digits = re.sub(r"\D", "", phone or "")[-10:]
        if len(digits) == 10:
            contact = await conn.fetchrow(
                """
                SELECT city, state FROM contacts
                WHERE right(regexp_replace(phone, '\\D', '', 'g'), 10) = $1
                ORDER BY (coalesce(state, '') <> '') DESC, updated_at DESC
                LIMIT 1
                """,
                digits,
            )
    if contact is None:
        return timezone_from_phone(phone)
    return guess_timezone(phone, contact["city"], contact["state"])
