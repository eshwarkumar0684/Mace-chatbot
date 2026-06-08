"""Demo date booking tests — duplicate prevention."""

from backend.agent.memory import init_agent_tables, reserve_booking
from backend.agent.slots import format_date_display, generate_available_dates, normalize_demo_date
from backend.agent.booking_workflow import execute_demo_booking
from backend import chatbot


def _setup():
    init_agent_tables()


def test_generate_weekday_dates():
    _setup()
    dates = generate_available_dates()
    assert dates, "need at least one date"
    assert all(len(d) == 10 for d in dates)
    assert format_date_display(dates[0]).count(",") == 1
    print("PASS generate weekday dates")


def test_duplicate_email_same_date_blocked():
    _setup()
    dates = generate_available_dates()
    date = dates[0]
    conv1 = chatbot.create_conversation("User A")["id"]
    conv2 = chatbot.create_conversation("User B")["id"]

    first = reserve_booking(
        conv1, "Eshwar", "eshwar@example.com", "9999999999", "AI & ML", date
    )
    assert first is not None

    second = reserve_booking(
        conv2, "Eshwar K", "eshwar@example.com", "8888888888", "Data Science", date
    )
    assert second is None, "duplicate email+date should be blocked"
    print("PASS duplicate email same date blocked")


def test_booking_workflow_returns_duplicate_conflict():
    _setup()
    dates = generate_available_dates()
    date = dates[1]
    conv1 = chatbot.create_conversation("Book A")["id"]
    conv2 = chatbot.create_conversation("Book B")["id"]

    ok = execute_demo_booking(
        conversation_id=conv1,
        name="Priya",
        email="priya@example.com",
        phone="7777777777",
        course_interest="AI & ML",
        demo_date=date,
    )
    assert ok["ok"] is True

    dup = execute_demo_booking(
        conversation_id=conv2,
        name="Priya S",
        email="priya@example.com",
        phone="6666666666",
        course_interest="Data Science",
        demo_date=date,
    )
    assert dup["ok"] is False
    assert dup["code"] == "duplicate_booking"
    assert dup["alternatives"]
    print("PASS workflow duplicate conflict")


if __name__ == "__main__":
    test_generate_weekday_dates()
    test_duplicate_email_same_date_blocked()
    test_booking_workflow_returns_duplicate_conflict()
    print("All demo date tests passed.")
