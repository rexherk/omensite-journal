"""Apply the journal schema to the database selected by DATABASE_URL."""

from app import db


def main():
    with db.session() as conn:
        db.init_db(conn)
    print("Omensite Journal schema is ready.")


if __name__ == "__main__":
    main()
