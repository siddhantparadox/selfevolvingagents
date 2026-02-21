import { fetchJson } from "@/lib/http";

type UsgsState = {
  id: number;
  abbreviation: string;
  name: string;
};

type UsgsReferencePoint = {
  site_name: string;
  gage_height: number;
  unit: string;
  is_flooding: boolean;
  nws_id: string | null;
};

export type FloodContext = {
  state?: string;
  floodingCount: number;
  sampledSites: string[];
  summary: string;
};

export async function getFloodContext(
  stateAbbreviation?: string
): Promise<FloodContext> {
  if (!stateAbbreviation) {
    return {
      floodingCount: 0,
      sampledSites: [],
      summary:
        "No state provided for USGS flood context. Ask caller for state or ZIP for a flood check.",
    };
  }

  const normalizedState = stateAbbreviation.trim().toUpperCase();

  const states = await fetchJson<UsgsState[]>(
    "https://api.waterdata.usgs.gov/rtfi-api/states?limit=100&page=1"
  );
  const state = states.find((item) => item.abbreviation === normalizedState);

  if (!state) {
    return {
      state: normalizedState,
      floodingCount: 0,
      sampledSites: [],
      summary: `USGS state lookup failed for ${normalizedState}.`,
    };
  }

  const points = await fetchJson<UsgsReferencePoint[]>(
    `https://api.waterdata.usgs.gov/rtfi-api/referencepoints/state/${state.id}`
  );

  const floodingSites = points.filter((point) => point.is_flooding);
  const sampledSites = floodingSites
    .slice(0, 3)
    .map(
      (site) =>
        `${site.site_name} (${site.gage_height}${site.unit}${site.nws_id ? `, NWS ${site.nws_id}` : ""})`
    );

  const summary =
    floodingSites.length > 0
      ? `USGS indicates ${floodingSites.length} flood-impact reference points in ${state.name}. Examples: ${sampledSites.join(
          " | "
        )}.`
      : `USGS reports no active flooding reference points in ${state.name}.`;

  return {
    state: state.abbreviation,
    floodingCount: floodingSites.length,
    sampledSites,
    summary,
  };
}
