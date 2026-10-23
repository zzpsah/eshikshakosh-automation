import { NextRequest, NextResponse } from "next/server";

const GATEWAY_URL = process.env.ESK_GATEWAY_URL ?? "";
const GATEWAY_TOKEN = process.env.ESK_GATEWAY_TOKEN ?? "";

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

  try {
    const res = await fetch(`${GATEWAY_URL}/v1/reports`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-report-token": GATEWAY_TOKEN,
      },
      body: JSON.stringify(body),
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
