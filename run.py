from app import create_app
import os
from dotenv import load_dotenv

load_dotenv()

app = create_app()

if __name__ == "__main__":
    # Try to use configuration from database first
    host = app.config.get("FLASK_HOST", os.getenv("FLASK_HOST", "0.0.0.0"))
    port = int(app.config.get("FLASK_PORT", os.getenv("FLASK_PORT", 5000)))
    debug = app.config.get(
        "FLASK_DEBUG", os.getenv("FLASK_DEBUG", "False").lower() == "true"
    )

    app.run(
        host=host,
        port=port,
        debug=debug,
    )
