from fastapi import FastAPI, Body
import requests
import json
import logging
from typing import Dict, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Phishing Detection Orchestrator")

# Configuration Replace 10.174.188.11 with your LLM VM IP address
AGENT_ENDPOINTS = {
    "content": "http://10.174.188.11:8001/analyze",
    "url": "http://10.174.188.11:8002/analyze",
    "header": "http://10.174.188.11:8003/analyze"
}

def call_agent(agent_name: str, email_text: str) -> Dict:
    """
    Call a specific agent and return its analysis.
    
    Args:
        agent_name: Name of the agent (content, url, header)
        email_text: The email content to analyze
        
    Returns:
        Agent's analysis response
    """
    try:
        url = AGENT_ENDPOINTS[agent_name]
        response = requests.post(
            url,
            json={"email_text": email_text},
            timeout=300  # 5 minute timeout per agent
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return {
                "agent": agent_name,
                "status": "error", 
                "error": f"HTTP {response.status_code}: {response.text}"
            }
            
    except requests.exceptions.Timeout:
        return {
            "agent": agent_name,
            "status": "error",
            "error": "Request timeout"
        }
    except Exception as e:
        return {
            "agent": agent_name,
            "status": "error",
            "error": str(e)
        }

def calculate_final_verdict(agent_results: Dict) -> Dict:
    """
    Synthesize all agent results into a final verdict.
    
    Args:
        agent_results: Results from all agents
        
    Returns:
        Final verdict and consolidated analysis
    """
    verdicts = []
    risk_scores = []
    all_reasons = []
    
    # Collect data from successful agent analyses
    for agent_name, result in agent_results.items():
        if result.get("status") == "success":
            analysis = result.get("analysis", {})
            
            # Extract verdict
            verdict = analysis.get("verdict", "unknown")
            verdicts.append(verdict)
            
            # Extract risk score
            risk_score = analysis.get("risk_score", 0)
            risk_scores.append(risk_score)
            
            # Extract reasons
            reasons = analysis.get("reasons", [])
            if isinstance(reasons, list):
                all_reasons.extend(reasons)
            elif isinstance(reasons, str):
                all_reasons.append(reasons)
    
    # Calculate final risk score (average of all agents)
    final_risk_score = sum(risk_scores) / len(risk_scores) if risk_scores else 0
    
    # Determine final verdict based on agent consensus
    if final_risk_score >= 70:
        final_verdict = "malicious"
    elif final_risk_score >= 40:
        final_verdict = "suspicious" 
    else:
        final_verdict = "safe"
    
    # If any agent says malicious, elevate the verdict
    if "malicious" in verdicts:
        final_verdict = "malicious"
        final_risk_score = max(final_risk_score, 80)
    
    return {
        "final_verdict": final_verdict,
        "final_risk_score": round(final_risk_score),
        "confidence": "high" if len(risk_scores) >= 2 else "medium",
        "summary_reasons": list(set(all_reasons))[:5],  # Remove duplicates, proritize the top 5
        "agents_consulted": len([r for r in agent_results.values() if r.get("status") == "success"])
    }

@app.post("/analyze-email")
async def analyze_email(email_text: str = Body(..., embed=True)):
    """
    Main endpoint that orchestrates phishing detection across all agents.
    
    Args:
        email_text: Raw email content to analyze
        
    Returns:
        Consolidated analysis from all agents
    """
    logger.info("Received email for analysis")
    
    # Call all agents in sequence
    agent_results = {}
    
    for agent_name in AGENT_ENDPOINTS.keys():
        logger.info(f"Calling {agent_name} agent...")
        result = call_agent(agent_name, email_text)
        agent_results[agent_name] = result
        logger.info(f"{agent_name} agent completed with status: {result.get('status')}")
    
    # Calculate final verdict
    final_analysis = calculate_final_verdict(agent_results)
    
    # Prepare response
    response = {
        "status": "complete",
        "final_analysis": final_analysis,
        "agent_details": agent_results,
        "timestamp": __import__('datetime').datetime.now().isoformat()
    }
    
    logger.info(f"Analysis complete. Final verdict: {final_analysis['final_verdict']}")
    return response

@app.get("/health")
async def health_check():
    """
    Health check endpoint to verify all agents are reachable.
    """
    status = {}
    for agent_name, url in AGENT_ENDPOINTS.items():
        try:
            response = requests.get(url.replace('/analyze', '/docs'), timeout=5)
            status[agent_name] = "healthy" if response.status_code == 200 else "unhealthy"
        except:
            status[agent_name] = "unreachable"
    
    return {
        "orchestrator": "healthy",
        "agents": status
    }

if __name__ == "__main__":
    import uvicorn
    # Run on port 8000 - this is your main API endpoint
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
