from sqlalchemy import create_engine, text

# This creates a file called users.db in the current folder
engine = create_engine("sqlite:///users.db")

with engine.begin() as conn:
    # Create table
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            id_type TEXT NOT NULL,
            id_value TEXT NOT NULL
        )
    """))

    # Insert ONE test user
    conn.execute(text("""
        INSERT INTO users (user_id, id_type, id_value)
        VALUES (103, 'aadhaar', '342506531151')
    """))

print("✅ Database created: users.db")
print("✅ User added: user_id=102, PAN=ABCDE1234F")
