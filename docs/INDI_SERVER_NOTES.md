# Notes on internal INDI Server implementation

The `indipy*` ecosystem provides several tools that could be useful for this driver:

## 1. `indipyserver`
This package allows running the driver as a standalone network server without an external `indiserver`.
**Potential benefit**: Simplifies deployment for users who don't want to manage a full INDI stack manually. The driver could have a `--host` and `--port` CLI option to start its own server.

## 2. Web and Terminal interfaces
`indipyterm` and `indipyweb` provide alternative ways to interact with the driver properties.

## Judgment
Currently, the driver follows the standard INDI model where it can be run by an external `indiserver` via stdin/stdout. This is the most flexible approach for integration with Ekos/KStars. 

However, implementing an optional internal server mode using `indipyserver` is a planned "Quality of Life" improvement for **Phase 12**. This will be particularly useful for users connecting over WiFi directly to the driver.
