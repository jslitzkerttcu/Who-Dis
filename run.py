from app import create_app
from dotenv import load_dotenv

load_dotenv()

app = create_app()

if __name__ == "__main__":
    # Use configuration from database
    from app.services.simple_config import config_get

    host = config_get("flask.host", "0.0.0.0")
    port = int(config_get("flask.port", "5000"))
    debug_value = config_get("flask.debug", "False")
    debug = str(debug_value).lower() == "true"

    app.run(
        host=host,
        port=port,
        debug=debug,
    )
