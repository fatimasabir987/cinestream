from app import create_app
from app.seed import seed_database

app = create_app()


@app.cli.command("seed")
def seed():
    """Load demo data (safe to run twice)."""
    if seed_database():
        print("Demo data loaded.")
    else:
        print("Database already seeded; nothing changed.")


if __name__ == "__main__":
    app.run(debug=True)
