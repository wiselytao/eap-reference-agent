import os
from reference_agent.app import create_app, build_service

app = create_app()

if __name__ == "__main__":
    import uvicorn

    service = build_service()
    tls = service.config.tls
    kwargs = {"host": "0.0.0.0", "port": service.config.runtime.port}
    if tls.enabled:
        if not tls.certfile or not tls.keyfile:
            raise ValueError("TLS enabled but certfile/keyfile not configured.")
        kwargs["ssl_certfile"] = tls.certfile
        kwargs["ssl_keyfile"] = tls.keyfile
    uvicorn.run("reference_agent.main:app", **kwargs)
