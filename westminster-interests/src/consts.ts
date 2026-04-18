/** Party name → short 2–3 letter tag used by PartyTag. */
export const PARTY_SHORT: Record<string, string> = {
  Conservative: "CON",
  Labour: "LAB",
  "Labour (Co-op)": "LAB",
  "Liberal Democrat": "LD",
  "Reform UK": "RFM",
  "Scottish National Party": "SNP",
  "Green Party": "GRN",
  "Plaid Cymru": "PC",
  "Democratic Unionist Party": "DUP",
  "Sinn Féin": "SF",
  "Social Democratic & Labour Party": "SDLP",
  Alliance: "APNI",
  "Ulster Unionist Party": "UUP",
  "Traditional Unionist Voice": "TUV",
  Independent: "IND",
  Speaker: "SPK",
  "Restore Britain": "RB",
  "Your Party": "YP",
  Crossbench: "XB",
};

/** Party name → accent colour used by PartyTag. Roughly matches
 * each party's official brand colour; white text is used on dark
 * fills. Independents / unknowns fall back to a neutral grey.
 */
export const PARTY_COLOURS: Record<string, { bg: string; fg: string }> = {
  Conservative: { bg: "#0087DC", fg: "#ffffff" },
  Labour: { bg: "#E4003B", fg: "#ffffff" },
  "Labour (Co-op)": { bg: "#E4003B", fg: "#ffffff" },
  "Liberal Democrat": { bg: "#FAA61A", fg: "#1a1a1a" },
  "Reform UK": { bg: "#12B6CF", fg: "#ffffff" },
  "Scottish National Party": { bg: "#FDF38E", fg: "#1a1a1a" },
  "Green Party": { bg: "#6AB023", fg: "#ffffff" },
  "Plaid Cymru": { bg: "#005B54", fg: "#ffffff" },
  "Democratic Unionist Party": { bg: "#D46A4C", fg: "#ffffff" },
  "Sinn Féin": { bg: "#326760", fg: "#ffffff" },
  "Social Democratic & Labour Party": { bg: "#2AA82C", fg: "#ffffff" },
  Alliance: { bg: "#F6CB2F", fg: "#1a1a1a" },
  "Ulster Unionist Party": { bg: "#48A5EE", fg: "#ffffff" },
  "Traditional Unionist Voice": { bg: "#0C3A6A", fg: "#ffffff" },
  Independent: { bg: "#888888", fg: "#ffffff" },
  Speaker: { bg: "#666666", fg: "#ffffff" },
  "Restore Britain": { bg: "#7F3F98", fg: "#ffffff" },
  "Your Party": { bg: "#666666", fg: "#ffffff" },
  Crossbench: { bg: "#5a5a5a", fg: "#ffffff" },
};

export const CATEGORY_LABELS: Record<string, string> = {
  "1.1": "Employment — ad hoc",
  "1.2": "Employment — regular",
  "2": "Donations",
  "3": "Gifts & hospitality",
  "4": "Visits abroad",
  "5": "Overseas gifts",
};

export const CATEGORY_SHORT: Record<string, string> = {
  "1.1": "Ad hoc",
  "1.2": "Regular",
  "2": "Donation",
  "3": "Gift",
  "4": "Visit",
  "5": "Overseas",
};

/** Category → pill background + text colour. Soft tints so pills
 * read as categorical accents without overpowering the table.
 */
export const CATEGORY_COLOURS: Record<string, { bg: string; fg: string }> = {
  "1.1": { bg: "#dbeafe", fg: "#1e3a8a" }, // ad-hoc employment — blue
  "1.2": { bg: "#e0e7ff", fg: "#3730a3" }, // regular employment — indigo
  "2":   { bg: "#fee2e2", fg: "#991b1b" }, // donations — red
  "3":   { bg: "#fef3c7", fg: "#92400e" }, // gifts — amber
  "4":   { bg: "#dcfce7", fg: "#166534" }, // visits — green
  "5":   { bg: "#f3e8ff", fg: "#6b21a8" }, // overseas gifts — purple
};

/** Strip noisy prefixes from APPG display names. The canonical
 * data keeps the full title; this is a display-only shortening.
 */
const APPG_PREFIX_PATTERNS = [
  /^All-Party Parliamentary Group on the\s+/i,
  /^All-Party Parliamentary Group on\s+/i,
  /^All-Party Parliamentary Group for the\s+/i,
  /^All-Party Parliamentary Group for\s+/i,
  /^All-Party Parliamentary Group\s+/i,
  /^All Party Parliamentary Group on the\s+/i,
  /^All Party Parliamentary Group on\s+/i,
  /^All Party Parliamentary Group for the\s+/i,
  /^All Party Parliamentary Group for\s+/i,
  /^All Party Parliamentary Group\s+/i,
  /^All-Partly Parliamentary Group on\s+/i, // source typo in register
  /^APPG on the\s+/i,
  /^APPG on\s+/i,
  /^APPG for\s+/i,
  /^APPG\s+/i,
];

export function shortenAppgName(full: string | null | undefined): string {
  if (!full) return "—";
  let out = full.trim();
  for (const re of APPG_PREFIX_PATTERNS) {
    out = out.replace(re, "");
  }
  // Remove trailing " Group" if the whole string still ends with it.
  out = out.replace(/\s+Group$/i, "");
  return out || full;
}
