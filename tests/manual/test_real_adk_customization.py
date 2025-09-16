#!/usr/bin/env python3
"""
Real example of ADK agent customization with actual execution.
Shows how to implement custom business logic in ADK agents.
"""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from aether_frame.bootstrap import create_ai_assistant
from aether_frame.config.settings import Settings
from aether_frame.contracts import TaskRequest, UniversalMessage

async def test_customized_financial_advisor():
    """Test a real customized financial advisor ADK agent."""
    print("💰 TESTING CUSTOMIZED FINANCIAL ADVISOR ADK AGENT")
    print("="*60)
    
    # Custom system prompt with specific business logic
    financial_advisor_prompt = """You are a professional financial advisor AI with these SPECIFIC CAPABILITIES:

INVESTMENT ANALYSIS PROTOCOL:
1. Always assess risk tolerance first (Conservative/Moderate/Aggressive)
2. Consider age-based allocation: Age in bonds rule (30 years old = 30% bonds)
3. Recommend diversified portfolio with specific asset classes
4. Include emergency fund recommendations (3-6 months expenses)
5. Consider tax implications and retirement accounts

BUSINESS RULES:
- Maximum single stock recommendation: 5% of portfolio
- Always include index funds/ETFs for diversification  
- Provide specific percentage allocations
- Include timeline for review (quarterly/annually)
- Mention risk disclaimers

COMPLIANCE:
- Never guarantee returns
- Always mention market risks
- Suggest consulting licensed advisors for large amounts
- Include educational disclaimers

ANALYSIS FORMAT:
1. Risk Assessment
2. Asset Allocation Recommendation  
3. Specific Investment Vehicles
4. Implementation Timeline
5. Risk Warnings"""

    # Create task request with customized agent configuration
    task_request = TaskRequest(
        task_id="custom_financial_advisor_test",
        task_type="chat",
        description="Provide personalized investment advice",
        messages=[
            UniversalMessage(
                role="user",
                content="I'm 32 years old with $75,000 to invest. I have a stable job earning $80,000/year, no debt, and $15,000 emergency fund. I can handle moderate risk. Where should I invest this money?",
                metadata={"client_profile": "moderate_risk_professional"}
            )
        ],
        metadata={
            "preferred_model": "deepseek-chat",
            "framework": "adk", 
            "temperature": 0.3,  # Lower temperature for more structured financial advice
            "max_tokens": 1500,
            "agent_specialization": "financial_advisor",
            "system_prompt_override": financial_advisor_prompt,  # 🔑 Custom prompt
            "business_domain": "finance",
            "compliance_mode": "strict"
        }
    )
    
    print("📋 Task Configuration:")
    print(f"   Client Age: 32, Investment: $75,000")
    print(f"   Risk Profile: Moderate")
    print(f"   Custom Prompt Length: {len(financial_advisor_prompt)} chars")
    print(f"   Temperature: 0.3 (structured advice)")
    
    # Initialize system
    print(f"\n🚀 Initializing Financial Advisory System...")
    settings = Settings()
    assistant = await create_ai_assistant(settings)
    
    # Execute with custom configuration
    print(f"\n💼 Executing Financial Analysis...")
    
    try:
        result = await asyncio.wait_for(
            assistant.process_request(task_request),
            timeout=30.0
        )
        
        print(f"\n📊 FINANCIAL ADVICE RESULT:")
        print(f"Status: {result.status}")
        
        if result.messages and result.messages[0].content:
            advice = result.messages[0].content
            print(f"\n💰 INVESTMENT ADVICE:")
            print("="*60)
            print(advice)
            print("="*60)
            
            # Analyze if custom logic was applied
            custom_elements = {
                "risk_assessment": any(word in advice.lower() for word in ["risk tolerance", "moderate risk", "conservative", "aggressive"]),
                "age_allocation": any(word in advice.lower() for word in ["age", "bond", "allocation", "32"]),
                "diversification": any(word in advice.lower() for word in ["diversif", "index fund", "etf", "asset class"]),
                "emergency_fund": any(word in advice.lower() for word in ["emergency", "15,000", "emergency fund"]),
                "percentages": "%" in advice,
                "disclaimers": any(word in advice.lower() for word in ["disclaimer", "risk", "guarantee", "consult"])
            }
            
            print(f"\n🔍 CUSTOM LOGIC VERIFICATION:")
            for element, found in custom_elements.items():
                status = "✅" if found else "❌"
                print(f"{status} {element.replace('_', ' ').title()}: {'Found' if found else 'Missing'}")
            
            applied_count = sum(custom_elements.values())
            print(f"\n📈 Custom Business Logic Applied: {applied_count}/6 elements")
            
            if applied_count >= 4:
                print("🎉 SUCCESS: Custom financial advisor logic working!")
            else:
                print("⚠️ WARNING: Some custom logic elements missing")
                
        else:
            print("❌ No advice generated")
            
    except asyncio.TimeoutError:
        print("⏰ Request timed out")
    except Exception as e:
        print(f"❌ Error: {e}")

