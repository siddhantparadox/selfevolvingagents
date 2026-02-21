import { fetchJson } from "@/lib/http";

type NwsPointsResponse = {
  properties?: {
    forecast?: string;
    forecastHourly?: string;
  };
};

type NwsForecastResponse = {
  properties?: {
    periods?: Array<{
      name: string;
      temperature: number;
      temperatureUnit: string;
      shortForecast: string;
    }>;
  };
};

type NwsAlertsResponse = {
  features?: Array<{
    properties?: {
      headline?: string;
      severity?: string;
    };
  }>;
};

export type WeatherContext = {
  alertCount: number;
  alertHeadlines: string[];
  forecastSummary: string;
  summary: string;
};

const NWS_HEADERS = {
  "User-Agent": "selfimprovingagents/0.1 (hackathon weather calm agent)",
  Accept: "application/geo+json",
};

export async function getWeatherContext(
  lat: number,
  lon: number
): Promise<WeatherContext> {
  const roundedLat = lat.toFixed(4);
  const roundedLon = lon.toFixed(4);

  const pointsUrl = `https://api.weather.gov/points/${roundedLat},${roundedLon}`;
  const points = await fetchJson<NwsPointsResponse>(pointsUrl, {
    headers: NWS_HEADERS,
  });

  const forecastHourlyUrl = points.properties?.forecastHourly;
  const alertsUrl = `https://api.weather.gov/alerts/active?point=${roundedLat},${roundedLon}`;

  let forecastSummary = "Forecast unavailable right now.";
  if (forecastHourlyUrl) {
    const forecast = await fetchJson<NwsForecastResponse>(forecastHourlyUrl, {
      headers: NWS_HEADERS,
    });

    const periods = (forecast.properties?.periods ?? []).slice(0, 3);
    if (periods.length > 0) {
      forecastSummary = periods
        .map(
          (period) =>
            `${period.name}: ${period.temperature}${period.temperatureUnit}, ${period.shortForecast}`
        )
        .join(" | ");
    }
  }

  const alerts = await fetchJson<NwsAlertsResponse>(alertsUrl, {
    headers: NWS_HEADERS,
  });
  const alertHeadlines = (alerts.features ?? [])
    .map((feature) => feature.properties?.headline)
    .filter((headline): headline is string => Boolean(headline))
    .slice(0, 3);

  const alertCount = alertHeadlines.length;
  const summary =
    alertCount > 0
      ? `There are ${alertCount} active weather alerts near this location. ${alertHeadlines.join(
          " | "
        )}. ${forecastSummary}`
      : `No active weather alerts near this location. ${forecastSummary}`;

  return {
    alertCount,
    alertHeadlines,
    forecastSummary,
    summary,
  };
}
