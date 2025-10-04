from fastapi import FastAPI, Body
import subprocess
import json
import re

app = FastAPI(title="Content Analysis Agent")

def extract_json_from_response(llm_output: str) -> dict:
    """
    This cleans and parses the LLM's response to extract valid JSON.
    This handles cases where LLM returns text with JSON embedded.
    """
    try:
        # Trying to find JSON pattern in the response
        json_match = re.search(r'\{[^{}]*\{[^{}]*\}[^{}]*\}|\{[^{}]*\}', llm_output, re.DOTALL)
        
        if json_match:
            json_str = json_match.group()
            # Cleaning common issues
            json_str = json_str.replace('\n', ' ').replace('\\', '')
            
            # Trying to parse the JSON
            return json.loads(json_str)
        else:
            # If no JSON found, this create a structured response from the text
            return parse_text_response(llm_output)
            
    except json.JSONDecodeError as e:
        # If JSON parsing fails, fall back to text parsing
        return parse_text_response(llm_output)

def parse_text_response(text: str) -> dict:
    """
    This parses the LLM's text response into structured JSON when JSON parsing fails.
    """
    # This initializes default structure
    result = {
        "risk_score": 50,
        "verdict": "suspicious",
        "reasons": [],
        "confidence": "medium",
        "keywords_found": []
    }
    
    # Extracting risk score if mentioned
    score_match = re.search(r'risk.score.*?(\d+)', text, re.IGNORECASE)
    if score_match:
        result["risk_score"] = int(score_match.group(1))
    
    # Extracting the verdict
    if re.search(r'\b(safe|legitimate|clean)\b', text, re.IGNORECASE):
        result["verdict"] = "safe"
        result["risk_score"] = min(result["risk_score"], 30)
    elif re.search(r'\b(malicious|phishing|scam|fraud)\b', text, re.IGNORECASE):
        result["verdict"] = "malicious"
        result["risk_score"] = max(result["risk_score"], 70)
    
    # Extracting the confidence
    if re.search(r'\b(high|very confident)\b', text, re.IGNORECASE):
        result["confidence"] = "high"
    elif re.search(r'\b(low|not sure|uncertain)\b', text, re.IGNORECASE):
        result["confidence"] = "low"
    
    # Extracting reasons (look for bullet points or numbered lists)
    reasons = re.findall(r'\d+\.\s*(.+?)(?=\n\d+\.|\n\*|\n-|\n\n|$)', text)
    if not reasons:
        # Fallback: look for lines that explain reasoning
        reasons = re.findall(r'[•\-*]\s*(.+?)(?=\n[•\-*]|\n\n|$)', text)
    
    result["reasons"] = reasons[:3]  # Taking top 3 reasons
    
    # Extracting keywords
    keywords = ['urgent', 'verify', 'password', 'account', 'bank', 'security', 'login']
    found_keywords = [kw for kw in keywords if kw in text.lower()]
    result["keywords_found"] = found_keywords
    
    return result

@app.post("/analyze")
def analyze_content(email_text: str = Body(..., embed=True)):
    """
    This analyzes email content for phishing indicators using LLM.
    
    Args:
        email_text: The full email content including subject and body
        
    Returns:
        JSON with risk assessment and detailed analysis
    """
    # Comprehensive prompt for phishing detection
    prompt = f"""
    Analyze this email for phishing indicators. Focus on:
    1. Urgency and pressure tactics
    2. Suspicious requests (passwords, payments, personal info)
    3. Grammar and spelling issues
    4. Unprofessional tone or formatting
    5. Impersonation of legitimate organizations
    
    Email to analyze:
    {email_text}
    
    Respond with ONLY valid JSON in this exact format:
    {{
        "risk_score": 0-100,
        "verdict": "safe/suspicious/malicious",
        "reasons": ["reason1", "reason2", "reason3"],
        "confidence": "low/medium/high",
        "keywords_found": ["urgent", "password", "verify"]
    }}
    """
    
    try:
        # Call Ollama with llama3.2:3b model
        result = subprocess.run(
            ["ollama", "run", "llama3.2:3b", prompt],  # Using the 3b model
            capture_output=True, 
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode == 0:
            # Parsing the LLM response
            analysis_result = extract_json_from_response(result.stdout)
            return {
                "agent": "content_analysis",
                "status": "success",
                "analysis": analysis_result
            }
        else:
            return {
                "agent": "content_analysis", 
                "status": "error",
                "error": result.stderr
            }
            
    except subprocess.TimeoutExpired:
        return {
            "agent": "content_analysis",
            "status": "error", 
            "error": "Analysis timeout - model took too long to respond"
        }
    except Exception as e:
        return {
            "agent": "content_analysis",
            "status": "error",
            "error": str(e)
        }

if __name__ == "__main__":
    import uvicorn
    # Run on port 8001 for content analysis
    uvicorn.run(app, host="0.0.0.0", port=8001)
