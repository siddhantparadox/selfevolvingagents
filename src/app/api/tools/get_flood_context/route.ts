import { NextRequest, NextResponse } from "next/server";
import { getFloodContext } from "@/lib/services/usgs";

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

  const state =
    typeof params.state === "string"
      ? params.state
      : typeof params.stateAbbreviation === "string"
        ? params.stateAbbreviation
        : undefined;

  try {
    const context = await getFloodContext(state);
    return NextResponse.json({
      result: context.summary,
      data: context,
    });
  } catch {
    return NextResponse.json(
      {
        result:
          "Flood context is temporarily unavailable. Continue with weather guidance.",
      },
      { status: 200 }
    );
  }
}
