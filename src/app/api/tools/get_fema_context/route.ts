import { NextRequest, NextResponse } from "next/server";
import { getFemaContext } from "@/lib/services/fema";

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

  const state = typeof params.state === "string" ? params.state : undefined;
  const county = typeof params.county === "string" ? params.county : undefined;

  const context = await getFemaContext(state, county);
  return NextResponse.json({
    result: context.summary,
    data: context,
  });
}
