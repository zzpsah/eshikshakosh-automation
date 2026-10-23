import { NextRequest, NextResponse } from "next/server";

const GATEWAY_URL = process.env.ESK_GATEWAY_URL ?? "";
const GATEWAY_TOKEN = process.env.ESK_GATEWAY_TOKEN ?? "";

const XLSX_TYPE =
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

/**
 * Streams the finished workbook.
 *
 * The signed download link is single-use and short-lived, so it is minted and
 * redeemed here, on the server. The browser only ever sees the job id.
 */
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
  const base = GATEWAY_URL.replace(/\/+$/, "");

  try {
    const statusRes = await fetch(`${base}/v1/reports/${encodeURIComponent(id)}`, {
      headers: { "x-report-token": GATEWAY_TOKEN },
      cache: "no-store",
    });
    const status = await statusRes.json().catch(() => ({}));
    if (!statusRes.ok) {
      return NextResponse.json(
        { error: status.error ?? "Gateway rejected the request." },
        { status: statusRes.status },
      );
    }
    if (status.status !== "done" || !status.download_url) {
      return NextResponse.json(
        { error: "Report is not ready yet." },
        { status: 409 },
      );
    }

    const fileRes = await fetch(`${base}/dl/${status.download_url}`, {
      headers: { "x-report-token": GATEWAY_TOKEN },
      cache: "no-store",
    });
    if (!fileRes.ok) {
      const detail = await fileRes.json().catch(() => ({}));
      return NextResponse.json(
        { error: detail.error ?? "Download failed." },
        { status: fileRes.status },
      );
    }

    const buf = await fileRes.arrayBuffer();
    const name = status.file_name || "report.xlsx";
    return new NextResponse(buf, {
      status: 200,
      headers: {
        "Content-Type": XLSX_TYPE,
        "Content-Length": String(buf.byteLength),
        "Content-Disposition": `attachment; filename="${name}"`,
        "Cache-Control": "no-store",
      },
    });
  } catch {
    return NextResponse.json(
      { error: "Report gateway is unreachable." },
      { status: 502 },
    );
  }
}
