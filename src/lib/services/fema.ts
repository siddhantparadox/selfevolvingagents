import { fetchJson } from "@/lib/http";

type FemaDeclaration = {
  declarationTitle?: string;
  declarationDate?: string;
  incidentType?: string;
  state?: string;
  designatedArea?: string;
};

type FemaDeclarationsResponse = {
  DisasterDeclarationsSummaries?: FemaDeclaration[];
};

export type FemaContext = {
  state?: string;
  county?: string;
  recentDeclarations: FemaDeclaration[];
  summary: string;
};

export async function getFemaContext(
  state?: string,
  county?: string
): Promise<FemaContext> {
  if (!state) {
    return {
      recentDeclarations: [],
      summary:
        "No state provided for FEMA context. Ask caller for location to provide local emergency context.",
    };
  }

  const normalizedState = state.trim().toUpperCase();
  const normalizedCounty = county?.trim();

  const filters = [`state eq '${normalizedState}'`];
  if (normalizedCounty) {
    filters.push(`contains(designatedArea,'${normalizedCounty.toUpperCase()}')`);
  }

  const query = new URLSearchParams({
    $top: "3",
    $orderby: "declarationDate desc",
    $filter: filters.join(" and "),
  });

  const url = `https://www.fema.gov/api/open/v1/DisasterDeclarationsSummaries?${query.toString()}`;

  try {
    const response = await fetchJson<FemaDeclarationsResponse>(url);
    const recentDeclarations = (response.DisasterDeclarationsSummaries ?? []).slice(
      0,
      3
    );

    const summary =
      recentDeclarations.length > 0
        ? `Recent FEMA declarations for ${normalizedState}: ${recentDeclarations
            .map((item) => `${item.incidentType ?? "Incident"} (${item.declarationDate ?? "date unavailable"})`)
            .join(" | ")}.`
        : `No recent FEMA declarations found for ${normalizedState}.`;

    return {
      state: normalizedState,
      county: normalizedCounty,
      recentDeclarations,
      summary,
    };
  } catch {
    return {
      state: normalizedState,
      county: normalizedCounty,
      recentDeclarations: [],
      summary:
        "FEMA data is temporarily unavailable. Continue with NWS + USGS context for response safety.",
    };
  }
}
