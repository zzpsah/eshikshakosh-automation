import { NextResponse } from "next/server";

const GATEWAY_URL = process.env.ESK_GATEWAY_URL ?? "";
const GATEWAY_TOKEN = process.env.ESK_GATEWAY_TOKEN ?? "";

function configured() {
  return Boolean(GATEWAY_URL && GATEWAY_TOKEN);
}

/** Workflows, schools, classes and modes — served by the gateway, not hardcoded. */
export async function GET() {
  if (!configured()) {
    return NextResponse.json(
      { error: "Report gateway is not configured." },
      { status: 503 },
    );
  }

  try {
    const res = await fetch(`${GATEWAY_URL}/v1/config`, {
      headers: { "x-report-token": GATEWAY_TOKEN },
      cache: "no-store",
    });
    const data = await res.json();
    if (!res.ok) {
      return NextResponse.json(
        { error: data.error ?? "Gateway rejected the request." },
        { status: res.status },
      );
    }
    return NextResponse.json(data);
  } catch {
    return NextResponse.json(
      { error: "Report gateway is unreachable." },
      { status: 502 },
    );
  }
}
