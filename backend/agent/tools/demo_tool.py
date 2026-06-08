from langchain_core.tools import tool

from backend.agent.slots import build_date_options, generate_available_dates, format_date_display


def create_demo_tools(conversation_id: str):
    @tool
    def check_demo_slots() -> str:
        """Return available demo dates for MACE AI Academy (weekdays only)."""
        dates = generate_available_dates()
        if not dates:
            return "No demo dates available in the next few weeks. Ask the user to try again later."
        formatted = "\n".join(f"- {format_date_display(d)}" for d in dates[:10])
        return f"Available demo dates:\n{formatted}"

    @tool
    def book_demo_session(
        name: str,
        email: str,
        phone: str,
        course_interest: str,
        slot_datetime: str,
    ) -> str:
        """Book a free demo session. Requires name, email, phone, course_interest, and demo date (YYYY-MM-DD)."""
        from backend.agent.booking_workflow import execute_demo_booking

        result = execute_demo_booking(
            conversation_id=conversation_id,
            name=name.strip(),
            email=email.strip(),
            phone=phone.strip(),
            course_interest=course_interest.strip(),
            demo_date=slot_datetime.strip(),
        )
        return result["message"]

    return [check_demo_slots, book_demo_session]
