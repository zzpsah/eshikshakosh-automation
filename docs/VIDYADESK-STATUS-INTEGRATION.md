# VidyaDesk read-only job status contract

The eShikshaKosh jobserver provides a fixed-school, aggregate-only endpoint for VidyaDesk:

- `GET /v1/integrations/vidyadesk/status`
- Authentication: `X-Vidyadesk-Token: <dedicated server-only token>`
- Configuration: add `VIDYADESK_READ_TOKEN=<high-entropy-secret>` to `/home/prashant/.config/systemd/user/esk-jobserver.env` (the service EnvironmentFile).
- Scope: `umv-tetahali` / UDISE `10160203806` only.

The response contains contract version, a fixed school scope, total jobs, counts by status, stale queued/running counts, and epoch timestamps. Unknown job states mark the summary unhealthy. It never returns job IDs, class, student data, credentials, errors, workbook paths, filenames, or report contents. Jobs for other schools are excluded. A missing token denies access; the endpoint does not fall back to `JOB_SERVER_TOKEN`.

The endpoint is intended for the existing private VPS/tailnet path. Do not add a public Funnel route or configure the VidyaDesk token until the owner has reviewed the endpoint and approved the private server-to-server route. No token is provisioned, no service environment is edited, and no service restart is performed by this code change. The endpoint is not active until the dedicated token is configured and the jobserver is restarted.
