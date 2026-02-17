from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from app.modules.leads.application.use_cases.list_leads_use_case.state.leads_state import (
    graph,
)

llm = ChatOpenAI(model="gpt-4o-mini")

agent = create_react_agent(
    llm=llm,
    tools=[],
    state=graph,
)
