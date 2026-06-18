// web/flags.js — canonical roster name -> flag emoji.
// Canonical names use the workbook's spellings (Korea Rep., Uzebekistan, Congo,
// Turkey, ...). Most map to an ISO 3166-1 alpha-2 code we turn into a flag emoji;
// England and Scotland use subdivision tag sequences.

const ISO = {
  "Mexico": "MX", "South Africa": "ZA", "Korea Rep.": "KR", "Czechia": "CZ",
  "Canada": "CA", "Bosnia": "BA", "Qatar": "QA", "Switzerland": "CH",
  "Brazil": "BR", "Morocco": "MA", "Haiti": "HT",
  "USA": "US", "Paraguay": "PY", "Australia": "AU", "Turkey": "TR",
  "Germany": "DE", "Curacao": "CW", "Ivory Coast": "CI", "Ecuador": "EC",
  "Netherlands": "NL", "Japan": "JP", "Sweden": "SE", "Tunisia": "TN",
  "Belgium": "BE", "Egypt": "EG", "Iran": "IR", "New Zealand": "NZ",
  "Spain": "ES", "Cape Verde": "CV", "Saudi Arabia": "SA", "Uruguay": "UY",
  "France": "FR", "Senegal": "SN", "Iraq": "IQ", "Norway": "NO",
  "Argentina": "AR", "Algeria": "DZ", "Austria": "AT", "Jordan": "JO",
  "Portugal": "PT", "Congo": "CD", "Uzebekistan": "UZ", "Colombia": "CO",
  "Croatia": "HR", "Ghana": "GH", "Panama": "PA",
};

// Subdivision flags (Great Britain ... England / Scotland).
const SPECIAL = {
  "England": "\u{1F3F4}\u{E0067}\u{E0062}\u{E0065}\u{E006E}\u{E0067}\u{E007F}",
  "Scotland": "\u{1F3F4}\u{E0067}\u{E0062}\u{E0073}\u{E0063}\u{E0074}\u{E007F}",
};

function codeToEmoji(cc) {
  return String.fromCodePoint(...[...cc].map((c) => 0x1f1e6 + c.charCodeAt(0) - 65));
}

const _cache = {};

export function flag(name) {
  if (name in _cache) return _cache[name];
  let out = "\u{1F3F3}"; // white flag fallback (defensive; all 48 are mapped)
  if (name in SPECIAL) out = SPECIAL[name];
  else if (name in ISO) out = codeToEmoji(ISO[name]);
  _cache[name] = out;
  return out;
}
