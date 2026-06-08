from langchain_core.tools import tool

from backend.chatbot import create_lead


def create_crm_tool(conversation_id: str):
    @tool
    def save_lead_to_crm(
        name: str,
        email: str,
        phone: str,
        course_interest: str,
    ) -> str:
        """Save student lead information to CRM for counselor follow-up."""
        lead = create_lead(
            name=name.strip(),
            email=email.strip(),
            phone=phone.strip(),
            course_interest=course_interest.strip(),
        )
        from backend.agent.memory import set_memory

        set_memory(conversation_id, "name", name.strip())
        set_memory(conversation_id, "email", email.strip())
        set_memory(conversation_id, "phone", phone.strip())
        set_memory(conversation_id, "course_interest", course_interest.strip())
        return f"Lead saved to CRM (ID: {lead['id']}). Counselor will follow up soon."

    return save_lead_to_crm
