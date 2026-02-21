import { NextRequest, NextResponse } from "next/server";
import { getWeatherContext } from "@/lib/services/weather";

function getParams(body: unknown): Record<string, unknown> {
  if (!body || typeof body !== "object") return {};
  const maybe = body as Record<string, unknown>;
  if (maybe.parameters && typeof maybe.parameters === "object") {
    return maybe.parameters as Record<string, unknown>;
  }
  return maybe;
}

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const params = getParams(body);

  const lat = Number(params.lat ?? params.latitude);
  const lon = Number(params.lon ?? params.lng ?? params.longitude);

  if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
    return NextResponse.json(
      {
        result:
          "Missing or invalid coordinates. Please provide numeric lat and lon.",
      },
      { status: 400 }
    );
  }

  try {
    const context = await getWeatherContext(lat, lon);
    return NextResponse.json({
      result: context.summary,
      data: context,
    });
  } catch {
    return NextResponse.json(
      {
        result:
          "Weather data is temporarily unavailable. Please retry in a few moments.",
      },
      { status: 200 }
    );
  }
}
