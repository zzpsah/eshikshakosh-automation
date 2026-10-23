import { NextRequest, NextResponse } from "next/server";

const GATEWAY_URL = process.env.ESK_GATEWAY_URL ?? "";
const GATEWAY_TOKEN = process.env.ESK_GATEWAY_TOKEN ?? "";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  if (!GATEWAY_URL || !GATEWAY_TOKEN) {
    return NextResponse.json(
      { error: "Report gateway is not configured." },
      { status: 503 },
    );
  }
  const { id } = await params;

  try {
    const res = await fetch(`${GATEWAY_URL}/v1/reports/${encodeURIComponent(id)}`, {
      headers: { "x-report-token": GATEWAY_TOKEN },
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
