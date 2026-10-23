import { NextRequest, NextResponse } from "next/server";

const GATEWAY_URL = process.env.ESK_GATEWAY_URL ?? "";
const GATEWAY_TOKEN = process.env.ESK_GATEWAY_TOKEN ?? "";

// Only these fields are forwarded. Anything else in the request body is
// dropped, so the route cannot be used to smuggle arbitrary data to the
// report service.
const FORWARDED_FIELDS = [
  "workflow",
  "class",
  "mode",
  "session",
  "school",
  "username",
  "password",
] as const;

function configured() {
  return Boolean(GATEWAY_URL && GATEWAY_TOKEN);
}

export async function POST(req: NextRequest) {
  if (!configured()) {
    return NextResponse.json(
      { error: "Job service is not configured." },
      { status: 503 },
    );
  }

  let body: Record<string, unknown>;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const payload: Record<string, unknown> = {};
  for (const key of FORWARDED_FIELDS) {
    if (body[key] !== undefined) payload[key] = body[key];
  }

  try {
    const res = await fetch(`${GATEWAY_URL}/v1/reports`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-report-token": GATEWAY_TOKEN,
      },
      body: JSON.stringify(payload),
      cache: "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json(
      { error: "Report gateway is unreachable." },
      { status: 502 },
    );
  }
}
