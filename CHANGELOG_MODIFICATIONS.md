## v1.1 - UX Improvements (May 1, 2026)

### Changed
- **Disabled auto-refresh** - UI no longer refreshes every 8 seconds (user controls refresh)
- **Show full IDs** - All UUIDs now display in full instead of truncated
- **Removed redundant Payload box** - Payload section removed from Event Detail
- **Auto-expand first successful delivery** - First delivery attempt expands by default to show payload

### Rationale
- Auto-refresh was disruptive and made the UI feel buggy
- Truncated IDs were not useful for debugging
- Redundant Payload box was unnecessary scrolling
- Auto-expanding first delivery provides immediate payload context