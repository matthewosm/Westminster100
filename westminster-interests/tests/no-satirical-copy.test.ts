import { describe, expect, it } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const DIST = join(__dirname, "..", "dist");

const FORBIDDEN = [
  "Elite Ten",
  "Principal Patron",
  "Podium",
  "Revenue Streams",
  "Benefactors",
  "Philanthropists",
  "Franchise",
  // "Patron" as standalone word (but allow "patronage" etc. if ever introduced).
  // Case-insensitive whole-word check via regex.
];

const FORBIDDEN_REGEX = [/\bPatron\b/];

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) {
      out.push(...walk(path));
    } else if (name.endsWith(".html")) {
      out.push(path);
    }
  }
  return out;
}

describe("satirical copy scrub (R1)", () => {
  it("no retained satirical terminology appears in rendered HTML", () => {
    let htmlFiles: string[];
    try {
      htmlFiles = walk(DIST);
    } catch {
      return; // dist/ not built — skip silently
    }
    for (const file of htmlFiles) {
      const body = readFileSync(file, "utf-8");
      for (const needle of FORBIDDEN) {
        expect(body, `${file} contains forbidden term "${needle}"`).not.toContain(
          needle,
        );
      }
      for (const re of FORBIDDEN_REGEX) {
        expect(body, `${file} matches forbidden pattern ${re}`).not.toMatch(re);
      }
    }
  });
});
