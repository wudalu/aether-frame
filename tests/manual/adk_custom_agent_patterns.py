#!/usr/bin/env python3
"""
ADK Custom Agent Implementation Example
Demonstrates recommended patterns for business logic implementation.
"""

import logging
from typing import AsyncGenerator
from typing_extensions import override

from google.adk.agents import LlmAgent, BaseAgent, LoopAgent, SequentialAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event

logger = logging.getLogger(__name__)

# =============================================================================
# Pattern 1: Complex Business Process Agent (Orchestration)
# =============================================================================

class LoanApprovalAgent(BaseAgent):
    """
    Custom agent for loan approval business process.
    
    Business Flow:
    1. Document Verification
    2. Credit Score Analysis  
    3. Risk Assessment
    4. Decision Making (with human approval for high amounts)
    5. Documentation Generation
    """
    
    # Pydantic field declarations
    document_verifier: LlmAgent
    credit_analyzer: LlmAgent
    risk_assessor: LlmAgent
    decision_maker: LlmAgent
    doc_generator: LlmAgent
    
    # Required Pydantic configuration
    model_config = {"arbitrary_types_allowed": True}
    
    def __init__(
        self,
        name: str,
        document_verifier: LlmAgent,
        credit_analyzer: LlmAgent, 
        risk_assessor: LlmAgent,
        decision_maker: LlmAgent,
        doc_generator: LlmAgent
    ):
        """Initialize loan approval agent with sub-agents."""
        
        # Create sub-agents list for the framework
        sub_agents_list = [
            document_verifier,
            credit_analyzer,
            risk_assessor, 
            decision_maker,
            doc_generator
        ]
        
        # Initialize with Pydantic validation
        super().__init__(
            name=name,
            document_verifier=document_verifier,
            credit_analyzer=credit_analyzer,
            risk_assessor=risk_assessor,
            decision_maker=decision_maker,
            doc_generator=doc_generator,
            sub_agents=sub_agents_list
        )
    
    @override
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """Implement loan approval business logic."""
        
        logger.info(f"[{self.name}] Starting loan approval process")
        
        # Stage 1: Document Verification
        logger.info(f"[{self.name}] Stage 1: Document Verification")
        async for event in self.document_verifier.run_async(ctx):
            logger.info(f"[{self.name}] Doc Verification Event: {event}")
            yield event
        
        # Check if documents are valid before proceeding
        doc_status = ctx.session.state.get("document_status")
        if doc_status != "valid":
            logger.error(f"[{self.name}] Documents invalid. Rejecting application.")
            ctx.session.state["final_decision"] = "REJECTED_INVALID_DOCUMENTS"
            return
        
        # Stage 2: Credit Score Analysis
        logger.info(f"[{self.name}] Stage 2: Credit Score Analysis")
        async for event in self.credit_analyzer.run_async(ctx):
            yield event
        
        # Stage 3: Risk Assessment
        logger.info(f"[{self.name}] Stage 3: Risk Assessment")
        async for event in self.risk_assessor.run_async(ctx):
            yield event
        
        # Stage 4: Decision Making with Business Rules
        logger.info(f"[{self.name}] Stage 4: Decision Making")
        
        # Business rule: High amount loans need special handling
        loan_amount = ctx.session.state.get("loan_amount", 0)
        credit_score = ctx.session.state.get("credit_score", 0)
        risk_level = ctx.session.state.get("risk_level", "unknown")
        
        # Custom business logic
        if loan_amount > 100000:  # High value loan
            logger.info(f"[{self.name}] High value loan detected: ${loan_amount}")
            ctx.session.state["requires_human_approval"] = True
            
        if credit_score < 600:  # Low credit score
            logger.info(f"[{self.name}] Low credit score: {credit_score}")
            ctx.session.state["auto_reject"] = True
            
        if risk_level == "high":
            logger.info(f"[{self.name}] High risk application detected")
            ctx.session.state["additional_review_required"] = True
        
        # Execute decision making
        async for event in self.decision_maker.run_async(ctx):
            yield event
        
        # Stage 5: Generate Documentation
        final_decision = ctx.session.state.get("final_decision")
        if final_decision in ["APPROVED", "CONDITIONALLY_APPROVED"]:
            logger.info(f"[{self.name}] Stage 5: Generating approval documentation")
            async for event in self.doc_generator.run_async(ctx):
                yield event
        
        logger.info(f"[{self.name}] Loan approval process completed")

