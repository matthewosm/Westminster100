/** Glob-based data loaders used by getStaticPaths and detail pages.
 *
 * All loaders are eager so the static build can resolve every path at
 * build time. Each returns a plain object keyed by the entity's
 * identifier.
 */

import type { Member } from "@/types/member";
import type { Payer } from "@/types/payer";
import type { Appg } from "@/types/appg";

type GlobMap<T> = Record<string, T>;

const MEMBERS = import.meta.glob<Member>("@/data/members/*.json", {
  eager: true,
  import: "default",
}) as GlobMap<Member>;

const PAYERS = import.meta.glob<Payer>("@/data/payers/*.json", {
  eager: true,
  import: "default",
}) as GlobMap<Payer>;

const APPGS = import.meta.glob<Appg>("@/data/appgs/*.json", {
  eager: true,
  import: "default",
}) as GlobMap<Appg>;

function basename(path: string): string {
  return path.split("/").pop()!.replace(/\.json$/, "");
}

export function allMembers(): Member[] {
  return Object.values(MEMBERS);
}

export function memberByMnisId(mnisId: number | string): Member | undefined {
  return allMembers().find((m) => String(m.mnis_id) === String(mnisId));
}

export function allPayers(): Payer[] {
  return Object.values(PAYERS);
}

export function payerByKey(key: number | string): Payer | undefined {
  const target = String(key);
  for (const [path, payer] of Object.entries(PAYERS)) {
    if (basename(path) === target) return payer;
  }
  return undefined;
}

export function allAppgs(): Appg[] {
  return Object.values(APPGS);
}

export function appgBySlug(slug: string): Appg | undefined {
  for (const [path, appg] of Object.entries(APPGS)) {
    if (basename(path) === slug) return appg;
  }
  return undefined;
}
