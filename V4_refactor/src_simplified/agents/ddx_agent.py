from .base_agent import BaseAgent
from ..prompts import DDX_DEEP_DIVE_SYSTEM_PROMPT
from ..tools.csv_tool import CSVTool


class DdxAgent(BaseAgent):
    """Differential diagnosis deep-dive agent.

    Runs a Socratic discussion helping the student differentiate between
    plausible diagnoses based on clinical presentations and investigations
    (not pathophysiology -- that belongs to PathophysEpiAgent).
    """

    def __init__(self, case_data: str, organism_name: str, csv_tool: CSVTool | None = None, model: str | None = None):
        super().__init__("ddx_deep_dive", model=model)
        self.case_data = case_data
        self.organism_name = organism_name
        self.csv_tool = csv_tool or CSVTool()

        factors = self.csv_tool.get_crucial_factors(self.organism_name)
        factors_str = ", ".join(factors) if factors else "None identified"

        self.system_prompt = DDX_DEEP_DIVE_SYSTEM_PROMPT.format(
            case=self.case_data,
            csv_guidance=factors_str,
        )

    def chat(self, user_input: str) -> str:
        return super().chat(user_input, self.system_prompt)