# =============================================================================
# Pattern 2: Specialized Single-Purpose Agents
# =============================================================================

# Document verification agent
document_verifier = LlmAgent(
    name="DocumentVerifier",
    model="deepseek-chat",
    instruction="""You are a document verification specialist.
    
    VERIFICATION CHECKLIST:
    1. Check if all required documents are present: {required_documents}
    2. Validate document authenticity and completeness
    3. Verify personal information consistency
    4. Check document expiration dates
    
    DOCUMENTS TO VERIFY:
    {documents}
    
    OUTPUT FORMAT:
    - Status: "valid" or "invalid"  
    - Missing documents: list any missing items
    - Issues found: list any problems
    
    Be thorough and precise in your verification.""",
    
    input_schema={
        "required_documents": {"type": "array"},
        "documents": {"type": "object"}
    },
    output_key="document_status"
)

# Credit analysis agent
credit_analyzer = LlmAgent(
    name="CreditAnalyzer", 
    model="deepseek-chat",
    instruction="""You are a credit analysis expert.
    
    ANALYSIS FRAMEWORK:
    1. Calculate credit score from credit history: {credit_history}
    2. Analyze payment patterns and defaults
    3. Assess debt-to-income ratio: {monthly_income} vs {monthly_debts}
    4. Review employment stability: {employment_history}
    
    SCORING CRITERIA:
    - Excellent: 750-850
    - Good: 700-749  
    - Fair: 650-699
    - Poor: 600-649
    - Very Poor: below 600
    
    OUTPUT:
    - Credit score: numerical value
    - Credit rating: category
    - Key risk factors: list major concerns
    - Recommendations: suggestions for approval""",
    
    input_schema={
        "credit_history": {"type": "object"},
        "monthly_income": {"type": "number"},
        "monthly_debts": {"type": "number"},
        "employment_history": {"type": "object"}
    },
    output_key="credit_score"
)

# Risk assessment agent
risk_assessor = LlmAgent(
    name="RiskAssessor",
    model="deepseek-chat", 
    instruction="""You are a loan risk assessment specialist.
    
    RISK FACTORS TO EVALUATE:
    1. Credit score: {credit_score}
    2. Loan amount: {loan_amount}
    3. Income stability: {employment_history}
    4. Existing debt load: {existing_debts}
    5. Collateral value: {collateral}
    
    RISK LEVELS:
    - Low: Minimal default risk, strong financials
    - Medium: Moderate risk, acceptable with conditions
    - High: Significant risk, requires careful consideration
    
    ASSESSMENT CRITERIA:
    - Debt-to-income ratio > 40% = Higher risk
    - Credit score < 650 = Higher risk  
    - Unstable employment = Higher risk
    - Loan amount > 5x annual income = Higher risk
    
    OUTPUT:
    - Risk level: low/medium/high
    - Risk factors: list specific concerns
    - Mitigation strategies: suggest risk reduction approaches""",
    
    output_key="risk_level"
)

# Decision making agent
decision_maker = LlmAgent(
    name="DecisionMaker",
    model="deepseek-chat",
    instruction="""You are a loan decision specialist.
    
    DECISION INPUTS:
    - Document status: {document_status}
    - Credit score: {credit_score}
    - Risk level: {risk_level}
    - Loan amount: {loan_amount}
    - Special flags: {requires_human_approval}, {auto_reject}, {additional_review_required}
    
    DECISION RULES:
    1. If auto_reject = true → REJECT
    2. If requires_human_approval = true → PENDING_HUMAN_REVIEW
    3. If risk_level = "low" AND credit_score > 700 → APPROVE
    4. If risk_level = "medium" AND credit_score > 650 → CONDITIONALLY_APPROVE
    5. Otherwise → REJECT
    
    OUTPUT DECISIONS:
    - APPROVED: Full approval, standard terms
    - CONDITIONALLY_APPROVED: Approved with conditions/higher rate
    - PENDING_HUMAN_REVIEW: Requires human decision maker
    - REJECTED: Application denied
    
    Always provide clear reasoning for the decision.""",
    
    output_key="final_decision"
)

