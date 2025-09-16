#!/usr/bin/env python3
"""
Example of customizing ADK agents with specific business logic.
Shows different ways to add custom behavior to ADK agents.
"""

import asyncio
import sys
import os
from datetime import datetime
from typing import Dict, Any, List

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from aether_frame.bootstrap import create_ai_assistant
from aether_frame.config.settings import Settings
from aether_frame.contracts import TaskRequest, UniversalMessage, UniversalTool

class CustomizedAdkAgent:
    """Example of how to customize ADK agents with specific business logic."""
    
    def __init__(self):
        self.custom_tools = []
        self.business_rules = {}
        self.domain_knowledge = {}
    
    def create_specialized_agent_config(self, agent_type: str, domain: str) -> Dict[str, Any]:
        """Create specialized agent configuration based on agent type and domain."""
        
        configs = {
            "financial_advisor": {
                "system_prompt": self._build_financial_advisor_prompt(),
                "tools": self._get_financial_tools(),
                "business_rules": {
                    "max_investment_recommendation": 1000000,
                    "risk_tolerance_levels": ["conservative", "moderate", "aggressive"],
                    "compliance_checks": True
                },
                "domain_knowledge": {
                    "financial_regulations": "SEC, FINRA compliance required",
                    "market_data_sources": ["Bloomberg", "Yahoo Finance"],
                    "analysis_frameworks": ["DCF", "P/E ratio", "Technical analysis"]
                }
            },
            
            "medical_assistant": {
                "system_prompt": self._build_medical_assistant_prompt(),
                "tools": self._get_medical_tools(),
                "business_rules": {
                    "disclaimer_required": True,
                    "prescription_forbidden": True,
                    "emergency_protocols": True
                },
                "domain_knowledge": {
                    "medical_databases": ["PubMed", "Mayo Clinic"],
                    "symptom_checker_limits": "General information only",
                    "referral_guidelines": "Always suggest consulting healthcare provider"
                }
            },
            
            "code_reviewer": {
                "system_prompt": self._build_code_reviewer_prompt(),
                "tools": self._get_coding_tools(),
                "business_rules": {
                    "languages_supported": ["python", "javascript", "java", "go"],
                    "security_scan_required": True,
                    "performance_analysis": True
                },
                "domain_knowledge": {
                    "coding_standards": ["PEP8", "ESLint", "SonarQube"],
                    "security_frameworks": ["OWASP", "CWE"],
                    "performance_metrics": ["Big-O complexity", "Memory usage"]
                }
            }
        }
        
        return configs.get(agent_type, self._get_default_config())
    
    def _build_financial_advisor_prompt(self) -> str:
        """Build specialized system prompt for financial advisor."""
        return """You are a professional financial advisor AI assistant with the following capabilities:

CORE EXPERTISE:
- Investment analysis and portfolio management
- Risk assessment and mitigation strategies  
- Financial planning and retirement advice
- Market analysis and trend identification

BUSINESS RULES:
- Always include appropriate disclaimers about investment risks
- Never guarantee specific returns or outcomes
- Emphasize diversification and risk management
- Suggest consulting with licensed professionals for major decisions

ANALYSIS FRAMEWORK:
1. Assess client's financial goals and risk tolerance
2. Analyze current market conditions and trends
3. Provide evidence-based recommendations
4. Include multiple scenario planning
5. Highlight potential risks and mitigation strategies

COMPLIANCE:
- Follow SEC and FINRA guidelines
- Provide educational information, not personalized advice
- Include standard investment disclaimers
- Maintain client confidentiality

Remember to be thorough, objective, and always prioritize the client's best interests."""

    def _build_medical_assistant_prompt(self) -> str:
        """Build specialized system prompt for medical assistant."""
        return """You are a medical information assistant with the following responsibilities:

CORE PURPOSE:
- Provide general health information and education
- Help users understand medical concepts and terminology
- Assist with symptom awareness and health maintenance
- Support informed healthcare decision-making

STRICT LIMITATIONS:
- NEVER provide specific medical diagnoses
- NEVER recommend specific treatments or medications
- NEVER replace professional medical consultation
- ALWAYS encourage users to consult healthcare providers

INFORMATION SOURCES:
- Evidence-based medical literature
- Peer-reviewed research studies
- Established medical organizations (WHO, CDC, Mayo Clinic)
- Current clinical guidelines and best practices

RESPONSE PROTOCOL:
1. Provide accurate, general medical information
2. Explain complex medical terms in simple language
3. Include appropriate medical disclaimers
4. Suggest when professional consultation is needed
5. Emphasize emergency protocols when relevant

EMERGENCY PROTOCOL:
- If user describes emergency symptoms, immediately advise calling emergency services
- Provide first aid information when appropriate
- Never delay emergency care with extended discussions"""

    def _build_code_reviewer_prompt(self) -> str:
        """Build specialized system prompt for code reviewer."""
        return """You are an expert code reviewer AI with comprehensive programming knowledge:

REVIEW AREAS:
- Code quality and best practices
- Security vulnerabilities and risks
- Performance optimization opportunities
- Maintainability and readability
- Documentation and testing coverage

ANALYSIS FRAMEWORK:
1. FUNCTIONALITY: Does the code work as intended?
2. SECURITY: Are there any security vulnerabilities?
3. PERFORMANCE: Can the code be optimized?
4. MAINTAINABILITY: Is the code clean and well-structured?
5. TESTING: Is there adequate test coverage?
6. DOCUMENTATION: Is the code properly documented?

SUPPORTED LANGUAGES:
- Python, JavaScript, Java, Go, C++, C#, Ruby, PHP
- Web technologies (HTML, CSS, SQL)
- DevOps tools (Docker, Kubernetes, CI/CD)

SECURITY FOCUS:
- OWASP Top 10 vulnerabilities
- Input validation and sanitization
- Authentication and authorization issues
- Data privacy and protection
- Secure coding practices

OUTPUT FORMAT:
- Provide specific line-by-line feedback
- Categorize issues by severity (Critical, High, Medium, Low)
- Suggest concrete improvements
- Include code examples when helpful
- Prioritize actionable recommendations"""

    def _get_financial_tools(self) -> List[UniversalTool]:
        """Get financial analysis tools."""
        return [
            UniversalTool(
                name="portfolio_analyzer",
                description="Analyze investment portfolio risk and return",
                parameters_schema={
                    "portfolio": {"type": "object", "description": "Portfolio holdings"},
                    "time_horizon": {"type": "string", "description": "Investment timeframe"},
                    "risk_tolerance": {"type": "string", "description": "Risk level"}
                }
            ),
            UniversalTool(
                name="market_data_fetcher", 
                description="Fetch current market data and trends",
                parameters_schema={
                    "symbols": {"type": "array", "description": "Stock/ETF symbols"},
                    "timeframe": {"type": "string", "description": "Data timeframe"}
                }
            ),
            UniversalTool(
                name="risk_calculator",
                description="Calculate investment risk metrics",
                parameters_schema={
                    "investment_amount": {"type": "number", "description": "Investment amount"},
                    "asset_allocation": {"type": "object", "description": "Asset allocation"}
                }
            )
        ]
    
    def _get_medical_tools(self) -> List[UniversalTool]:
        """Get medical information tools."""
        return [
            UniversalTool(
                name="symptom_checker",
                description="Provide general information about symptoms",
                parameters_schema={
                    "symptoms": {"type": "array", "description": "List of symptoms"},
                    "age_range": {"type": "string", "description": "Patient age range"}
                }
            ),
            UniversalTool(
                name="drug_interaction_checker",
                description="Check for potential drug interactions",
                parameters_schema={
                    "medications": {"type": "array", "description": "List of medications"}
                }
            ),
            UniversalTool(
                name="health_info_lookup",
                description="Look up general health information",
                parameters_schema={
                    "condition": {"type": "string", "description": "Health condition or topic"}
                }
            )
        ]
    
    def _get_coding_tools(self) -> List[UniversalTool]:
        """Get code analysis tools."""
        return [
            UniversalTool(
                name="static_analysis",
                description="Perform static code analysis",
                parameters_schema={
                    "code": {"type": "string", "description": "Code to analyze"},
                    "language": {"type": "string", "description": "Programming language"}
                }
            ),
            UniversalTool(
                name="security_scanner",
                description="Scan code for security vulnerabilities",
                parameters_schema={
                    "code": {"type": "string", "description": "Code to scan"},
                    "scan_type": {"type": "string", "description": "Type of security scan"}
                }
            ),
            UniversalTool(
                name="performance_profiler",
                description="Analyze code performance characteristics",
                parameters_schema={
                    "code": {"type": "string", "description": "Code to profile"},
                    "metrics": {"type": "array", "description": "Performance metrics to analyze"}
                }
            )
        ]
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration for generic agents."""
        return {
            "system_prompt": "You are a helpful AI assistant.",
            "tools": [],
            "business_rules": {},
            "domain_knowledge": {}
        }

async def test_customized_agents():
    """Test different types of customized ADK agents."""
    print("🎯 TESTING CUSTOMIZED ADK AGENTS")
    print("="*60)
    
    customizer = CustomizedAdkAgent()
    
    # Test scenarios for different agent types
    test_scenarios = [
        {
            "agent_type": "financial_advisor",
            "task_id": "financial_analysis",
            "description": "Provide investment portfolio analysis",
            "user_message": "I have $50,000 to invest and I'm 30 years old. What should I consider?",
            "metadata": {
                "preferred_model": "deepseek-chat",
                "agent_specialization": "financial_advisor",
                "domain": "finance"
            }
        },
        {
            "agent_type": "medical_assistant", 
            "task_id": "medical_info",
            "description": "Provide general medical information",
            "user_message": "What should I know about managing high blood pressure?",
            "metadata": {
                "preferred_model": "deepseek-chat",
                "agent_specialization": "medical_assistant",
                "domain": "healthcare"
            }
        },
        {
            "agent_type": "code_reviewer",
            "task_id": "code_review",
            "description": "Review and analyze code quality",
            "user_message": "Please review this Python function for potential issues:\n\ndef process_data(data):\n    result = []\n    for i in range(len(data)):\n        if data[i] > 0:\n            result.append(data[i] * 2)\n    return result",
            "metadata": {
                "preferred_model": "deepseek-chat",
                "agent_specialization": "code_reviewer",
                "domain": "software_development"
            }
        }
    ]
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n🔍 TEST {i}: {scenario['agent_type'].upper()}")
        print("-" * 40)
        
        # Get specialized configuration
        agent_config = customizer.create_specialized_agent_config(
            scenario["agent_type"], 
            scenario["metadata"]["domain"]
        )
        
        print(f"Agent Type: {scenario['agent_type']}")
        print(f"System Prompt: {agent_config['system_prompt'][:100]}...")
        print(f"Available Tools: {len(agent_config['tools'])}")
        print(f"Business Rules: {len(agent_config['business_rules'])} rules")
        
        # Create task request with specialized configuration
        task_request = TaskRequest(
            task_id=scenario["task_id"],
            task_type="chat",
            description=scenario["description"],
            messages=[
                UniversalMessage(
                    role="user",
                    content=scenario["user_message"],
                    metadata={"agent_type": scenario["agent_type"]}
                )
            ],
            available_tools=agent_config["tools"],
            metadata={
                **scenario["metadata"],
                "system_prompt": agent_config["system_prompt"],
                "business_rules": agent_config["business_rules"],
                "domain_knowledge": agent_config["domain_knowledge"]
            }
        )
        
        print(f"Task Created: {task_request.task_id}")
        print(f"User Message: {scenario['user_message'][:100]}...")
        
        # For this demo, we don't actually execute to avoid network calls
        # but show how the customization would work
        print("✅ Customized agent configuration prepared")
        
        # Show how tools would be integrated
        if agent_config["tools"]:
            print(f"🔧 Specialized Tools Available:")
            for tool in agent_config["tools"]:
                print(f"   - {tool.name}: {tool.description}")
    
    print(f"\n📊 CUSTOMIZATION SUMMARY")
    print("="*60)
    print("✅ Financial Advisor: Investment analysis with compliance rules")
    print("✅ Medical Assistant: Health information with safety protocols")  
    print("✅ Code Reviewer: Code analysis with security scanning")
    print("\n🎉 All customized agent configurations prepared successfully!")

if __name__ == "__main__":
    asyncio.run(test_customized_agents())