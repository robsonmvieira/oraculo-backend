from typing import TypedDict

from langgraph.graph import END, START, StateBuilder

from app.models.lead import Lead


class LeadsState(TypedDict):
    """
    Estado para listar leads
    """

    leads: list[Lead]


def add_lead_node(lead: Lead, state: LeadsState) -> LeadsState:
    """
    Adiciona um lead ao estado
    """
    return {"leads": [*state["leads"], lead]}


def get_leads(state: LeadsState) -> list[Lead]:
    """
    Retorna a lista de leads
    """
    return state["leads"]


def get_lead_by_id(id: str, state: LeadsState) -> Lead | None:
    """
    Retorna um lead pelo ID
    """
    return next((lead for lead in state["leads"] if lead.id == id), None)


def get_lead_by_email(email: str, state: LeadsState) -> Lead | None:
    """
    Retorna um lead pelo email
    """
    return next((lead for lead in state["leads"] if lead.email == email), None)


builder = StateBuilder(LeadsState)

builder.add_node("add_lead", add_lead_node)
builder.add_node("get_leads", get_leads)
builder.add_node("get_lead_by_id", get_lead_by_id)
builder.add_node("get_lead_by_email", get_lead_by_email)

builder.add_edge(START, "add_lead")
builder.add_edge("add_lead", "get_leads")
builder.add_edge("get_leads", END)
builder.add_edge("get_lead_by_id", END)
builder.add_edge("get_lead_by_email", END)
graph = builder.compile()