# Documentation generator
doc_generator = LlmAgent(
    name="DocumentationGenerator",
    model="deepseek-chat",
    instruction="""You are a loan documentation specialist.
    
    GENERATE DOCUMENTS FOR:
    Decision: {final_decision}
    Loan amount: {loan_amount}
    Applicant: {applicant_name}
    Terms: {loan_terms}
    
    DOCUMENT TYPES TO GENERATE:
    1. Approval Letter (for approved loans)
    2. Terms and Conditions document
    3. Next steps instructions
    4. Contact information for questions
    
    FORMAT: Professional, clear, legally compliant language.
    INCLUDE: All necessary disclosures and terms.""",
    
    output_key="generated_documents"
)

# =============================================================================
# Agent Factory Pattern for Easy Creation
# =============================================================================

def create_loan_approval_agent() -> LoanApprovalAgent:
    """Factory function to create a configured loan approval agent."""
    
    return LoanApprovalAgent(
        name="LoanApprovalAgent",
        document_verifier=document_verifier,
        credit_analyzer=credit_analyzer,
        risk_assessor=risk_assessor,
        decision_maker=decision_maker,
        doc_generator=doc_generator
    )

# =============================================================================
# Usage Example 
# =============================================================================

async def process_loan_application(loan_data: dict):
    """Example of how to use the custom agent."""
    
    from google.adk.sessions import InMemorySessionService
    from google.adk.runners import Runner
    from google.genai import types
    
    # Setup session with loan application data
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="loan_system",
        user_id=loan_data.get("applicant_id", "unknown"),
        session_id="loan_app_123",
        state=loan_data  # Initial loan application data
    )
    
    # Create and configure the agent
    loan_agent = create_loan_approval_agent()
    
    # Create runner
    runner = Runner(
        agent=loan_agent,
        app_name="loan_system",
        session_service=session_service
    )
    
    # Process the loan application
    content = types.Content(
        role='user', 
        parts=[types.Part(text=f"Please process loan application for ${loan_data['loan_amount']}")]
    )
    
    events = runner.run_async(
        user_id=loan_data.get("applicant_id", "unknown"),
        session_id="loan_app_123",
        new_message=content
    )
    
    # Process results
    async for event in events:
        if event.is_final_response() and event.content:
            print(f"Final Result: {event.content.parts[0].text}")
    
    # Get final session state
    final_session = await session_service.get_session(
        app_name="loan_system",
        user_id=loan_data.get("applicant_id", "unknown"),
        session_id="loan_app_123"
    )
    
    return final_session.state

# Example loan application data
SAMPLE_LOAN_DATA = {
    "applicant_id": "APP123456",
    "applicant_name": "John Doe", 
    "loan_amount": 75000,
    "loan_purpose": "home_improvement",
    "monthly_income": 8000,
    "monthly_debts": 2500,
    "credit_history": {"previous_loans": 3, "defaults": 0},
    "employment_history": {"current_job_years": 5, "total_experience": 12},
    "required_documents": ["income_proof", "id_document", "bank_statements"],
    "documents": {"income_proof": "present", "id_document": "present", "bank_statements": "present"}
}

if __name__ == "__main__":
    import asyncio
    
    # This would process a loan application
    # result = asyncio.run(process_loan_application(SAMPLE_LOAN_DATA))
    # print("Loan decision:", result.get("final_decision"))
    
    print("ADK Custom Agent patterns demonstrated:")
    print("✅ Complex orchestration with BaseAgent")  
    print("✅ Specialized LlmAgent for domain tasks")
    print("✅ State management with output_key")
    print("✅ Business rule integration")
    print("✅ Error handling and validation")
    print("✅ Factory pattern for agent creation")