"""Start the Realestate Com Au Scraper API.

    python run.py            # http://localhost:8000
    PORT=9000 python run.py  # another port

Then:  curl "http://localhost:8000/properties/details?listing=152396892"

The first request opens Google Chrome for ~10 seconds to pass Kasada; every
request after that runs over plain HTTP.
"""
import bottle
from cheroot import wsgi

import config
import routes  # noqa: F401  (mounts the routes on bottle's default app)


def main():
    app = bottle.default_app()
    print(f"Realestate Com Au Scraper listening on http://localhost:{config.PORT}/")
    print(f"Try:  curl \"http://localhost:{config.PORT}/properties/details?listing=152396892\"")
    server = wsgi.Server(("0.0.0.0", config.PORT), app, server_name="realestate-com-au-scraper", numthreads=16)
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()


if __name__ == "__main__":
    main()