async def test_customized_code_reviewer():
    """Test a real customized code reviewer ADK agent."""
    print("\n\n🔍 TESTING CUSTOMIZED CODE REVIEWER ADK AGENT")
    print("="*60)
    
    # Custom system prompt for code review
    code_reviewer_prompt = """You are an expert code reviewer with SPECIFIC ANALYSIS PROTOCOLS:

REVIEW CHECKLIST:
1. SECURITY: Check for SQL injection, XSS, buffer overflows, input validation
2. PERFORMANCE: Analyze time/space complexity, identify bottlenecks  
3. MAINTAINABILITY: Code structure, naming conventions, documentation
4. BUGS: Logic errors, edge cases, null pointer exceptions
5. BEST PRACTICES: Language-specific idioms, design patterns
6. TESTING: Test coverage implications, testability

OUTPUT FORMAT:
🔴 CRITICAL Issues (security vulnerabilities, major bugs)
🟡 MODERATE Issues (performance, maintainability)  
🟢 MINOR Issues (style, optimization suggestions)
📋 SUMMARY with prioritized action items

ANALYSIS DEPTH:
- Line-by-line review for critical sections
- Suggest specific code improvements with examples
- Rate overall code quality (1-10)
- Estimate fix effort (Low/Medium/High)"""

    code_to_review = """
def process_user_data(user_input, database_conn):
    # Process user registration data
    query = "INSERT INTO users (name, email) VALUES ('" + user_input['name'] + "', '" + user_input['email'] + "')"
    
    result = database_conn.execute(query)
    
    if result:
        return {"status": "success", "user_id": result.lastrowid}
    else:
        return {"status": "error"}
        
def calculate_discount(price, user_type):
    if user_type == "premium":
        discount = price * 0.2
    elif user_type == "regular":
        discount = price * 0.1
    
    return price - discount
"""

    task_request = TaskRequest(
        task_id="custom_code_review_test",
        task_type="chat", 
        description="Perform comprehensive code security and quality review",
        messages=[
            UniversalMessage(
                role="user",
                content=f"Please perform a comprehensive code review on this Python code:\n\n```python\n{code_to_review}\n```",
                metadata={"code_language": "python", "review_type": "security_focused"}
            )
        ],
        metadata={
            "preferred_model": "deepseek-chat",
            "framework": "adk",
            "temperature": 0.2,  # Very structured for code analysis
            "max_tokens": 2000,
            "agent_specialization": "code_reviewer",  
            "system_prompt_override": code_reviewer_prompt,  # 🔑 Custom prompt
            "business_domain": "software_security",
            "analysis_depth": "comprehensive"
        }
    )
    
    print("📋 Code Review Configuration:")
    print(f"   Code Length: {len(code_to_review)} chars")
    print(f"   Language: Python")
    print(f"   Focus: Security & Quality")
    print(f"   Temperature: 0.2 (precise analysis)")
    
    # Execute code review
    print(f"\n🔍 Executing Code Review Analysis...")
    
    try:
        settings = Settings()
        assistant = await create_ai_assistant(settings)
        
        result = await asyncio.wait_for(
            assistant.process_request(task_request),
            timeout=30.0
        )
        
        print(f"\n📊 CODE REVIEW RESULT:")
        print(f"Status: {result.status}")
        
        if result.messages and result.messages[0].content:
            review = result.messages[0].content
            print(f"\n🔍 CODE REVIEW ANALYSIS:")
            print("="*60)
            print(review)
            print("="*60)
            
            # Check if custom review elements were applied
            review_elements = {
                "security_analysis": any(word in review.lower() for word in ["sql injection", "security", "vulnerability", "xss"]),
                "performance_analysis": any(word in review.lower() for word in ["performance", "complexity", "optimization"]),
                "maintainability": any(word in review.lower() for word in ["maintainability", "readable", "structure"]),
                "bug_detection": any(word in review.lower() for word in ["bug", "error", "exception", "edge case"]),
                "severity_levels": any(word in review.lower() for word in ["critical", "moderate", "minor", "🔴", "🟡", "🟢"]),
                "specific_suggestions": any(word in review.lower() for word in ["suggest", "recommend", "fix", "improve"])
            }
            
            print(f"\n🔍 CUSTOM REVIEW LOGIC VERIFICATION:")
            for element, found in review_elements.items():
                status = "✅" if found else "❌"
                print(f"{status} {element.replace('_', ' ').title()}: {'Found' if found else 'Missing'}")
            
            applied_count = sum(review_elements.values())
            print(f"\n📈 Custom Review Logic Applied: {applied_count}/6 elements")
            
            if applied_count >= 4:
                print("🎉 SUCCESS: Custom code reviewer logic working!")
            else:
                print("⚠️ WARNING: Some custom review elements missing")
                
        else:
            print("❌ No review generated")
            
    except asyncio.TimeoutError:
        print("⏰ Request timed out")
    except Exception as e:
        print(f"❌ Error: {e}")

async def main():
    """Run all customized agent tests."""
    print("🎯 ADK AGENT CUSTOMIZATION REAL EXECUTION TEST")
    print("="*80)
    
    # Test 1: Financial Advisor with custom business logic
    await test_customized_financial_advisor()
    
    # Test 2: Code Reviewer with custom analysis protocols  
    await test_customized_code_reviewer()
    
    print(f"\n\n🎉 ADK CUSTOMIZATION TESTS COMPLETED!")
    print("="*80)
    print("Key Customization Methods Demonstrated:")
    print("✅ Custom System Prompts with Domain-Specific Instructions")
    print("✅ Business Rules Integration via Natural Language") 
    print("✅ Structured Output Formats")
    print("✅ Temperature Control for Different Use Cases")
    print("✅ Metadata-Driven Agent Specialization")
    print("✅ Custom Verification and Quality Checks")

if __name__ == "__main__":
    asyncio.run(main())