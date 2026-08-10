"""Entry point for kid-net-guard."""

import uvicorn


def main():
    uvicorn.run(
        "kid_net_guard:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
