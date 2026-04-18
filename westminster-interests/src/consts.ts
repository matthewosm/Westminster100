/** Party name → short 2–3 letter tag used by PartyTag. Monochrome; no colours. */
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
