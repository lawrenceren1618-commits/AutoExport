import destRules from "./carton-destination-rules.json";

export type CartonChannel = "FC" | "AWD" | "UNKNOWN";

export type CartonDestinationRules = typeof destRules;

export function cartonDestinationRules(): CartonDestinationRules {
  return destRules;
}

export function fcWarehouses(): Set<string> {
  return new Set(destRules.warehouses.FC.map((w) => w.toUpperCase()));
}

export function awdWarehouses(): Set<string> {
  return new Set(destRules.warehouses.AWD.map((w) => w.toUpperCase()));
}

export function allKnownWarehouses(): Set<string> {
  return new Set([...fcWarehouses(), ...awdWarehouses()]);
}

export function pdfJunkTokens(): Set<string> {
  return new Set(destRules.pdf_text_layer.ignore_tokens.map((t) => t.toUpperCase()));
}

export function detectCartonChannel(text: string): {
  channel: CartonChannel;
  signals: string[];
} {
  const u = text.toUpperCase();
  const signals: string[] = [];
  const hasStar = /\bSTAR-[0-9A-Z]+/.test(u);
  const hasAwdWord = /\bAWD\b/.test(u) || u.includes("AWD 3PL") || u.includes("AWD BOX");
  const hasAwdSite = destRules.warehouses.AWD.some((w) => new RegExp(`\\b${w}\\b`, "i").test(text));
  const hasFba = /\bFBA[0-9A-Z]{8,}/.test(u);
  const hasFcName = /货件名称/.test(text);

  if (hasStar) signals.push("STAR-");
  if (hasAwdWord) signals.push("AWD");
  if (hasAwdSite) signals.push("AWD_SITE");
  if (hasFba) signals.push("FBA");
  if (hasFcName) signals.push("货件名称");

  if (hasStar || hasAwdWord || (hasAwdSite && !hasFba)) {
    return { channel: "AWD", signals };
  }
  if (hasFba || hasFcName) {
    return { channel: "FC", signals };
  }
  return { channel: "UNKNOWN", signals };
}
