# tests/test_db_connection.py
from app.db.base import Base
from sqlalchemy import text


def test_database_connection(db_engine, db_session):
    """Test that we can connect to the database."""
    # Try to execute a simple query
    result = db_session.execute(text("SELECT 1")).scalar()
    assert result == 1

    # Check that we can create and query a simple table
    class TestTable(Base):
        __tablename__ = "test_table"
        from sqlalchemy import Column, Integer, String

        id = Column(Integer, primary_key=True)
        name = Column(String)

    # Create the table
    TestTable.__table__.create(db_engine, checkfirst=True)

    # Insert a row
    db_session.add(TestTable(name="test"))
    db_session.commit()

    # Query the table
    result = db_session.query(TestTable).filter_by(name="test").first()
    assert result is not None
    assert result.name == "test"
